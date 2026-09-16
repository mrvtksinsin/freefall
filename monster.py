import pygame
import math
import config
import graphics as gfx
import random

# Seviye bazlı canavar hız ve görünüm
MONSTER_BASE_SPEED = 210.0
MONSTER_SPEED_PER_LEVEL = 14.0
MONSTER_CATCHUP_FACTOR = 42.0  # oyuncu yavaşlayınca yaklaşma
MONSTER_FOLLOW_X_LERP = 2.2

# Bölüm bazlı canavar renkleri
MONSTER_THEMES = {
    "HAVA":           {"body": (60,60,70), "eye": (255,40,40), "accent": (200,200,210), "glow": (90,90,110)},
    "TOPRAK":         {"body": (90,62,38), "eye": (255,200,40), "accent": (160,120,80), "glow": (110,80,40)},
    "KAYA":           {"body": (70,70,78), "eye": (255,60,60), "accent": (180,180,190), "glow": (90,90,100)},
    "MAGMA":          {"body": (120,30,20), "eye": (255,240,80), "accent": (255,90,20), "glow": (255,70,20)},
    "BUZUL":          {"body": (140,180,220), "eye": (40,80,255), "accent": (255,255,255), "glow": (140,180,255)},
    "DERIN":          {"body": (30,40,90), "eye": (80,180,255), "accent": (60,90,160), "glow": (60,90,160)},
    "KATMAN KAYASI":  {"body": (72,62,56), "eye": (255,220,100), "accent": (210,190,170), "glow": (110,100,90)},
    "KANALIZASYON":   {"body": (48,72,52), "eye": (140,255,90), "accent": (90,130,70), "glow": (90,140,70)},
    "CAFE":           {"body": (168,132,92), "eye": (60,30,10), "accent": (255,228,180), "glow": (180,140,100)},
    "OFIS":           {"body": (186,192,200), "eye": (40,80,160), "accent": (90,130,210), "glow": (120,140,170)},
    "BACKROOMS":      {"body": (205,180,120), "eye": (60,60,40), "accent": (255,255,180), "glow": (180,160,100)},
    "GUC SANTRALI":   {"body": (72,72,78), "eye": (255,220,0), "accent": (255,180,0), "glow": (90,90,80)},
    "MUZE":           {"body": (212,206,192), "eye": (80,60,40), "accent": (180,160,120), "glow": (160,150,130)},
    "SINIF":          {"body": (152,182,152), "eye": (30,50,30), "accent": (220,240,220), "glow": (100,140,100)},
    "FABRIKA":        {"body": (52,52,56), "eye": (255,80,40), "accent": (90,90,96), "glow": (80,80,80)},
    "POLIGAN":        {"body": (82,62,122), "eye": (255,80,180), "accent": (140,100,180), "glow": (90,70,130)},
    "ORMAN":          {"body": (42,82,52), "eye": (255,220,40), "accent": (120,200,80), "glow": (60,110,60)},
    "SARAY":          {"body": (182,162,122), "eye": (80,40,10), "accent": (255,215,0), "glow": (160,140,100)},
    "KOY":            {"body": (122,152,92), "eye": (60,30,10), "accent": (200,180,140), "glow": (100,130,80)},
    "SEHIR":          {"body": (62,72,88), "eye": (100,200,255), "accent": (120,140,170), "glow": (80,100,130)},
    "TOKYO":          {"body": (32,32,62), "eye": (255,50,150), "accent": (90,90,140), "glow": (60,60,100)},
    "FRANSA":         {"body": (152,172,202), "eye": (200,40,60), "accent": (255,200,210), "glow": (120,140,170)},
    "FINAL":          {"body": (90,70,140),  "eye": (255,215,0), "accent": (255,215,0), "glow": (90,70,140)},
}

