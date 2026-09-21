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
        """Bir sonraki engelin gap ortasına doğru hedef seç — dünya koordinatında, geniş görüş."""
        # 600->950 geniş görüş, 300 filtresi kaldırıldı; dünya y'sine göre
        view_ahead = 950
        best = None
        best_dist = 1e9
        for o in obstacles:
            if o.y < self.y + 18:
                continue
            if o.y > self.y + view_ahead:
                continue
            d = o.y - self.y
            if 0 <= d < best_dist:
                best_dist = d
                best = o
        # Hata ekle — sadece best bulunduğunda hata uygula, hareketsiz kalma durumu hariç
        if best is not None and random.random() < self.mistake_chance:
            return random.choice([-1, 0, 1])
        if best is None:
            # Önünde geçerli engel yok: tamamen hareketsiz kalma yerine
            # en yakın gap'e doğru hafif yönelim dene (rastgele değil, veriye dayalı)
            # Uzakta kalan ilk engeli bul
            fallback = None
            fb_dist = 1e9
            for o in obstacles:
                if o.y <= self.y:
                    continue
                d = o.y - self.y
                if d < fb_dist:
                    fb_dist = d
                    fallback = o
            if fallback is not None:
                y = fallback.y
                left_max = 0
                right_min = config.SCREEN_WIDTH
                for oo in obstacles:
                    if abs(oo.y - y) < 2:
                        if oo.x == 0:
                            left_max = max(left_max, oo.right)
                        else:
                            right_min = min(right_min, oo.left)
                gap_center = (left_max + right_min) / 2
                bot_center = self.x + self.w/2
                if gap_center < bot_center - 22:
                    return -1
                elif gap_center > bot_center + 22:
                    return 1
            return 0
        # Mevcut en yakın gap + sonraki 1-2 gap'i birlikte değerlendir
        # Önce y'ye göre gruplanmış gap merkezlerini topla (950px içinde)
        # step_deco (h=6) gibi küçük dekor engelleri gap sayılmaz
        gaps = []  # (y, gap_center)
        seen_y = set()
        for o in obstacles:
            if o.height < 12:  # step_deco filtresi
                continue
            if o.y < self.y + 18 or o.y > self.y + view_ahead:
                continue
            yk = int(round(o.y / 10) * 10)  # 10px gruplama, 6px kaymaları birleştir
            if yk in seen_y:
                continue
            seen_y.add(yk)
            left_max = 0
            right_min = config.SCREEN_WIDTH
            for oo in obstacles:
                if oo.height < 12:
                    continue
                if abs(oo.y - o.y) < 10:
                    if oo.x == 0:
                        left_max = max(left_max, oo.right)
                    else:
                        right_min = min(right_min, oo.left)
            if right_min <= left_max:
                continue
            # gap genişliği en az 90 olmalı
            if right_min - left_max < 90:
                continue
            gaps.append((o.y, (left_max + right_min) / 2))
        gaps.sort(key=lambda t: t[0])
        if not gaps:
            return 0
        cur_y, cur_center = gaps[0]
        bot_center = self.x + self.w/2
        # Mevcut gap'e göre yön
        if cur_center < bot_center - 22:
            cur_dir = -1
        elif cur_center > bot_center + 22:
            cur_dir = 1
        else:
            cur_dir = 0
        # Bot zaten mevcut gap merkezinde ve on_ground ise, bir sonraki gap'e bak
        if cur_dir == 0 and self.on_ground and len(gaps) >= 2:
            nxt_y, nxt_center = gaps[1]
            if nxt_center < bot_center - 18:
                cur_dir = -1
            elif nxt_center > bot_center + 18:
                cur_dir = 1
            else:
                if len(gaps) >= 3:
                    _, nxt2_center = gaps[2]
                    if nxt2_center < bot_center - 18:
                        cur_dir = -1
                    elif nxt2_center > bot_center + 18:
                        cur_dir = 1
                    else:
                        cur_dir = 0
                else:
                    cur_dir = 0
            # hata payı (veriye dayalı karar bozulmadan hafif)
            if random.random() < self.mistake_chance:
                return random.choice([-1, 0, 1])
            return cur_dir
        if random.random() < self.mistake_chance:
            return random.choice([-1, 0, 1])
        return cur_dir

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
        # ÇANTA — vücudun ARKASINDA (arka taraf, bakış yönünün karşısı)
        if equipped:
            bx_off, by_off = offsets["bag"]
            bag = equipped.get("bag")
            if bag:
                side = -1 if self.facing >= 0 else 1
                bag_x = body_rect.x - 6 if side < 0 else body_rect.right - 6
                br = pygame.Rect(bag_x, body_rect.y + 10 + by_off, 12, 16)
                _P._draw_bag(None, surf, br, bag)
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
        # KOZMETİKLER — ana oyuncuyla aynı hizalama
        if equipped:
            ox, oy = offsets["hat"]
            hat = equipped.get("hat")
            if hat:
                _P._draw_hat(None, surf, head_cx-head_r+ox, head_cy-head_r-3+oy, hat)
            gx, gy = offsets["glasses"]
            glasses = equipped.get("glasses")
            if glasses:
                _P._draw_glasses(None, surf, head_cx+gx, head_cy+gy, glasses)
            cx_off, cy_off = offsets["cane"]
            cane = equipped.get("cane")
            if cane:
                cane_x = sx - 7 + cx_off
                if self.facing >= 0:
                    cane_x = 2*(sx + self.w//2) - (cane_x + 6)
                cr = pygame.Rect(cane_x, int(by+7+cy_off), 6, bh-3)
                _P._draw_cane(None, surf, cr, cane, self.state)
