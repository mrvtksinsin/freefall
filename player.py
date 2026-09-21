import pygame
import math
import config
import graphics as gfx

CHAR_OFFSETS = {
    "default": {"hat": (0,-11), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 8)},
    "cop_adam": {"hat": (0,-11), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 8)},
    "madame":  {"hat": (0,-13), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 8)},
    "kadin":   {"hat": (0,-12), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 8)},
    "erkek":   {"hat": (0,-11), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 8)},
    "asker":   {"hat": (0,-10), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 8)},
    "ninja":   {"hat": (0,-13), "glasses": (0,-3), "bag": (9, 11), "cane": (-7, 9)},
    "balon":   {"hat": (0,-15), "glasses": (0,-4), "bag": (8, 12), "cane": (-6, 10)},
    "sihirbaz":{"hat": (0,-16), "glasses": (0,-2), "bag": (8, 10), "cane": (-8, 6)},
    "noel_baba":{"hat": (0,-14), "glasses": (0,-2), "bag": (9, 9), "cane": (-7, 7)},
    "soylu":   {"hat": (0,-12), "glasses": (0,-2), "bag": (8, 9), "cane": (-6, 9)},
    "soytari": {"hat": (0,-17), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 8)},
    "ayi":     {"hat": (0,-10), "glasses": (0,-1), "bag": (9, 11), "cane": (-7, 9)},
    "tavuk":   {"hat": (0,-14), "glasses": (0,-3), "bag": (8, 9),  "cane": (-6, 8)},
    "robot":   {"hat": (0,-12), "glasses": (0,-2), "bag": (8, 10), "cane": (-6, 7)},
    "iskelet": {"hat": (0,-13), "glasses": (0,-2), "bag": (8, 10), "cane": (-7, 8)},
    "korsan":  {"hat": (0,-12), "glasses": (0,-2), "bag": (9, 10), "cane": (-7, 9)},
    "gotik_kiz":{"hat": (0,-15), "glasses": (0,-2), "bag": (8, 11), "cane": (-6, 8)},
    "gotik_erkek":{"hat": (0,-15), "glasses": (0,-2), "bag": (8, 11), "cane": (-6, 8)},
}

# Karaktere özel detay renkleri ve ikincil accent
CHAR_DETAILS = {
    "cop_adam":   {"secondary": (110,110,110), "shoe": (50,50,50),  "skin_accent": (220,180,140)},
    "soylu":      {"secondary": (90,20,20),   "shoe": (20,20,20),  "skin_accent": (255,215,160)},
    "madame":     {"secondary": (140,30,70),  "shoe": (80,20,40),  "skin_accent": (255,200,180)},
    "kadin":      {"secondary": (200,80,110), "shoe": (60,30,40),  "skin_accent": (255,210,190)},
    "erkek":      {"secondary": (20,60,120),  "shoe": (30,30,30),  "skin_accent": (235,205,165)},
    "noel_baba":  {"secondary": (160,20,20),  "shoe": (30,15,10),  "skin_accent": (255,230,200)},
    "ninja":      {"secondary": (30,30,30),   "shoe": (10,10,10),  "skin_accent": (245,210,180)},
    "sihirbaz":   {"secondary": (60,20,90),   "shoe": (40,20,60),  "skin_accent": (255,220,180)},
    "asker":      {"secondary": (40,70,30),   "shoe": (35,25,15),  "skin_accent": (235,205,160)},
    "balon":      {"secondary": (255,160,40), "shoe": (255,100,80), "skin_accent": (255,235,200)},
    "soytari":    {"secondary": (160,30,80),  "shoe": (120,20,60),  "skin_accent": (255,220,180)},
    "ayi":        {"secondary": (90,60,40),   "shoe": (60,40,20),   "skin_accent": (210,180,140)},
    "tavuk":      {"secondary": (220,200,120),"shoe": (200,160,60), "skin_accent": (255,235,180)},
    "robot":      {"secondary": (100,110,120),"shoe": (70,80,90),   "skin_accent": (200,230,255)},
    "iskelet":    {"secondary": (180,180,180),"shoe": (90,90,90),   "skin_accent": (240,240,230)},
    "korsan":     {"secondary": (30,30,70),   "shoe": (20,20,40),   "skin_accent": (235,210,180)},
    "gotik_kiz":  {"secondary": (80,20,50),   "shoe": (20,10,20),   "skin_accent": (255,200,210)},
    "gotik_erkek":{"secondary": (20,20,40),   "shoe": (15,15,25),   "skin_accent": (220,200,230)},
}