class Monster:
    def __init__(self):
        self.x = config.SCREEN_WIDTH//2 - 44
        self.y = -420  # ekrandan 420px yukarıda başlar (takip)
        self.w = 88
        self.h = 64
        self.vx = 0
        self.vy = 0
        self.anim = 0.0
        self.level = 1
        self.level_name = "HAVA"
        self.base_speed = MONSTER_BASE_SPEED
        self.caught = False

    def reset(self, player_y, level, level_name):
        self.level = level
        self.level_name = level_name
        self.y = player_y - 520  # oyuncudan 520px geride başla
        self.x = config.SCREEN_WIDTH//2 - self.w//2
        self.anim = 0
        self.caught = False
        # seviye bazlı hız
        self.base_speed = MONSTER_BASE_SPEED + (level-1)*MONSTER_SPEED_PER_LEVEL
        # magma, tokyo, final gibi zor seviyelerde ekstra
        if level_name in ("MAGMA","FABRIKA","TOKYO","FRANSA","FINAL"):
            self.base_speed += 22
        if level_name == "FINAL":
            self.base_speed += 12  # final ekstra baskı

    def get_speed(self):
        return self.base_speed

    def update(self, dt, player, camera_y):
        self.anim += dt * (6 + self.level*0.35)
        # Hedef: oyuncunun gerisinde kal, ama yakala
        # Oyuncu hızı yaklaşık vy ~ 400-650, canavar base 210+... oyuncu daha hızlı
        # Ancak oyuncu engelde takılırsa (on_ground ve düşük vx/vy) canavar yaklaşır
        player_vy = player.vy if hasattr(player, 'vy') else 350
        # catchup: oyuncu yavaşsa canavar hızlanır
        # player tıkalıysa (on_ground ve crush_timer) -> ek hız
        extra = 0
        if getattr(player, 'on_ground', False) and abs(getattr(player, 'vy', 0)) < 80:
            extra += MONSTER_CATCHUP_FACTOR * 0.9
        if getattr(player, 'crush_timer', 0) > 0.15:
            extra += 90
        # oyuncu iyi gidiyorsa mesafe açılsın: player hızlı ise canavar biraz yavaş
        if player_vy > 520:
            extra -= 18
        speed = self.base_speed + extra
        # y takip — aşağı doğru
        # canavar hep aşağı gider, oyuncuyu kovalarken y farkını kapatmaya çalışır
        # hedef: oyuncunun 180-260px gerisinde kalmaya çalış, yakalayamazsa yavaş yavaş yaklaş
        target_gap = 220 - min(60, self.level*3)  # seviye arttıkça daha yakın
        desired_y = player.y - target_gap
        # eğer çok gerideyse daha hızlı yaklaş
        gap = player.y - self.y
        if gap > 320:
            speed += (gap - 320) * 0.55
        if gap < 120:
            speed -= (120 - gap) * 0.35
        # aslında canavar aşağı doğru hızla gider
        self.y += speed * dt
        # asla oyuncuyu geçmesin (y > player.y + 30) clamp — yakalayınca death
        # x takip — yumuşak lerp
        target_x = player.x + player.w//2 - self.w//2
        # duvarlara yapışmasın
        target_x = max(6, min(config.SCREEN_WIDTH - self.w - 6, target_x))
        self.x += (target_x - self.x) * MONSTER_FOLLOW_X_LERP * dt
        # animasyon titreme

    def get_rect(self):
        # biraz küçük hitbox — adil
        return pygame.Rect(int(self.x+10), int(self.y+12), self.w-20, self.h-18)

    def check_catch(self, player):
        if self.caught:
            return True
        pr = player.rect
        mr = self.get_rect()
        if mr.colliderect(pr):
            # y farkı küçükse yakaladı
            if abs((self.y + self.h) - (player.y + player.h//2)) < 64:
                self.caught = True
                return True
            # veya canavar oyuncuyu geçmişse
            if self.y + self.h//2 >= player.y + 8 and abs(self.x - player.x) < 38:
                self.caught = True
                return True
        # arkadan çok yaklaşma: mesafe < 36
        if player.y - self.y < 36 and abs(self.x - player.x) < 40:
            self.caught = True
            return True
        return False

    def draw(self, surf, cam_y):
        lvl = self.level_name
        theme = MONSTER_THEMES.get(lvl, MONSTER_THEMES["HAVA"])
        sx = int(self.x)
        sy = int(self.y - cam_y)
        # ekranda değilse çizme (optimizasyon ama gölge için hafif tolerans)
        if sy < -90 or sy > config.SCREEN_HEIGHT + 90:
            return
        # gölge
        shadow_w = self.w - 18
        pygame.draw.ellipse(surf, (0,0,0, 90), pygame.Rect(sx+10, sy+self.h-6, shadow_w, 10))
        # ana gövde — seviye temasına göre
        body_col = theme["body"]
        # vücut bobbing
        bob = math.sin(self.anim*2.1) * 3
        # glow arkasında
        gfx.draw_glow(surf, (sx+self.w//2, sy+self.h//2 + int(bob)), 34, theme["glow"], 28)
        # gövde
        body_rect = pygame.Rect(sx+6, sy+8+int(bob), self.w-12, self.h-18)
        pygame.draw.rect(surf, body_col, body_rect, border_radius=14)
        pygame.draw.rect(surf, (0,0,0), body_rect, width=2, border_radius=14)
        # üst highlight
        pygame.draw.rect(surf, tuple(min(255,c+32) for c in body_col), pygame.Rect(body_rect.x+4, body_rect.y+4, body_rect.width-8, 5), border_radius=3)
        # gözler — parlayan
        eye_y = sy+18+int(bob*0.5)
        # sol göz
        for ex in [sx+22, sx+self.w-22]:
            pygame.draw.circle(surf, (0,0,0), (ex, eye_y), 11)
            pygame.draw.circle(surf, (255,255,255), (ex, eye_y), 9)
            pygame.draw.circle(surf, theme["eye"], (ex, eye_y), 6)
            pygame.draw.circle(surf, (0,0,0), (ex, eye_y), 6, 1)
            pygame.draw.circle(surf, (255,255,255), (ex-2, eye_y-2), 2)
            # göz bebeği takibi — oyuncuya bak
            pygame.draw.circle(surf, (0,0,0), (ex+1, eye_y+1), 2)
        # dişler / ağız
        mouth_y = sy+38+int(bob*0.3)
        pygame.draw.ellipse(surf, (20,10,10), pygame.Rect(sx+self.w//2-18, mouth_y, 36, 14))
        pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(sx+self.w//2-18, mouth_y, 36, 14), 1)
        # dişler
        for dx in [-12,-6,0,6,12]:
            pygame.draw.polygon(surf, (240,240,230), [(sx+self.w//2+dx, mouth_y+2),(sx+self.w//2+dx-3, mouth_y+9),(sx+self.w//2+dx+3, mouth_y+9)])
        # pençe izi accent
        for cx in [sx+12, sx+self.w-12]:
            pygame.draw.line(surf, theme["accent"], (cx, sy+44+int(bob)), (cx, sy+52+int(bob)), 2)
        # seviye yazısı küçük
        # duman / parçacık izi (MAGMA, FABRIKA)
        if lvl in ("MAGMA","FABRIKA","GUC SANTRALI"):
            for i in range(2):
                px = sx + self.w//2 + random.randint(-14,14)
                py = sy - 6 - i*8
                pygame.draw.circle(surf, (80,80,80, 70), (px, py), 3)
        elif lvl == "BUZUL":
            pygame.draw.circle(surf, (200,230,255, 90), (sx+self.w//2, sy-8), 3)
