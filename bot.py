import random
import math
import pygame
import config

class BotPlayer:
    """Bilgisayara karşı rakip — aynı fizik, dengeli zorluk, kusursuz değil."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.w = config.PLAYER_W
        self.h = config.PLAYER_H
        self.on_ground = False
        self.alive = True
        self.coins = 0
        self.distance_px = 0
        self.start_y = y
        self.anim_time = 0.0
        self.facing = 1
        self.state = "idle"
        self.squash = 0.0
        self.was_on_ground = False
        self.crush_timer = 0.0
        self.roll_timer = 0.0
        self.death_anim = 0.0
        # AI params — dengeli, hatalı
        self.reaction = 0.18 + random.random()*0.12  # gecikme
        self.mistake_chance = 0.08  # %8 hata
        self.target_gap_x = None

    def reset(self, x, y):
        self.x=x; self.y=y; self.vx=0; self.vy=0; self.on_ground=False; self.crush_timer=0; self.alive=True; self.death_anim=0; self.coins=0; self.distance_px=0; self.start_y=y; self.anim_time=0; self.roll_timer=0; self.squash=0; self.state="idle"

    @property
    def rect(self):
        return pygame.Rect(int(round(self.x)), int(round(self.y)), self.w, self.h)

    def _find_support(self, obstacles):
        foot_y = self.y + self.h
        for o in obstacles:
            if abs(foot_y - o.top) < 1.5 and self.x + self.w > o.left and self.x < o.right:
                return o
        return None

    def ai_choose(self, obstacles, cam_y):
        """Bir sonraki engelin gap ortasına doğru hedef seç."""
        # Önündeki en yakın engeli bul (y > self.y ve ekran içinde)
        best = None
        best_dist = 1e9
        for o in obstacles:
            # sadece oyuncunun önündeki engeller (y >= self.y)
            if o.y < self.y - 20:
                continue
            if o.y > self.y + 600:
                continue
            # sol/sağ engel — gap bulmak için çiftleri işle
            # Basit: gap ortasını tahmin et
            # Bu engelin karşı eşini bul (aynı y)
            if abs(o.y - self.y) < 300:
                # en yakın
                d = o.y - self.y
                if 0 <= d < best_dist:
                    best_dist = d
                    best = o
        # Hata ekle
        if random.random() < self.mistake_chance:
            return random.choice([-1, 0, 1])
        if best is None:
            return 0
        # Gap tahmini: ekran ortasına gitme eğilimi + rastgele
        # Gerçek gap'i bul: aynı y'deki iki engelin arası
        y = best.y
        left_max = 0
        right_min = config.SCREEN_WIDTH
        for o in obstacles:
            if abs(o.y - y) < 2:
                if o.x == 0:
                    left_max = max(left_max, o.right)
                else:
                    right_min = min(right_min, o.left)
        gap_center = (left_max + right_min) / 2
        # Botun hedefi gap ortası
        bot_center = self.x + self.w/2
        if gap_center < bot_center - 18:
            return -1
        elif gap_center > bot_center + 18:
            return 1
        else:
            return 0

    def handle_ai(self, obstacles, dt):
        if not self.alive:
            return
        dir = self.ai_choose(obstacles, 0)
        # yüzde 10 ihtimal zıplama hazırsa zıpla
        accel = dir
        if accel != 0:
            self.facing = accel
        target_vx = accel * config.MOVE_SPEED * 0.92  # bot biraz yavaş
        accel_factor = config.HORIZONTAL_ACCEL if accel != 0 else config.HORIZONTAL_FRICTION
        # gecikmeli tepki
        self.vx += (target_vx - self.vx) * accel_factor * dt * (0.85 + self.reaction)
        if abs(self.vx) > config.HORIZONTAL_MAX_SPEED:
            self.vx = math.copysign(config.HORIZONTAL_MAX_SPEED, self.vx)
        # rastgele roll (hızlı düşüş) — %2 ihtimal
        if random.random() < 0.015 and self.vy > 100:
            self.vy += config.ROLL_SPEED_BOOST * dt * 2
            self.roll_timer = 0.2
        else:
            if self.roll_timer > 0:
                self.roll_timer -= dt
        # zıplama — yerdeyse %12 ihtimal
        if self.on_ground and random.random() < 0.09:
            # önünde engel varsa zıpla
            if dir != 0 or random.random() < 0.04:
                self.vy = config.JUMP_FORCE
                self.on_ground = False
                self.squash = -0.22
                self.state = "jump"

    def update_physics(self, dt, obstacles):
        self.anim_time += dt
        if self.squash != 0:
            self.squash += dt*4
            if self.squash > 0:
                self.squash = max(0, self.squash - dt*6)
            if abs(self.squash) < 0.02:
                self.squash = 0
        if not self.alive:
            self.death_anim += dt
            self.state = "death"
            return "none"
        support = self._find_support(obstacles) if self.on_ground else None
        if support is not None and self.vy >= -8:
            if self.x + self.w > support.left and self.x < support.right:
                self.y = float(support.top - self.h)
                self.vy = 0.0
                self.on_ground = True
                new_x = self.x + self.vx * dt
                rect_x = pygame.Rect(int(round(new_x)), int(round(self.y)), self.w, self.h)
                blocked_x = any(rect_x.colliderect(o) for o in obstacles)
                if not blocked_x:
                    self.x = new_x
                    if not (self.x + self.w > support.left and self.x < support.right):
                        self.on_ground = False
                else:
                    self.vx *= 0.2
                    if abs(self.vx) < 1:
                        self.vx = 0
                self.was_on_ground = self.on_ground
                if self.y > self.start_y:
                    self.distance_px = self.y - self.start_y
                if self.on_ground:
                    self.state = "run" if abs(self.vx) > 18 else "idle"
                return "none"
        self.vy += config.GRAVITY * dt
        cur_max = config.MAX_FALL_SPEED * (1.25 if self.roll_timer > 0 else 1.0)
        if self.vy > cur_max:
            self.vy = cur_max
        if self.vy < -900:
            self.vy = -900
        new_x = self.x + self.vx * dt
        rect_x = pygame.Rect(int(round(new_x)), int(round(self.y)), self.w, self.h)
        blocked_x = any(rect_x.colliderect(o) for o in obstacles)
        if not blocked_x:
            self.x = new_x
        else:
            self.vx *= 0.15
            if abs(self.vx) < 2:
                self.vx = 0
        new_y = self.y + self.vy * dt
        collided = None
        best_dist = float('inf')
        for o in obstacles:
            if self.x + self.w <= o.left or self.x >= o.right:
                continue
            if self.vy > 0:
                if self.y + self.h <= o.top and new_y + self.h >= o.top:
                    dist = o.top - (self.y + self.h)
                    if dist < best_dist:
                        best_dist = dist; collided = o
            elif self.vy < 0:
                if self.y >= o.bottom and new_y <= o.bottom:
                    dist = self.y - o.bottom
                    if dist < best_dist:
                        best_dist = dist; collided = o
        if collided is None:
            rect_y = pygame.Rect(int(round(self.x)), int(round(new_y)), self.w, self.h)
            for o in obstacles:
                if rect_y.colliderect(o):
                    collided = o; break
        event = "none"
        if collided:
            if self.vy > 0:
                self.y = float(collided.top - self.h)
                if not self.was_on_ground:
                    self.squash = 0.28; event = "land"
                self.vy = 0; self.on_ground = True
            else:
                self.y = float(collided.bottom); self.vy = 0; self.on_ground = False
        else:
            self.y = new_y; self.on_ground = False
        self.was_on_ground = self.on_ground
        if self.y > self.start_y:
            self.distance_px = self.y - self.start_y
        if not self.on_ground:
            self.state = "jump" if self.vy < -50 else ("roll" if self.roll_timer > 0 else "fall")
        else:
            self.state = "run" if abs(self.vx) > 20 else "idle"
        # crush
        touching=False
        expanded=pygame.Rect(int(round(self.x))-1,int(round(self.y))-1,self.w+2,self.h+2)
        for o in obstacles:
            if expanded.colliderect(o):
                touching=True; break
        if touching and abs(self.vx)<10 and abs(self.vy)<10 and self.on_ground:
            above_rect=pygame.Rect(int(self.x),int(self.y)-8,self.w,8)
            has_above=any(above_rect.colliderect(o) for o in obstacles)
            if has_above:
                self.crush_timer+=dt
            else:
                left_rect=pygame.Rect(int(round(self.x))-6,int(round(self.y))+4,6,self.h-8)
                right_rect=pygame.Rect(int(round(self.x))+self.w,int(round(self.y))+4,6,self.h-8)
                has_left=any(left_rect.colliderect(o) for o in obstacles)
                has_right=any(right_rect.colliderect(o) for o in obstacles)
                if has_left and has_right:
                    self.crush_timer+=dt
                else:
                    self.crush_timer=max(0,self.crush_timer-dt*2)
        else:
            if touching and self.on_ground and abs(self.vx)<5:
                self.crush_timer+=dt*0.4
            else:
                self.crush_timer=max(0,self.crush_timer-dt*1.5)
        if self.crush_timer>0.7:
            self.alive=False; self.crush_timer=0.7; self.state="death"; event="death"
        return event

    def draw(self, surf, cam_y, char_data, equipped, theme):
        # Aynı Player draw ama hafif şeffaf + BOT etiketi
        import math, graphics as gfx
        from player import CHAR_OFFSETS, CHAR_DETAILS
        sx=int(round(self.x)); sy=int(round(self.y - cam_y))
        color=char_data["color"]; accent=char_data["accent"]
        cid=char_data["id"]
        # bot ghost effect — hafif koyu
        # reuse Player draw logic simplified: call Player draw via temp? For now simple rect + etiket
        # Basit bot çizimi: Player'ın aynısı ama BOT yazısı
        from player import Player as _P
        # Create temp player to draw — but we need to avoid recursion
        # Inline minimal draw: gövde + kafa + BOT tag
        # Use same logic as Player.draw but with alpha
        offsets=CHAR_OFFSETS.get(cid, CHAR_OFFSETS["default"])
        det = CHAR_DETAILS.get(cid, CHAR_DETAILS["cop_adam"])
        squash=self.squash
        bob=0; tilt=0; stretch=1.0; leg_swing=0
        if self.state=="run" and self.alive:
            bob=math.sin(self.anim_time*13)*1.6
            leg_swing=math.sin(self.anim_time*13)*14
            tilt=math.sin(self.anim_time*13)*0.04*self.facing
        elif self.state=="fall":
            bob=math.sin(self.anim_time*5)*1.0
            leg_swing=math.sin(self.anim_time*6)*6
        elif self.state=="roll":
            tilt=self.facing*0.18; stretch=0.88
            leg_swing=math.sin(self.anim_time*18)*18
        elif self.state=="jump":
            stretch=1.08; bob=math.sin(self.anim_time*8)*0.8
        if squash!=0: stretch+=squash
        bh=int(self.h*stretch); bw=int(self.w*(2-stretch))
        bx=sx+(self.w-bw)//2; by=sy+(self.h-bh)
        body_rect=pygame.Rect(bx, int(by+bob), bw, bh)
        # gölge
        pygame.draw.ellipse(surf, (0,0,0,70), pygame.Rect(sx+self.w//2-(bw-4)//2, sy+self.h-3, max(10,bw-4), 6))
        if self.alive:
            gfx.draw_glow(surf, (sx+self.w//2, int(by+bh//2+bob)), 22, accent, 14)
        pygame.draw.rect(surf, color, body_rect, border_radius=9)
        dark = tuple(max(0,c-38) for c in color)
        shadow_rect=pygame.Rect(body_rect.x, body_rect.y+body_rect.height-12, body_rect.width, 12)
        pygame.draw.rect(surf, dark, shadow_rect, border_radius=6)
        high = tuple(min(255,c+32) for c in color)
        pygame.draw.rect(surf, high, pygame.Rect(body_rect.x+3, body_rect.y+3, body_rect.width-6, 6), border_radius=3)
        pygame.draw.rect(surf, (0,0,0), body_rect, width=2, border_radius=9)
        # BOT etiketi üstte
        tag = pygame.font.SysFont("Arial", 10, bold=True).render("BOT", True, (255,255,255))
        tag_bg = pygame.Rect(sx+self.w//2 - tag.get_width()//2 -4, sy-14, tag.get_width()+8, 12)
        pygame.draw.rect(surf, (200,30,30), tag_bg, border_radius=4)
        pygame.draw.rect(surf, (0,0,0), tag_bg, width=1, border_radius=4)
        surf.blit(tag, (tag_bg.centerx - tag.get_width()//2, tag_bg.centery - tag.get_height()//2))
        # kafa basit
        head_r=12
        head_cx=sx+self.w//2 + int(tilt*6)
        head_cy=int(by+10 + bob*0.4)
        pygame.draw.circle(surf, (255,220,180), (head_cx, head_cy), head_r)
        pygame.draw.circle(surf, (0,0,0), (head_cx, head_cy), head_r, 2)
        # göz
        pygame.draw.ellipse(surf, (255,255,255), pygame.Rect(head_cx-6, head_cy-2, 5, 6))
        pygame.draw.ellipse(surf, (255,255,255), pygame.Rect(head_cx+1, head_cy-2, 5, 6))
        pygame.draw.circle(surf, (60,40,20), (head_cx-3, head_cy+1), 2)
        pygame.draw.circle(surf, (60,40,20), (head_cx+4, head_cy+1), 2)