class Player:
    def __init__(self, x, y):
        self.x = x; self.y = y
        self.vx = 0.0; self.vy = 0.0
        self.w = config.PLAYER_W; self.h = config.PLAYER_H
        self.on_ground = False
        self.crush_timer = 0.0
        self.alive = True; self.death_anim = 0.0
        self.coins = 0; self.distance_px = 0.0; self.start_y = y
        self.anim_time = 0.0; self.facing = 1
        self.state = "idle"; self.roll_timer = 0.0
        self.was_on_ground = False; self.squash = 0.0

    @property
    def rect(self):
        # Fizik rect'i — integer'a yuvarlamadan önce float korunur, collision hassas
        return pygame.Rect(int(round(self.x)), int(round(self.y)), self.w, self.h)

    @property
    def physics_pos(self):
        """Gerçek fizik konumu (float) — render'dan bağımsız."""
        return (self.x, self.y)

    @property
    def render_pos(self):
        """Render için ideal konum — kamera sonrası hesaplanacak, fizikle karışmaz."""
        return (self.x, self.y)

    def reset(self, x, y):
        self.x=x; self.y=y; self.vx=0; self.vy=0; self.on_ground=False; self.crush_timer=0; self.alive=True; self.death_anim=0; self.coins=0; self.distance_px=0; self.start_y=y; self.anim_time=0; self.roll_timer=0; self.squash=0; self.state="idle"

    def handle_input(self, keys, dt):
        if not self.alive: return
        accel=0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: accel-=1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: accel+=1
        if accel!=0: self.facing=accel
        target_vx=accel*config.MOVE_SPEED
        accel_factor=config.HORIZONTAL_ACCEL if accel!=0 else config.HORIZONTAL_FRICTION
        # tek lerp ile hem ivme hem sürtünme - çift çarpımı önlendi
        self.vx += (target_vx - self.vx)*accel_factor*dt
        if abs(accel)<0.1 and abs(self.vx)<5: self.vx=0
        if abs(self.vx)>config.HORIZONTAL_MAX_SPEED: self.vx=math.copysign(config.HORIZONTAL_MAX_SPEED, self.vx)
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.vy+=config.ROLL_SPEED_BOOST*dt*3; self.roll_timer=0.25; self.state="roll"
        else:
            if self.roll_timer>0: self.roll_timer-=dt

    def try_jump(self):
        if self.on_ground and self.alive:
            self.vy=config.JUMP_FORCE; self.on_ground=False; self.squash=-0.25; self.state="jump"; return True
        return False

    def _find_support(self, obstacles):
        """Ayak altında destek var mı? Float tolerans ile."""
        foot_y = self.y + self.h
        for o in obstacles:
            if abs(foot_y - o.top) < 1.5 and self.x + self.w > o.left and self.x < o.right:
                return o
        return None

    def update_physics(self, dt, obstacles):
        self.anim_time+=dt
        if self.squash!=0:
            self.squash+=dt*4
            if self.squash>0: self.squash=max(0,self.squash-dt*6)
            if abs(self.squash)<0.02: self.squash=0
        if not self.alive:
            self.death_anim+=dt; self.state="death"; return "none"

        # --- KÖK: grounded stabilizasyon — fizik ile render ayrımı ---
        # Oyuncu yerdeyse gravity uygulama, y'yi support'a kilitle (titreme root-cause)
        # Bu dalda vy kesin 0, y kesin support.top - h, sprite animasyonu fiziği etkilemez
        support = self._find_support(obstacles) if self.on_ground else None
        if support is not None and self.vy >= -8:
            if self.x + self.w > support.left and self.x < support.right:
                self.y = float(support.top - self.h)
                self.vy = 0.0
                self.on_ground = True
                # yatay kayma — int(round) ile collision hassas, sub-pixel jitter yok
                new_x = self.x + self.vx * dt
                rect_x = pygame.Rect(int(round(new_x)), int(round(self.y)), self.w, self.h)
                blocked_x = any(rect_x.colliderect(o) for o in obstacles)
                if not blocked_x:
                    self.x = new_x
                    if not (self.x + self.w > support.left and self.x < support.right):
                        self.on_ground = False
                else:
                    self.vx *= 0.2  # yumuşak sönümle, aniden 0 yaparak jitter üretme
                    if abs(self.vx) < 1:
                        self.vx = 0
                self.was_on_ground = self.on_ground
                if self.y > self.start_y:
                    self.distance_px = self.y - self.start_y
                if self.on_ground:
                    if abs(self.vx) > 18:
                        self.state = "run"
                    else:
                        self.state = "idle"
                return "none"

        self.vy+=config.GRAVITY*dt
        cur_max=config.MAX_FALL_SPEED*(1.25 if self.roll_timer>0 else 1.0)
        if self.vy>cur_max: self.vy=cur_max
        if self.vy<-900: self.vy=-900
        new_x=self.x+self.vx*dt
        rect_x=pygame.Rect(int(round(new_x)),int(round(self.y)),self.w,self.h)
        blocked_x=any(rect_x.colliderect(o) for o in obstacles)
        if not blocked_x:
            self.x=new_x
        else:
            # duvara çarpınca hızı sönümle — aniden sıfırlama jitter yapar
            self.vx *= 0.15
            if abs(self.vx) < 2:
                self.vx = 0
        new_y=self.y+self.vy*dt
        # dikey collision float tabanlı (int truncation jitterını azalt)
        collided=None
        # önce aşağı doğru hareket için en yakın engeli bul
        best_dist = float('inf')
        for o in obstacles:
            # x overlap var mı?
            if self.x + self.w <= o.left or self.x >= o.right:
                continue
            if self.vy > 0:
                # aşağı inerken: ayak o.top'u geçiyor mu?
                if self.y + self.h <= o.top and new_y + self.h >= o.top:
                    dist = o.top - (self.y + self.h)
                    if dist < best_dist:
                        best_dist = dist; collided = o
            elif self.vy < 0:
                if self.y >= o.bottom and new_y <= o.bottom:
                    dist = self.y - o.bottom
                    if dist < best_dist:
                        best_dist = dist; collided = o
        # fallback: rect overlap (hızlı hareket / tünelleme koruma) — round ile hassas
        if collided is None:
            rect_y=pygame.Rect(int(round(self.x)),int(round(new_y)),self.w,self.h)
            for o in obstacles:
                if rect_y.colliderect(o):
                    collided=o; break
        event="none"
        if collided:
            if self.vy>0:
                self.y=float(collided.top-self.h)
                if not self.was_on_ground: self.squash=0.28; event="land"
                self.vy=0; self.on_ground=True
            else:
                self.y=float(collided.bottom); self.vy=0; self.on_ground=False
        else:
            self.y=new_y; self.on_ground=False
        self.was_on_ground=self.on_ground
        if self.y>self.start_y: self.distance_px=self.y-self.start_y
        if not self.on_ground:
            if self.vy<-50: self.state="jump"
            elif self.roll_timer>0: self.state="roll"
            else: self.state="fall"
        else:
            if abs(self.vx)>20: self.state="run"
            else: self.state="idle"
        # crush — sadece gerçekten sıkışınca
        touching=False
        expanded=pygame.Rect(int(round(self.x))-1,int(round(self.y))-1,self.w+2,self.h+2)
        for o in obstacles:
            if expanded.colliderect(o):
                touching=True; break
        if touching and abs(self.vx)<10 and abs(self.vy)<10 and self.on_ground:
            above_rect=pygame.Rect(int(self.x),int(self.y)-8,self.w,8)
            has_above=any(above_rect.colliderect(o) for o in obstacles)
            if has_above: self.crush_timer+=dt
            else:
                left_rect=pygame.Rect(int(round(self.x))-6,int(round(self.y))+4,6,self.h-8)
                right_rect=pygame.Rect(int(round(self.x))+self.w,int(round(self.y))+4,6,self.h-8)
                has_left=any(left_rect.colliderect(o) for o in obstacles)
                has_right=any(right_rect.colliderect(o) for o in obstacles)
                if has_left and has_right: self.crush_timer+=dt
                else: self.crush_timer=max(0,self.crush_timer-dt*2)
        else:
            if touching and self.on_ground and abs(self.vx)<5: self.crush_timer+=dt*0.4
            else: self.crush_timer=max(0,self.crush_timer-dt*1.5)
        if self.crush_timer>0.7:
            self.alive=False; self.crush_timer=0.7; self.state="death"; event="death"
        return event

    def draw(self, surf, cam_y, char_data, equipped, theme):
        # RENDER POSITION = physics - camera, tek bir round — sub-pixel jitter'ı bitirir
        # squash/bob/tilt sadece görsel, fizik rect'ini asla değiştirmez
        sx=int(round(self.x)); sy=int(round(self.y - cam_y))
        color=char_data["color"]; accent=char_data["accent"]
        cid=char_data["id"]
        offsets=CHAR_OFFSETS.get(cid, CHAR_OFFSETS["default"])
        det = CHAR_DETAILS.get(cid, CHAR_DETAILS["cop_adam"])

        # anim params
        squash=self.squash
        bob=0; tilt=0; stretch=1.0; leg_swing=0; arm_swing=0
        if self.state=="run" and self.alive:
            bob=math.sin(self.anim_time*13)*1.6
            leg_swing=math.sin(self.anim_time*13)*14
            arm_swing=math.sin(self.anim_time*13+math.pi)*10
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

        bh=int(self.h*stretch)
        bw=int(self.w*(2-stretch))
        bx=sx+(self.w-bw)//2
        by=sy+(self.h-bh)
        body_rect=pygame.Rect(bx, int(by+bob), bw, bh)

        # gölge
        shadow_w=max(10,bw-4)
        pygame.draw.ellipse(surf, (0,0,0,80), pygame.Rect(sx+self.w//2-shadow_w//2, sy+self.h-3, shadow_w, 7))
        # hafif glow karakter etrafında (canlıysa)
        if self.alive:
            gfx.draw_glow(surf, (sx+self.w//2, int(by+bh//2+bob)), 26, accent, 18)

        # ÇANTA — vücudun ARKASINDA çizilir (arka taraf, bakış yönünün karşısı)
        bx_off, by_off = offsets["bag"]
        bag = equipped.get("bag")
        if bag:
            side = -1 if self.facing >= 0 else 1
            bag_x = body_rect.x - 6 if side < 0 else body_rect.right - 6
            br = pygame.Rect(bag_x, body_rect.y + 10 + by_off, 12, 16)
            self._draw_bag(surf, br, bag)

        # VÜCUT - katmanlı
        # ana gövde gradient gibi iki ton
        # önce base
        pygame.draw.rect(surf, color, body_rect, border_radius=10)
        # iç gölge alt kısım
        shadow_rect=pygame.Rect(body_rect.x, body_rect.y+body_rect.height-12, body_rect.width, 12)
        dark = tuple(max(0,c-38) for c in color)
        pygame.draw.rect(surf, dark, shadow_rect, border_radius=6)
        # üst highlight
        high = tuple(min(255,c+32) for c in color)
        pygame.draw.rect(surf, high, pygame.Rect(body_rect.x+3, body_rect.y+3, body_rect.width-6, 6), border_radius=3)
        # dış kenar
        pygame.draw.rect(surf, (0,0,0), body_rect, width=2, border_radius=10)
        # accent yatay şerit + dikey detay
        stripe_y = body_rect.y + body_rect.height//2 - 2
        pygame.draw.rect(surf, accent, pygame.Rect(body_rect.x+5, stripe_y, body_rect.width-10, 4), border_radius=2)
        # karakter özel detay: soylu yakası, ninja kuşak vb.
        self._draw_char_costume(surf, body_rect, cid, color, accent, det)

        # KOLLAR - basit procedural
        arm_w=6; arm_h=16
        # sol kol
        l_arm_x = body_rect.x -3 + int(math.sin(self.anim_time*13+0.5)*2 if self.state=="run" else 0)
        r_arm_x = body_rect.right -3 + int(math.sin(self.anim_time*13+math.pi+0.5)*2 if self.state=="run" else 0)
        arm_y = body_rect.y+10 + int(bob*0.5)
        # kolları çiz (fall'da açık)
        if self.state in ("fall","jump"):
            # kollar yana açık
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(l_arm_x-6, arm_y+2, arm_w+2, 10), border_radius=4)
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(r_arm_x+2, arm_y+2, arm_w+2, 10), border_radius=4)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(l_arm_x-6, arm_y+2, arm_w+2, 10), width=1, border_radius=4)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(r_arm_x+2, arm_y+2, arm_w+2, 10), width=1, border_radius=4)
        elif self.state=="roll":
            # kollar vücuda yapışık dönüş
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(body_rect.x+2, arm_y, 5, 12), border_radius=3)
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(body_rect.right-7, arm_y, 5, 12), border_radius=3)
        else:
            # normal sallanan kollar
            la_y = arm_y + int(arm_swing*0.18)
            ra_y = arm_y - int(arm_swing*0.18)
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(l_arm_x, la_y, arm_w, arm_h), border_radius=4)
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(r_arm_x, ra_y, arm_w, arm_h), border_radius=4)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(l_arm_x, la_y, arm_w, arm_h), width=1, border_radius=4)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(r_arm_x, ra_y, arm_w, arm_h), width=1, border_radius=4)
            # eller (ten)
            pygame.draw.circle(surf, (255,220,180), (l_arm_x+3, la_y+arm_h+2), 4)
            pygame.draw.circle(surf, (255,220,180), (r_arm_x+3, ra_y+arm_h+2), 4)

        # BACAKLAR + AYAKKABI
        leg_w=8; leg_h=10
        # balon karakteri için balon çiz (bacak yerine)
        if cid=="balon" and self.alive:
            # balon gövdesi altında
            bx_c = sx+self.w//2 + int(tilt*6)
            by_c = body_rect.bottom -2 + int(bob*0.3)
            # ip
            pygame.draw.line(surf, (80,80,80), (bx_c, by_c), (bx_c+ int(math.sin(self.anim_time*3)*4), by_c+12), 1)
            # balon
            balloon_rect = pygame.Rect(bx_c-14, by_c+10, 28, 34)
            pygame.draw.ellipse(surf, (255,100,100), balloon_rect)
            pygame.draw.ellipse(surf, (255,180,180), pygame.Rect(balloon_rect.x+5, balloon_rect.y+6, 10, 8))
            pygame.draw.ellipse(surf, (0,0,0), balloon_rect, 2)
            # bacaklar küçük
            pygame.draw.rect(surf, color, pygame.Rect(body_rect.x+6, body_rect.bottom-4, 6, 6), border_radius=2)
            pygame.draw.rect(surf, color, pygame.Rect(body_rect.right-12, body_rect.bottom-4, 6, 6), border_radius=2)
        else:
            # normal bacaklar - swing
            ls = math.sin(math.radians(leg_swing))
            l_leg_x = body_rect.x+5 + int(ls*2)
            r_leg_x = body_rect.right-13 - int(ls*2)
            l_leg_y = body_rect.bottom -2
            r_leg_y = body_rect.bottom -2
            if self.state=="run":
                l_leg_y += int(abs(ls)*3)
                r_leg_y += int(abs(ls)*3)
            elif self.state=="jump":
                l_leg_x -=2; r_leg_x+=2
            # bacak
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(l_leg_x, l_leg_y, leg_w, leg_h), border_radius=3)
            pygame.draw.rect(surf, det["secondary"], pygame.Rect(r_leg_x, r_leg_y, leg_w, leg_h), border_radius=3)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(l_leg_x, l_leg_y, leg_w, leg_h), width=1, border_radius=3)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(r_leg_x, r_leg_y, leg_w, leg_h), width=1, border_radius=3)
            # ayakkabı
            shoe_col = det["shoe"]
            pygame.draw.ellipse(surf, shoe_col, pygame.Rect(l_leg_x-2, l_leg_y+leg_h-2, leg_w+4, 6))
            pygame.draw.ellipse(surf, shoe_col, pygame.Rect(r_leg_x-2, r_leg_y+leg_h-2, leg_w+4, 6))
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(l_leg_x-2, l_leg_y+leg_h-2, leg_w+4, 6), 1)
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(r_leg_x-2, r_leg_y+leg_h-2, leg_w+4, 6), 1)
            # ayakkabı bağcığı detayı
            pygame.draw.line(surf, (255,255,255), (l_leg_x+2, l_leg_y+leg_h+1), (l_leg_x+6, l_leg_y+leg_h+1), 1)
            pygame.draw.line(surf, (255,255,255), (r_leg_x+2, r_leg_y+leg_h+1), (r_leg_x+6, r_leg_y+leg_h+1), 1)

        # KAFA - daha detaylı
        head_r=13
        head_cx=sx+self.w//2 + int(tilt*7)
        head_cy=int(by+11 + bob*0.4)
        # boyun
        pygame.draw.rect(surf, (255,220,180), pygame.Rect(head_cx-4, head_cy+8, 8, 6), border_radius=2)
        # kafa gölgesi
        pygame.draw.circle(surf, (30,30,30), (head_cx+1, head_cy+1), head_r)
        # ten
        pygame.draw.circle(surf, (255,220,180), (head_cx, head_cy), head_r)
        # yanak pembeliği
        pygame.draw.circle(surf, (255,180,180), (head_cx-6, head_cy+3), 2)
        pygame.draw.circle(surf, (255,180,180), (head_cx+6, head_cy+3), 2)
        # saç / karakter saç detayı
        self._draw_hair(surf, head_cx, head_cy, head_r, cid, color)
        # kafa kenarı
        pygame.draw.circle(surf, (0,0,0), (head_cx, head_cy), head_r, 2)
        # gözler
        eye_off = 3 * self.facing if self.state in ("run","fall","roll") else 0
        ex=head_cx+eye_off
        # göz beyazı
        pygame.draw.ellipse(surf, (255,255,255), pygame.Rect(ex-7, head_cy-3, 6, 7))
        pygame.draw.ellipse(surf, (255,255,255), pygame.Rect(ex+1, head_cy-3, 6, 7))
        pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(ex-7, head_cy-3, 6, 7), 1)
        pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(ex+1, head_cy-3, 6, 7), 1)
        if not self.alive:
            # X göz
            pygame.draw.line(surf, (220,0,0), (ex-7, head_cy-3), (ex-1, head_cy+3), 2)
            pygame.draw.line(surf, (220,0,0), (ex-1, head_cy-3), (ex-7, head_cy+3), 2)
            pygame.draw.line(surf, (220,0,0), (ex+1, head_cy-3), (ex+7, head_cy+3), 2)
            pygame.draw.line(surf, (220,0,0), (ex+7, head_cy-3), (ex+1, head_cy+3), 2)
        else:
            # iris
            iris_x_off = 1*self.facing
            pygame.draw.circle(surf, (60,40,20), (ex-4+iris_x_off, head_cy+1), 2)
            pygame.draw.circle(surf, (60,40,20), (ex+4+iris_x_off, head_cy+1), 2)
            pygame.draw.circle(surf, (0,0,0), (ex-4+iris_x_off, head_cy+1), 1)
            pygame.draw.circle(surf, (0,0,0), (ex+4+iris_x_off, head_cy+1), 1)
            # parlama
            pygame.draw.circle(surf, (255,255,255), (ex-3+iris_x_off, head_cy+0), 1)
            pygame.draw.circle(surf, (255,255,255), (ex+5+iris_x_off, head_cy+0), 1)
            # kaş
            brow_y = head_cy-5
            pygame.draw.line(surf, (80,50,30), (ex-7, brow_y), (ex-1, brow_y-1), 2)
            pygame.draw.line(surf, (80,50,30), (ex+1, brow_y-1), (ex+7, brow_y), 2)
            # ağız
            if self.state=="roll":
                pygame.draw.ellipse(surf, (120,30,30), pygame.Rect(ex-3, head_cy+5, 6, 4))
                pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(ex-3, head_cy+5, 6, 4), 1)
            elif self.state=="jump":
                pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(ex-4, head_cy+5, 8, 5))
                pygame.draw.ellipse(surf, (180,60,60), pygame.Rect(ex-3, head_cy+6, 6, 3))
            else:
                # gülümseme
                pygame.draw.arc(surf, (0,0,0), (ex-5, head_cy+3, 10, 6), 3.14, 0, 2)
                # alt dudak
                pygame.draw.line(surf, (180,80,80), (ex-2, head_cy+7), (ex+2, head_cy+7), 1)

        # KOZMETİKLER
        ox, oy = offsets["hat"]
        hat=equipped.get("hat")
        if hat:
            self._draw_hat(surf, head_cx-head_r+ox, head_cy-head_r-3+oy, hat)
        gx, gy = offsets["glasses"]
        glasses=equipped.get("glasses")
        if glasses:
            self._draw_glasses(surf, head_cx+gx, head_cy+gy, glasses)
        cx_off, cy_off = offsets["cane"]
        cane=equipped.get("cane")
        if cane:
            cane_x = sx - 7 + cx_off
            if self.facing >= 0:
                cane_x = 2*(sx + self.w//2) - (cane_x + 6)
            cr=pygame.Rect(cane_x, int(by+7+cy_off), 6, bh-3)
            self._draw_cane(surf, cr, cane, self.state)

        # crush
        if self.crush_timer>0.2 and self.alive:
            t=int(self.crush_timer*10)%2
            if t==0:
                pygame.draw.rect(surf, (255,0,0), body_rect, width=3, border_radius=10)
                ex2=body_rect.centerx; ey=body_rect.y-16
                pygame.draw.polygon(surf, (255,30,30), [(ex2,ey),(ex2-8,ey+13),(ex2+8,ey+13)])
                pygame.draw.polygon(surf, (0,0,0), [(ex2,ey),(ex2-8,ey+13),(ex2+8,ey+13)], 2)
                # ünlem
                txt = pygame.font.SysFont("Arial", 14, bold=True).render("!", True, (255,255,255))
                surf.blit(txt, (ex2 - txt.get_width()//2, ey+1))
                # ekran titreşim hissi için kırmızı vignette
                # (game'de değil burada hafif)

    def _draw_char_costume(self, surf, rect, cid, col, accent, det):
        # her karaktere özel kostüm detayı
        if cid=="soylu":
            # yakalı ceket
            pygame.draw.polygon(surf, (0,0,0), [(rect.x+8, rect.y+8),(rect.centerx, rect.y+18),(rect.x+8, rect.y+18)])
            pygame.draw.polygon(surf, (0,0,0), [(rect.right-8, rect.y+8),(rect.centerx, rect.y+18),(rect.right-8, rect.y+18)])
            pygame.draw.line(surf, (255,215,0), (rect.centerx, rect.y+12),(rect.centerx, rect.bottom-8),2)
            for y in [rect.y+22, rect.y+30, rect.y+38]:
                pygame.draw.circle(surf, (255,215,0), (rect.centerx, y), 2)
                pygame.draw.circle(surf, (0,0,0), (rect.centerx, y), 2,1)
        elif cid=="madame":
            # elbise fırfırı
            pygame.draw.ellipse(surf, accent, pygame.Rect(rect.x+4, rect.bottom-10, rect.width-8, 10))
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(rect.x+4, rect.bottom-10, rect.width-8, 10),1)
            # kemer
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+6, rect.centery+4, rect.width-12, 3), border_radius=2)
            pygame.draw.circle(surf, (255,215,0), (rect.centerx, rect.centery+5), 4)
        elif cid=="ninja":
            # kuşak
            pygame.draw.rect(surf, (200,30,30), pygame.Rect(rect.x+2, rect.centery+2, rect.width-4, 6), border_radius=2)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+2, rect.centery+2, rect.width-4, 6), width=1, border_radius=2)
            # maske çizgisi (boyunda)
            pygame.draw.line(surf, (0,0,0), (rect.x+4, rect.y+6),(rect.x+rect.width-4, rect.y+6),1)
        elif cid=="sihirbaz":
            # yıldızlar
            for i, pos in enumerate([(rect.x+8, rect.y+12),(rect.right-10, rect.y+16),(rect.centerx, rect.y+28)]):
                pygame.draw.polygon(surf, (255,215,0), [(pos[0],pos[1]-4),(pos[0]-3,pos[1]+2),(pos[0]+3,pos[1]+2)])
            # düğmeler
            pygame.draw.line(surf, (0,0,0), (rect.centerx, rect.y+14),(rect.centerx, rect.bottom-10),1)
        elif cid=="asker":
            # kamuflaj noktaları
            import random
            rnd=random.Random(hash(cid)%100)
            for _ in range(4):
                x=rnd.randint(rect.x+4, rect.right-8); y=rnd.randint(rect.y+8, rect.bottom-6)
                pygame.draw.circle(surf, (60,90,40), (x,y), 3)
            # cep
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+6, rect.centery-2, 10, 8), width=1, border_radius=2)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.right-16, rect.centery-2, 10, 8), width=1, border_radius=2)
        elif cid=="noel_baba":
            # kürk yakası
            pygame.draw.rect(surf, (255,255,255), pygame.Rect(rect.x+2, rect.y+6, rect.width-4, 8), border_radius=4)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+2, rect.y+6, rect.width-4, 8), width=1, border_radius=4)
            # kemer
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+4, rect.centery+2, rect.width-8, 6))
            pygame.draw.rect(surf, (255,215,0), pygame.Rect(rect.centerx-8, rect.centery+1, 16, 8), border_radius=2)
        elif cid=="balon":
            # balon karakteri - noktalı kıyafet
            for x in [rect.x+8, rect.centerx, rect.right-8]:
                for y in [rect.y+18, rect.y+28]:
                    pygame.draw.circle(surf, (255,255,255), (x,y), 2)
        elif cid=="cop_adam":
            # yama
            pygame.draw.rect(surf, (90,90,90), pygame.Rect(rect.x+6, rect.y+16, 10, 7), border_radius=2)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+6, rect.y+16, 10, 7), width=1, border_radius=2)
            pygame.draw.line(surf, (0,0,0), (rect.x+6, rect.y+19),(rect.x+16, rect.y+19),1)
            pygame.draw.line(surf, (0,0,0), (rect.x+11, rect.y+16),(rect.x+11, rect.y+23),1)
        elif cid=="soytari":
            # palyaço yakası
            for dx in [-8,0,8]:
                pygame.draw.circle(surf, (255,255,255), (rect.centerx+dx, rect.y+14), 5)
                pygame.draw.circle(surf, (0,0,0), (rect.centerx+dx, rect.y+14), 5,1)
                pygame.draw.circle(surf, (255,40,40), (rect.centerx+dx, rect.y+14), 2)
            pygame.draw.circle(surf, (255,40,40), (rect.centerx, rect.centery+6), 4)
        elif cid=="ayi":
            # kürk göbek
            pygame.draw.ellipse(surf, (90,60,40), pygame.Rect(rect.x+6, rect.y+12, rect.width-12, 18))
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(rect.x+6, rect.y+12, rect.width-12, 18),1)
            pygame.draw.circle(surf, (60,40,20), (rect.centerx-6, rect.y+20), 2)
            pygame.draw.circle(surf, (60,40,20), (rect.centerx+6, rect.y+20), 2)
        elif cid=="tavuk":
            # tüyler
            for x in [rect.x+6, rect.centerx, rect.right-8]:
                pygame.draw.ellipse(surf, (255,255,255), pygame.Rect(x-4, rect.y+10, 8, 12))
                pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(x-4, rect.y+10, 8, 12),1)
            pygame.draw.circle(surf, (255,200,40), (rect.centerx, rect.centery+4), 3)
        elif cid=="robot":
            # metal panel
            pygame.draw.rect(surf, (120,130,140), pygame.Rect(rect.x+4, rect.y+10, rect.width-8, 16), border_radius=3)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+4, rect.y+10, rect.width-8, 16), width=1, border_radius=3)
            for x in [rect.x+10, rect.centerx, rect.right-10]:
                gfx.draw_glow(surf, (x, rect.y+18), 6, (80,220,255), 22)
                pygame.draw.circle(surf, (80,220,255), (x, rect.y+18), 2)
        elif cid=="iskelet":
            # kaburga
            for y in [rect.y+14, rect.y+22, rect.y+30]:
                pygame.draw.line(surf, (200,200,200), (rect.x+8, y), (rect.right-8, y), 2)
                pygame.draw.line(surf, (0,0,0), (rect.x+8, y), (rect.right-8, y), 1)
            pygame.draw.circle(surf, (60,60,60), (rect.centerx, rect.centery+8), 3)
        elif cid=="korsan":
            # çapraz kemer + kafatası
            pygame.draw.line(surf, (90,40,20), (rect.x+4, rect.y+12), (rect.right-4, rect.bottom-10), 4)
            pygame.draw.line(surf, (0,0,0), (rect.x+4, rect.y+12), (rect.right-4, rect.bottom-10), 1)
            pygame.draw.circle(surf, (240,240,230), (rect.centerx+6, rect.centery-2), 5)
            pygame.draw.circle(surf, (0,0,0), (rect.centerx+6, rect.centery-2), 5,1)
        elif cid=="gotik_kiz":
            # dantel
            pygame.draw.rect(surf, (40,10,30), pygame.Rect(rect.x+4, rect.y+12, rect.width-8, 6), border_radius=3)
            pygame.draw.circle(surf, (180,80,160), (rect.centerx, rect.centery+6), 3)
            pygame.draw.line(surf, (0,0,0), (rect.centerx, rect.y+18),(rect.centerx, rect.bottom-8),1)
        elif cid=="gotik_erkek":
            # uzun palto
            pygame.draw.rect(surf, (20,20,35), pygame.Rect(rect.x+6, rect.y+12, rect.width-12, rect.height-14), border_radius=4)
            pygame.draw.line(surf, (80,40,80), (rect.centerx, rect.y+14),(rect.centerx, rect.bottom-6),2)
            for y in [rect.y+22, rect.y+32]:
                pygame.draw.circle(surf, (140,80,180), (rect.centerx, y), 2)

    def _draw_hair(self, surf, cx, cy, r, cid, col):
        if cid=="cop_adam":
            # dağınık saç
            pygame.draw.arc(surf, (70,50,30), (cx-r+2, cy-r, r*2-4, r+8), 0, 3.14, 4)
            for dx in [-7,-3,3,7]:
                pygame.draw.line(surf, (70,50,30), (cx+dx, cy-r+2),(cx+dx+2, cy-r-2),2)
        elif cid=="madame":
            # topuz
            pygame.draw.circle(surf, (50,30,10), (cx, cy-r+2), 9)
            pygame.draw.circle(surf, (90,60,30), (cx, cy-r+2), 6)
        elif cid=="soylu":
            # düzgün saç
            pygame.draw.arc(surf, (40,20,10), (cx-r+1, cy-r+1, r*2-2, r+6), 0, 3.14, 6)
        elif cid=="ninja":
            # başlık - siyah kapşon
            pygame.draw.circle(surf, (20,20,20), (cx, cy), r)
            pygame.draw.circle(surf, (0,0,0), (cx, cy), r,2)
            # sadece gözler görünsün - ten yok, maske zaten çizildi
            pygame.draw.rect(surf, (20,20,20), pygame.Rect(cx-r, cy-2, r*2, r+6))
        elif cid=="sihirbaz":
            # uzun saç
            pygame.draw.arc(surf, (200,200,220), (cx-r, cy-r+4, r*2, r+10), 0, 3.14, 5)
        elif cid=="noel_baba":
            # sakal
            pygame.draw.ellipse(surf, (255,255,255), pygame.Rect(cx-10, cy+4, 20, 12))
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(cx-10, cy+4, 20, 12),1)
            # bıyık
            pygame.draw.ellipse(surf, (255,255,255), pygame.Rect(cx-8, cy+1, 16, 6))
        elif cid in ("kadin","erkek"):
            hair_col = (80,40,20) if cid=="kadin" else (30,20,10)
            pygame.draw.arc(surf, hair_col, (cx-r+2, cy-r, r*2-4, r+8), 0, 3.14, 5)
            if cid=="kadin":
                # uzun saç yanlarda
                pygame.draw.ellipse(surf, hair_col, pygame.Rect(cx-r-2, cy-4, 8, 18))
                pygame.draw.ellipse(surf, hair_col, pygame.Rect(cx+r-6, cy-4, 8, 18))
        elif cid=="asker":
            # kısa kesim
            pygame.draw.arc(surf, (60,40,20), (cx-r+2, cy-r, r*2-4, 8), 0, 3.14, 4)
            pygame.draw.rect(surf, (60,40,20), pygame.Rect(cx-r+2, cy-r+2, r*2-4, 6))
        elif cid=="soytari":
            # renkli peruk
            pygame.draw.circle(surf, (200,30,30), (cx-8, cy-r+4), 6)
            pygame.draw.circle(surf, (30,160,30), (cx+8, cy-r+4), 6)
            pygame.draw.circle(surf, (255,215,0), (cx, cy-r+1), 7)
            pygame.draw.circle(surf, (0,0,0), (cx, cy-r+1), 7,1)
        elif cid=="ayi":
            # kulaklar
            pygame.draw.circle(surf, (90,60,40), (cx-10, cy-r+6), 6)
            pygame.draw.circle(surf, (90,60,40), (cx+10, cy-r+6), 6)
            pygame.draw.circle(surf, (60,40,20), (cx-10, cy-r+6), 3)
            pygame.draw.circle(surf, (60,40,20), (cx+10, cy-r+6), 3)
            pygame.draw.arc(surf, (90,60,40), (cx-r+2, cy-r+2, r*2-4, r+6), 0, 3.14, 5)
        elif cid=="tavuk":
            # ibik
            pygame.draw.polygon(surf, (200,30,30), [(cx, cy-r-4),(cx-7, cy-r+6),(cx+7, cy-r+6)])
            pygame.draw.polygon(surf, (0,0,0), [(cx, cy-r-4),(cx-7, cy-r+6),(cx+7, cy-r+6)],1)
            for dx in [-5,5]:
                pygame.draw.circle(surf, (255,230,100), (cx+dx, cy-r+8), 3)
        elif cid=="robot":
            # anten
            pygame.draw.rect(surf, (120,130,140), pygame.Rect(cx-6, cy-r-2, 12, 6), border_radius=2)
            pygame.draw.line(surf, (80,80,80), (cx, cy-r-2), (cx, cy-r-10), 2)
            pygame.draw.circle(surf, (255,40,40), (cx, cy-r-12), 4)
            gfx.draw_glow(surf, (cx, cy-r-12), 8, (255,40,40), 30)
        elif cid=="iskelet":
            # kafatası çizgileri
            pygame.draw.arc(surf, (180,180,180), (cx-r+3, cy-r+2, r*2-6, r+4), 0, 3.14, 2)
            for dx in [-4,4]:
                pygame.draw.circle(surf, (40,40,40), (cx+dx, cy), 2)
            pygame.draw.line(surf, (60,60,60), (cx-6, cy+6), (cx+6, cy+6),1)
        elif cid=="korsan":
            # bandana + yama
            pygame.draw.rect(surf, (160,30,30), pygame.Rect(cx-r+1, cy-r, r*2-2, 8), border_radius=3)
            pygame.draw.circle(surf, (0,0,0), (cx+4, cy), 5,1)
            pygame.draw.line(surf, (0,0,0), (cx+2, cy-3),(cx+6, cy+3),2)
            pygame.draw.line(surf, (0,0,0), (cx+6, cy-3),(cx+2, cy+3),2)
        elif cid in ("gotik_kiz","gotik_erkek"):
            hair_col = (20,10,20) if cid=="gotik_kiz" else (10,10,16)
            pygame.draw.arc(surf, hair_col, (cx-r+1, cy-r, r*2-2, r+8), 0, 3.14, 6)
            if cid=="gotik_kiz":
                pygame.draw.ellipse(surf, hair_col, pygame.Rect(cx-r-1, cy-2, 8, 20))
                pygame.draw.ellipse(surf, hair_col, pygame.Rect(cx+r-7, cy-2, 8, 20))
            else:
                for dx in [-6,0,6]:
                    pygame.draw.line(surf, hair_col, (cx+dx, cy-r+2),(cx+dx, cy-r-4),2)

    def _draw_hat(self, surf, x, y, hat_id):
        colors={"hat1":(200,30,30),"hat2":(30,30,200),"hat3":(30,150,30),"hat4":(255,215,0),
                "hat5":(120,40,160),"hat6":(40,160,160),"hat7":(200,120,30),"hat8":(90,90,90),"hat9":(30,90,160),"hat10":(160,30,90)}
        hc=colors.get(hat_id,(100,100,100))
        # hash'den ton üret fallback için
        if hat_id not in colors:
            hv = hash(hat_id) % 360
            import colorsys
            r,g,b = colorsys.hsv_to_rgb(hv/360, 0.65, 0.85)
            hc = (int(r*255), int(g*255), int(b*255))
        if hat_id=="hat1": # klasik
            pygame.draw.ellipse(surf, hc, pygame.Rect(x, y, 28, 12))
            pygame.draw.rect(surf, hc, pygame.Rect(x+4, y-8, 20, 10), border_radius=3)
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(x, y, 28, 12),1)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(x+4, y-8, 20, 10), width=1, border_radius=3)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(x+4, y-2, 20, 3))
        elif hat_id=="hat2": # silindir
            pygame.draw.rect(surf, (20,20,20), pygame.Rect(x+2, y-14, 24, 18), border_radius=2)
            pygame.draw.ellipse(surf, (20,20,20), pygame.Rect(x, y+2, 28, 6))
            pygame.draw.rect(surf, (200,30,30), pygame.Rect(x+2, y-2, 24, 3))
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(x+2, y-14, 24, 18), width=1, border_radius=2)
        elif hat_id=="hat3": # kovboy
            pygame.draw.ellipse(surf, (139,90,43), pygame.Rect(x-2, y, 32, 9))
            pygame.draw.rect(surf, (139,90,43), pygame.Rect(x+5, y-10, 18, 12), border_radius=4)
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(x-2, y, 32, 9),1)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(x+5, y-10, 18, 12), width=1, border_radius=4)
        elif hat_id=="hat4": # taç
            points=[(x+2,y+8),(x+7,y-6),(x+14,y+2),(x+21,y-6),(x+26,y+8)]
            pygame.draw.polygon(surf, (255,215,0), points)
            pygame.draw.polygon(surf, (0,0,0), points,2)
            for px in [7,14,21]:
                pygame.draw.circle(surf, (255,80,80), (x+px, y-2), 2)
                pygame.draw.circle(surf, (255,255,255), (x+px-1, y-3), 1)
        else: # hat5-10 generic premium
            # kask / bere tarzı
            pygame.draw.ellipse(surf, hc, pygame.Rect(x, y, 28, 12))
            pygame.draw.rect(surf, hc, pygame.Rect(x+4, y-10, 20, 12), border_radius=5)
            pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(x, y, 28, 12),1)
            pygame.draw.rect(surf, (0,0,0), pygame.Rect(x+4, y-10, 20, 12), width=1, border_radius=5)
            # şerit
            pygame.draw.rect(surf, tuple(min(255,c+40) for c in hc), pygame.Rect(x+4, y-2, 20, 3))
            # tepe detayı
            pygame.draw.circle(surf, (255,255,255), (x+14, y-6), 2)

    def _draw_glasses(self, surf, cx, cy, gid):
        # genişletildi 1-10 — her gözlük farklı renk
        palette={"glasses1":(20,20,20),"glasses2":(255,215,0),"glasses3":(0,200,200),
                 "glasses4":(200,30,30),"glasses5":(40,160,40),"glasses6":(120,40,160),
                 "glasses7":(255,120,0),"glasses8":(90,90,90),"glasses9":(30,110,180),"glasses10":(160,30,110)}
        gc=palette.get(gid,(30,30,30))
        if gid not in palette:
            import colorsys
            hv=hash(gid)%360
            r,g,b=colorsys.hsv_to_rgb(hv/360,0.7,0.9)
            gc=(int(r*255),int(g*255),int(b*255))
        # lens with reflection
        pygame.draw.ellipse(surf, gc, pygame.Rect(cx-11, cy-4, 10, 8))
        pygame.draw.ellipse(surf, gc, pygame.Rect(cx+1, cy-4, 10, 8))
        pygame.draw.line(surf, gc, (cx-1, cy), (cx+1, cy),2)
        # cam içi - opaque (önceki 90 alpha display'de hataydı)
        pygame.draw.ellipse(surf, (120,190,255), pygame.Rect(cx-9, cy-2, 6, 4))
        pygame.draw.ellipse(surf, (120,190,255), pygame.Rect(cx+3, cy-2, 6, 4))
        pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(cx-11, cy-4, 10, 8),1)
        pygame.draw.ellipse(surf, (0,0,0), pygame.Rect(cx+1, cy-4, 10, 8),1)
        # sap
        pygame.draw.line(surf, (0,0,0), (cx-11, cy-1),(cx-14, cy-2),1)
        pygame.draw.line(surf, (0,0,0), (cx+11, cy-1),(cx+14, cy-2),1)

    def _draw_bag(self, surf, rect, bag_id):
        cols={"bag1":(139,90,43),"bag2":(70,70,70),"bag3":(180,40,60),
              "bag4":(40,100,160),"bag5":(160,40,90),"bag6":(60,140,80),"bag7":(120,90,40),
              "bag8":(90,40,140),"bag9":(180,120,40),"bag10":(40,40,40)}
        col=cols.get(bag_id,(100,70,30))
        if bag_id not in cols:
            import colorsys
            hv=hash(bag_id)%360
            r,g,b=colorsys.hsv_to_rgb(hv/360,0.6,0.8)
            col=(int(r*255),int(g*255),int(b*255))
        pygame.draw.rect(surf, col, rect, border_radius=3)
        # highlight
        pygame.draw.rect(surf, tuple(min(255,c+30) for c in col), pygame.Rect(rect.x+2, rect.y+2, rect.width-4, 4), border_radius=2)
        pygame.draw.rect(surf, (0,0,0), rect, width=1, border_radius=3)
        # cep ve fermuar
        pygame.draw.rect(surf, (0,0,0), pygame.Rect(rect.x+2, rect.y+5, rect.width-4, 2))
        pygame.draw.circle(surf, (255,215,0), (rect.centerx, rect.y+9), 2)
        if bag_id=="bag3":
            pygame.draw.circle(surf, (255,80,80), (rect.centerx+3, rect.y+5), 2)

    def _draw_cane(self, surf, rect, cane_id, state):
        cols={"cane1":(139,90,43),"cane2":(180,180,180),"cane3":(255,215,0),
              "cane4":(200,50,50),"cane5":(50,150,50),"cane6":(80,60,160),"cane7":(200,150,40),
              "cane8":(60,60,60),"cane9":(30,120,180),"cane10":(160,40,120)}
        col=cols.get(cane_id,(110,80,40))
        if cane_id not in cols:
            import colorsys
            hv=hash(cane_id)%360
            r,g,b=colorsys.hsv_to_rgb(hv/360,0.7,0.85)
            col=(int(r*255),int(g*255),int(b*255))
        # gövde
        pygame.draw.rect(surf, col, rect, border_radius=3)
        # sargı
        for y in range(rect.y+6, rect.bottom-6, 5):
            pygame.draw.line(surf, (0,0,0), (rect.x, y),(rect.x+rect.width, y),1)
        pygame.draw.rect(surf, (0,0,0), rect, width=1, border_radius=3)
        # kafa
        head_c = (rect.centerx, rect.y)
        if cane_id=="cane1":
            pygame.draw.circle(surf, col, head_c, 7)
            pygame.draw.circle(surf, (90,60,30), head_c, 7,1)
            pygame.draw.circle(surf, (0,0,0), head_c, 7,1)
        elif cane_id=="cane2":
            # kristal
            pygame.draw.polygon(surf, (120,200,255), [(head_c[0],head_c[1]-8),(head_c[0]-6,head_c[1]+2),(head_c[0]+6,head_c[1]+2)])
            pygame.draw.polygon(surf, (0,0,0), [(head_c[0],head_c[1]-8),(head_c[0]-6,head_c[1]+2),(head_c[0]+6,head_c[1]+2)],1)
            gfx.draw_glow(surf, head_c, 14, (120,200,255), 40)
        elif cane_id=="cane3":
            pygame.draw.circle(surf, (255,215,0), head_c, 7)
            pygame.draw.circle(surf, (255,255,255), (head_c[0]-2, head_c[1]-2), 2)
            pygame.draw.circle(surf, (0,0,0), head_c, 7,1)
            gfx.draw_glow(surf, head_c, 16, (255,215,0), 45)
