import pygame
import random
import math

class Particle:
    def __init__(self, x, y, vx, vy, life, color, size, kind="default"):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.kind = kind
        self.rotation = random.uniform(0, 6.28)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        # kind-based gravity
        if self.kind in ("dust","smoke"):
            self.vy += 180 * dt
            self.vx *= (1 - 0.6*dt)
        elif self.kind == "spark":
            self.vy += 520 * dt
            self.vx *= (1 - 0.5*dt)
        elif self.kind == "snow":
            self.vy += 60 * dt
            self.x += math.sin(pygame.time.get_ticks()*0.002 + self.y*0.01)*0.6
        else:
            self.vy += 900 * dt
            self.vx *= (1 - 0.8*dt)
        self.life -= dt
        self.rotation += dt * 3

    def draw(self, surf, cam_y):
        if self.life <= 0:
            return
        sy = int(round(self.y - cam_y))
        if sy < -24 or sy > 724:
            return
        t = self.life / max(0.001,self.max_life)
        alpha = int(255 * t)
        alpha = max(0, min(255, alpha))
        sx = int(round(self.x))
        if self.kind == "spark":
            # bright core + glow - alpha via temp surface (display has no alpha)
            sz = max(1, int(self.size * (0.55 + 0.45*t)))
            col = self.color[:3] if len(self.color) == 4 else self.color
            s = pygame.Surface((sz*2+4, sz*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, int(alpha*0.9)), (sz+2, sz+2), sz)
            pygame.draw.circle(s, (255,255,255, int(alpha*0.85)), (sz+2, sz+2), max(1,int(sz*0.5)))
            surf.blit(s, (sx - sz -2, sy - sz -2), special_flags=pygame.BLEND_RGBA_ADD)
            # trail
            if t>0.5:
                ts = max(1,int(sz*0.6))
                ts_surf = pygame.Surface((ts*2+2, ts*2+2), pygame.SRCALPHA)
                pygame.draw.circle(ts_surf, (*col, int(alpha*0.35)), (ts+1, ts+1), ts)
                surf.blit(ts_surf, (int(sx - self.vx*0.015)-ts-1, int(sy - self.vy*0.015)-ts-1), special_flags=pygame.BLEND_RGBA_ADD)
        elif self.kind == "smoke":
            # soft puff
            a = int(alpha*0.55)
            sz = int(self.size * (0.7 + 0.6*(1-t)))
            s = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, a), (sz, sz), sz)
            pygame.draw.circle(s, (255,255,255, int(a*0.25)), (sz-2, sz-2), max(1,sz//2))
            surf.blit(s, (sx - sz, sy - sz))
        elif self.kind == "dust":
            a = int(alpha*0.62)
            sz = max(1, int(self.size * t))
            s = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, a), (sz, sz), sz)
            surf.blit(s, (sx - sz, sy - sz))
        elif self.kind == "snow":
            a = int(alpha*0.88)
            sz = self.size
            col = self.color[:3] if len(self.color) == 4 else self.color
            s = pygame.Surface((sz*2+4, sz*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, a), (sz+2, sz+2), sz)
            pygame.draw.circle(s, (255,255,255, a), (sz+2, sz+2), max(1,sz-1))
            surf.blit(s, (sx - sz -2, sy - sz -2), special_flags=pygame.BLEND_RGBA_ADD)
        elif self.kind == "coin_ring":
            # expanding ring - via temp surface
            r = int(self.size * (1 + (1-t)*1.8))
            a = int(alpha*0.28*t)
            col = self.color[:3] if len(self.color) == 4 else self.color
            # need surface big enough to hold ring with thickness
            sz = r+4
            s = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, a), (sz, sz), r, 2)
            surf.blit(s, (sx - sz, sy - sz))
        else:
            s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
            col = (*self.color, alpha)
            pygame.draw.circle(s, col, (self.size, self.size), self.size)
            # tiny highlight
            pygame.draw.circle(s, (255,255,255, int(alpha*0.45)), (self.size-1, self.size-1), max(1,self.size//3))
            surf.blit(s, (sx - self.size, sy - self.size))

class ParticleSystem:
    def __init__(self):
        self.particles = []
        self.atmos_particles = []
        self._atmos_timer = 0
        self._pool = []  # simple reuse pool for performance

    def _alloc(self, x, y, vx, vy, life, color, size, kind):
        # limit check before alloc
        if len(self.particles) > 220:
            return
        self.particles.append(Particle(x, y, vx, vy, life, color, size, kind))

    def emit_coin(self, x, y, value=1):
        is_rare = value >= 3
        colors = [(255,215,0),(255,238,110),(255,180,0)] if is_rare else [(255,215,0),(255,180,0)]
        count = 9 if value >= 5 else 6 if is_rare else 4
        for _ in range(count):
            angle = random.uniform(-1.15, 1.15) - math.pi/2
            speed = random.uniform(88, 205 if is_rare else 175)
            vx = math.cos(angle)*speed
            vy = math.sin(angle)*speed
            self._alloc(x, y, vx, vy, random.uniform(0.38,0.72), random.choice(colors), random.randint(3,5), "spark")
        for _ in range(3 + (1 if is_rare else 0)):
            self._alloc(x, y, random.uniform(-42,42), random.uniform(-120,-38), 0.42, (255,255,180), 2, "spark")
        # coin ring
        self._alloc(x, y, 0, 0, 0.36, (255,215,0), 10, "coin_ring")
        if is_rare:
            self._alloc(x, y, 0, 0, 0.40, (255,238,110), 16, "coin_ring")

    def emit_jump(self, x, y):
        for _ in range(6):
            self._alloc(x+random.randint(-7,7), y, random.uniform(-66,66), random.uniform(-44,8), 0.34, (205,205,200), 3, "dust")
        self._alloc(x, y, 0, -20, 0.28, (255,255,255), 8, "coin_ring")

    def emit_land(self, x, y):
        # dust puff + tiny stones
        for _ in range(8):
            self._alloc(x+random.randint(-14,14), y, random.uniform(-95,95), random.uniform(-84,-12), 0.38, (184,180,164), random.randint(2,4), "dust")
        for _ in range(3):
            self._alloc(x+random.randint(-10,10), y, random.uniform(-50,50), random.uniform(-60,-10), 0.42, (110,90,70), 2, "default")

    def emit_death(self, x, y):
        # dramatic burst — not gore, just energy + smoke
        for _ in range(24):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(90, 280)
            vx = math.cos(angle)*speed
            vy = math.sin(angle)*speed - 70
            col = random.choice([(236,40,40),(255,96,96),(130,24,24),(255,162,162),(80,80,80)])
            kind = "spark" if col[0]>180 else "smoke" if col==(80,80,80) else "default"
            self._alloc(x, y, vx, vy, random.uniform(0.62,1.05), col, random.randint(3,6), kind)
        # shock ring
        self._alloc(x, y, 0, 0, 0.48, (255,90,90), 18, "coin_ring")
        self._alloc(x, y, 0, 0, 0.42, (255,255,255), 12, "coin_ring")

    def emit_levelup(self, x, y):
        for _ in range(16):
            angle = random.uniform(-2.4, 2.4) - math.pi/2
            speed = random.uniform(95, 215)
            vx = math.cos(angle)*speed
            vy = math.sin(angle)*speed
            col = random.choice([(86,210,255),(255,215,0),(186,120,255),(255,120,180)])
            self._alloc(x, y, vx, vy, 0.72, col, 4, "spark")
        self._alloc(x, y, 0, -30, 0.52, (255,215,0), 22, "coin_ring")

    def emit_wind(self, x, y, n=2):
        for _ in range(n):
            self._alloc(x, y, random.uniform(-30,30), random.uniform(-40,-10), random.uniform(0.45,0.85), (255,255,255), random.randint(2,3), "dust")

    def emit_snow_burst(self, x, y, n=3):
        for _ in range(n):
            self._alloc(x+random.randint(-20,20), y, random.uniform(-22,22), random.uniform(-10,20), random.uniform(0.6,1.0), (230,244,255), random.randint(2,3), "snow")

    def update(self, dt, cam_y=None, level_name=None):
        for p in self.particles:
            p.update(dt)
        alive = [p for p in self.particles if p.life > 0]
        if len(alive) > 220:
            alive = alive[-220:]
        self.particles = alive

        # atmosfer — biome-aware, çok hafif, performans dostu
        self._atmos_timer += dt
        if cam_y is not None and self._atmos_timer > 0.07:
            self._atmos_timer = 0
            if level_name == "HAVA":
                if random.random() < 0.55 and len(self.atmos_particles) < 24:
                    self.atmos_particles.append({
                        "x": random.randint(-24, 924),
                        "y": cam_y + random.randint(-80, 700),
                        "vx": random.uniform(-18, 18),
                        "vy": random.uniform(14, 34),
                        "life": random.uniform(6, 12),
                        "size": random.randint(2,4),
                        "alpha": random.randint(42,110),
                        "color": (255,255,255),
                        "kind": "dust",
                    })
            elif level_name == "MAGMA":
                if random.random() < 0.46 and len(self.atmos_particles) < 20:
                    self.atmos_particles.append({
                        "x": random.randint(40, 860),
                        "y": cam_y + 700 + random.randint(0,110),
                        "vx": random.uniform(-16,16),
                        "vy": random.uniform(-56,-20),
                        "life": random.uniform(4,8),
                        "size": random.randint(2,3),
                        "alpha": random.randint(90,170),
                        "color": random.choice([(255,84,0),(255,126,32),(255,204,100)]),
                        "kind": "spark",
                    })
            elif level_name == "BUZUL":
                if random.random() < 0.62 and len(self.atmos_particles) < 28:
                    self.atmos_particles.append({
                        "x": random.randint(0, 900),
                        "y": cam_y - random.randint(0,100),
                        "vx": random.uniform(-24,24),
                        "vy": random.uniform(32, 72),
                        "life": random.uniform(5,10),
                        "size": random.randint(2,3),
                        "alpha": random.randint(84,164),
                        "color": (226,242,255),
                        "kind": "snow",
                    })
            elif level_name == "KAYA":
                if random.random() < 0.32 and len(self.atmos_particles) < 14:
                    self.atmos_particles.append({
                        "x": random.randint(20, 880),
                        "y": cam_y + random.randint(-60, 760),
                        "vx": random.uniform(-12,12),
                        "vy": random.uniform(10,22),
                        "life": random.uniform(5,9),
                        "size": 2,
                        "alpha": random.randint(30,70),
                        "color": (160,160,170),
                        "kind": "dust",
                    })
            elif level_name == "TOPRAK":
                if random.random() < 0.38 and len(self.atmos_particles) < 16:
                    self.atmos_particles.append({
                        "x": random.randint(30, 870),
                        "y": cam_y + random.randint(-40, 740),
                        "vx": random.uniform(-10,10),
                        "vy": random.uniform(8,20),
                        "life": random.uniform(5,8),
                        "size": 2,
                        "alpha": random.randint(32,72),
                        "color": (210,180,140),
                        "kind": "dust",
                    })
            elif level_name == "DERIN":
                if random.random() < 0.36 and len(self.atmos_particles) < 18:
                    self.atmos_particles.append({
                        "x": random.randint(40, 860),
                        "y": cam_y + random.randint(-40, 760),
                        "vx": random.uniform(-14,14),
                        "vy": random.uniform(-18,-6),
                        "life": random.uniform(6,11),
                        "size": 2,
                        "alpha": random.randint(48,96),
                        "color": (90,140,255),
                        "kind": "dust",
                    })
            elif level_name == "FINAL":
                if random.random() < 0.42 and len(self.atmos_particles) < 20:
                    self.atmos_particles.append({
                        "x": random.randint(40, 860),
                        "y": cam_y + random.randint(-40, 760),
                        "vx": random.uniform(-12,12),
                        "vy": random.uniform(-14,14),
                        "life": random.uniform(6,11),
                        "size": 2,
                        "alpha": random.randint(60,120),
                        "color": random.choice([(255,215,0),(180,140,255),(255,255,180)]),
                        "kind": "spark",
                    })
        for a in self.atmos_particles:
            a["x"] += a["vx"]*dt
            a["y"] += a["vy"]*dt
            a["life"] -= dt
            # fade by kind
            if a["kind"] == "spark":
                a["alpha"] = max(0, a["alpha"] - 18*dt)
            else:
                a["alpha"] = max(0, a["alpha"] - 9*dt)
        self.atmos_particles = [a for a in self.atmos_particles if a["life"]>0 and a["y"] < cam_y+820 and a["y"]>cam_y-220 and a["alpha"]>4]

    def draw(self, surf, cam_y):
        for a in self.atmos_particles:
            sy = int(round(a["y"] - cam_y))
            if 0 <= sy <= 700:
                col = a.get("color", (255,255,255))
                alpha = int(a["alpha"])
                sz = a["size"]
                if a["kind"] == "snow":
                    # six-point star for snow - via temp surface
                    s = pygame.Surface((sz*2+6, sz*2+6), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*col, alpha), (sz+3, sz+3), sz)
                    pygame.draw.line(s, (*col, int(alpha*0.8)), (sz+1, sz+3), (sz+5, sz+3), 1)
                    pygame.draw.line(s, (*col, int(alpha*0.8)), (sz+3, sz+1), (sz+3, sz+5), 1)
                    surf.blit(s, (int(a["x"]) - sz -3, sy - sz -3))
                elif a["kind"] == "spark":
                    s = pygame.Surface((sz*2+4, sz*2+4), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*col, alpha), (sz+2, sz+2), sz)
                    pygame.draw.circle(s, (255,255,255, int(alpha*0.55)), (sz+2, sz+2), max(1,sz-1))
                    surf.blit(s, (int(a["x"]) - sz -2, sy - sz -2), special_flags=pygame.BLEND_RGBA_ADD)
                else:
                    s = pygame.Surface((sz*2, sz*2), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*col, alpha), (sz, sz), sz)
                    surf.blit(s, (int(a["x"] - sz), sy - sz))
        for p in self.particles:
            p.draw(surf, cam_y)
