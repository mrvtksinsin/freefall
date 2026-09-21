import pygame
import random
import math
import config
import graphics as gfx

def _safe_randint(rnd, a, b):
    """randint crash'ını önle: a>b ise swap et, eşit ise a döndür."""
    if a > b:
        a, b = b, a
    try:
        return rnd.randint(a, b)
    except ValueError:
        return a

class Coin:
    def __init__(self, x, y, value=1):
        self.x=x; self.y=y; self.value=value; self.collected=False; self.r=11; self.bob=random.random()*6.28; self.spin=0
    def rect(self): return pygame.Rect(int(self.x-self.r),int(self.y-self.r),self.r*2,self.r*2)
    def update(self, dt): self.spin+=dt*6

class World:
    def __init__(self):
        self.obstacles=[]; self.obstacle_meta=[]; self.coins=[]; self.decor=[]
        self.next_gen_y=config.SAFE_START_DISTANCE
        self.rng=random.Random(42)
        self.generated_sections=0
        self.last_gap_start=None

    def reset(self):
        self.obstacles.clear(); self.obstacle_meta.clear(); self.coins.clear(); self.decor.clear()
        self.next_gen_y=config.SAFE_START_DISTANCE
        self.rng=random.Random(random.randint(0,100000)); self.generated_sections=0
        self.last_gap_start=None

    def ensure_generated(self, cam_y, keep_cam_y=None):
        # keep_cam_y: culling için en gerideki kamera (VS_BOT'ta bot gerideyse korumak için)
        # Normalde keep_cam_y == cam_y
        target_y=cam_y+config.SCREEN_HEIGHT+config.WORLD_GEN_AHEAD
        while self.next_gen_y<target_y:
            self.generate_layer(self.next_gen_y)
            spacing=self._current_spacing()
            self.next_gen_y+=spacing; self.generated_sections+=1
        keep = keep_cam_y if keep_cam_y is not None else cam_y
        limit=keep-config.WORLD_CLEAN_BEHIND
        new_obs=[]; new_meta=[]
        for r,m in zip(self.obstacles,self.obstacle_meta):
            if r.bottom>limit: new_obs.append(r); new_meta.append(m)
        self.obstacles=new_obs; self.obstacle_meta=new_meta
        self.coins=[c for c in self.coins if not c.collected and c.y>limit-200]
        self.decor=[d for d in self.decor if d["y"]>limit-300]

    def _current_spacing(self):
        cur_dist_m=self.next_gen_y/config.PIXELS_PER_METER
        factor=min(1.0, cur_dist_m/300.0)
        spacing=config.DIFFICULTY_SPACING_START-factor*(config.DIFFICULTY_SPACING_START-config.DIFFICULTY_SPACING_MIN)
        spacing+=self.rng.randint(-12,12)
        return max(config.DIFFICULTY_SPACING_MIN-20, spacing)

    def _current_gap(self):
        cur_dist_m=self.next_gen_y/config.PIXELS_PER_METER
        shrink=int(cur_dist_m/100*config.DIFFICULTY_GAP_SHRINK_PER_100M)
        gap_min=max(92, config.GAP_MIN-shrink); gap_max=max(124, config.GAP_MAX-shrink)
        if gap_max<gap_min: gap_max=gap_min+18
        return self.rng.randint(gap_min,gap_max)

    def _current_level_name(self):
        # mesafe + 75 engelde bir katman ilerlemesi (uzatıldı)
        px=self.next_gen_y; name=config.LEVELS[0]["name"]
        for e in config.LEVELS:
            if px>=e["distance"]: name=e["name"]
        # 75 engelde bir seviye atlat (seviyeyle senkron - uzatıldı)
        try:
            count_level = min(len(config.LEVELS), self.generated_sections // 75 + 1)
            count_name = config.LEVELS[count_level-1]["name"]
            # iki hesaptan büyük olanı al (distance vs count)
            dist_idx = next((i for i,e in enumerate(config.LEVELS) if e["name"]==name), 0)
            count_idx = count_level - 1
            if count_idx > dist_idx:
                name = count_name
        except:
            pass
        return name

    def generate_layer(self,y):
        # her 75 engelde bir nefes boşluğu: engeli atla, sadece coin bırak (uzatıldı)
        if self.generated_sections>0 and self.generated_sections % 75 == 0:
            # geniş coin koridoru, engel yok
            gap=self._current_gap()+40
            gap_start=(config.SCREEN_WIDTH-gap)//2 + self.rng.randint(-20,20)
            gap_start=max(config.WALL_THICKNESS+8, min(config.SCREEN_WIDTH-config.WALL_THICKNESS-gap-8, gap_start))
            c=Coin(gap_start+gap//2, y+20, self.rng.choice([1,5]))
            self.coins.append(c)
            # hafif dekor
            if self.rng.random()<0.5:
                self.decor.append({"x":self.rng.randint(100,800),"y":y,"kind":"crystal"})
            return
        gap=self._current_gap(); lvl_name=self._current_level_name()
        if y<config.SAFE_START_DISTANCE+500:
            gap_start=(config.SCREEN_WIDTH-gap)//2+self.rng.randint(-40,40)
            self._add_obstacle_pair(y,gap_start,gap,kind="flat")
            c=Coin(gap_start+gap//2,y+30+self.rng.randint(8,18),self.rng.choice([1,1,5])); self.coins.append(c); return
        patterns=["flat","flat","flat","stepped","notch"]
        cur_dist=self.next_gen_y/config.PIXELS_PER_METER
        if cur_dist>40: patterns+=["zigzag","narrow"]
        if cur_dist>80: patterns+=["stepped","zigzag"]
        kind=self.rng.choice(patterns)
        min_x=config.WALL_THICKNESS+10; max_x=config.SCREEN_WIDTH-config.WALL_THICKNESS-gap-10
        if max_x<=min_x: gap_start=(config.SCREEN_WIDTH-gap)//2
        else:
            if self.last_gap_start is not None:
                max_drift = 210 if kind in ("zigzag","narrow") else 190
                lo=max(min_x,self.last_gap_start-max_drift); hi=min(max_x,self.last_gap_start+max_drift)
                if lo<hi:
                    if self.rng.random()<0.88:
                        gap_start=self.rng.randint(lo,hi)
                    else:
                        lo2=max(min_x,self.last_gap_start-max_drift-40); hi2=min(max_x,self.last_gap_start+max_drift+40)
                        gap_start=self.rng.randint(lo2,hi2)
                else:
                    gap_start=self.rng.randint(min_x,max_x)
            else:
                gap_start=self.rng.randint(min_x,max_x)
        self.last_gap_start=gap_start
        if kind=="narrow": gap=max(92,gap-22)
        self._add_obstacle_pair(y,gap_start,gap,kind=kind,lvl=lvl_name)
        gap_center=gap_start+gap//2; coin_y=y+28+(10 if kind=="stepped" else 0)
        val=self.rng.choice([1,1,1,5,5,10]) if cur_dist>60 else self.rng.choice([1,1,1,5,5])
        # riskli rota daha fazla coin - gap içinde kalacak şekilde clamp
        base_coin_x=gap_center
        if val>=5 and self.rng.random()<0.35:
            base_coin_x=gap_center+self.rng.choice([-1,1])*self.rng.randint(18,36)
        else:
            base_coin_x=gap_center+self.rng.randint(-12,12)
        # gap sınırları içinde tut (duvar payı 12)
        coin_x = max(gap_start+12, min(gap_start+gap-12, base_coin_x))
        # çok değerli coin için yay dizilim
        if val==10:
            # 10 coin -> 3'lü yay, hepsi gap içinde kalmalı
            for i,dx in enumerate([-18,0,18]):
                cx = max(gap_start+12, min(gap_start+gap-12, coin_x+dx))
                cc=Coin(cx, coin_y+ abs(dx)//2, 3 if i!=1 else 4)
                # toplam 10 olsun: 3+4+3
                if self.rng.random()<0.9: self.coins.append(cc)
        elif self.rng.random()<0.78:
            c=Coin(coin_x,coin_y,val if val!=10 else 5); self.coins.append(c)
            if self.rng.random()<0.22:
                c2=Coin(coin_x+self.rng.randint(-28,28),coin_y+18,1); self.coins.append(c2)
        if self.rng.random()<0.28:
            self.decor.append({"x":self.rng.randint(40,860),"y":y+self.rng.randint(-40,40),"kind":self.rng.choice(["stone","crack","moss","crystal"])})

    def _add_obstacle_pair(self,y,gap_start,gap,kind="flat",lvl=None):
        h=self.rng.randint(config.OBSTACLE_MIN_HEIGHT,config.OBSTACLE_MAX_HEIGHT)
        if kind=="stepped":
            h2=h+self.rng.randint(6,14); left_w=gap_start; right_x=gap_start+gap
            left_rect=pygame.Rect(0,int(y),int(left_w),int(h)); right_rect=pygame.Rect(int(right_x),int(y),int(config.SCREEN_WIDTH-right_x),int(h))
            self.obstacles.append(left_rect); self.obstacle_meta.append({"kind":"stepped","h2":h2})
            self.obstacles.append(right_rect); self.obstacle_meta.append({"kind":"stepped","h2":h2})
            if self.rng.random()<0.5:
                step_w=self.rng.randint(18,42)
                if left_w>step_w+20:
                    step=pygame.Rect(left_w-step_w,int(y)-6,step_w,6); self.obstacles.append(step); self.obstacle_meta.append({"kind":"step_deco"})
                if config.SCREEN_WIDTH-right_x>step_w+20:
                    step2=pygame.Rect(right_x,int(y)-6,step_w,6); self.obstacles.append(step2); self.obstacle_meta.append({"kind":"step_deco"})
            return
        elif kind=="notch":
            left_rect=pygame.Rect(0,int(y),int(gap_start),int(h)); right_rect=pygame.Rect(int(gap_start+gap),int(y),int(config.SCREEN_WIDTH-(gap_start+gap)),int(h))
            self.obstacles.append(left_rect); self.obstacle_meta.append({"kind":"notch"})
            self.obstacles.append(right_rect); self.obstacle_meta.append({"kind":"notch"}); return
        elif kind=="zigzag":
            h=max(18,h-6); left_rect=pygame.Rect(0,int(y),int(gap_start),int(h)); right_rect=pygame.Rect(int(gap_start+gap),int(y),int(config.SCREEN_WIDTH-(gap_start+gap)),int(h))
            self.obstacles.append(left_rect); self.obstacle_meta.append({"kind":"zigzag"})
            self.obstacles.append(right_rect); self.obstacle_meta.append({"kind":"zigzag"}); return
        else:
            left_rect=pygame.Rect(0,int(y),int(gap_start),int(h)); right_rect=pygame.Rect(int(gap_start+gap),int(y),int(config.SCREEN_WIDTH-(gap_start+gap)),int(h))
            self.obstacles.append(left_rect); self.obstacle_meta.append({"kind":kind})
            self.obstacles.append(right_rect); self.obstacle_meta.append({"kind":kind})

    def check_coin_collection(self,player_rect):
        gained=0
        for c in self.coins:
            if not c.collected and player_rect.colliderect(c.rect()): c.collected=True; gained+=c.value
        return gained
    def update_coins(self,dt):
        for c in self.coins:
            if not c.collected: c.update(dt)

    # ---------- DRAW — PROFESYONEL GÖRSEL PIPELINE (parallax 3 katman, lighting, bevel) ----------
    def draw(self, surf, cam_y, level_info):
        lvl=level_info["name"]
        # 1) ARKA PLAN — biome-specific gradient + atmospheric perspective + light beams
        if lvl=="HAVA":
            top=(135,206,235); bottom=(210,235,255)
            gfx.vertical_gradient(surf, top, bottom)
            # sunlight god-rays
            gfx.light_beam(surf, 140, 120, alpha=10)
            gfx.light_beam(surf, 760, 90, alpha=8)
            self._draw_parallax_hava(surf, cam_y)
        elif lvl=="TOPRAK":
            top=(118,78,42); bottom=(68,44,20)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_toprak(surf, cam_y)
        elif lvl=="KAYA":
            top=(62,65,72); bottom=(28,28,34)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_kaya(surf, cam_y)
        elif lvl=="MAGMA":
            top=(50,16,16); bottom=(18,6,8)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_magma(surf, cam_y)
        elif lvl=="BUZUL":
            top=(205,232,255); bottom=(172,202,232)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_buzul(surf, cam_y)
        elif lvl=="DERIN":
            top=(10,18,36); bottom=(6,10,22)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_derin(surf, cam_y)
        elif lvl=="KATMAN KAYASI":
            top=(72,62,56); bottom=(52,44,40)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_katman_kayasi(surf, cam_y)
        elif lvl=="KANALIZASYON":
            top=(54,68,50); bottom=(36,48,34)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_kanalizasyon(surf, cam_y)
        elif lvl=="CAFE":
            top=(228,198,156); bottom=(196,164,122)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_cafe(surf, cam_y)
        elif lvl=="OFIS":
            top=(232,236,242); bottom=(210,216,224)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_ofis(surf, cam_y)
        elif lvl=="BACKROOMS":
            top=(212,188,128); bottom=(188,164,108)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_backrooms(surf, cam_y)
        elif lvl=="GUC SANTRALI":
            top=(78,80,86); bottom=(58,60,66)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_guc_santrali(surf, cam_y)
        elif lvl=="MUZE":
            top=(238,232,218); bottom=(216,210,196)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_muze(surf, cam_y)
        elif lvl=="SINIF":
            top=(188,218,188); bottom=(158,188,158)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_sinif(surf, cam_y)
        elif lvl=="FABRIKA":
            top=(60,60,64); bottom=(42,42,46)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_fabrika(surf, cam_y)
        elif lvl=="POLIGAN":
            top=(88,68,128); bottom=(68,48,108)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_poligan(surf, cam_y)
        elif lvl=="ORMAN":
            top=(38,80,50); bottom=(28,60,38)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_orman(surf, cam_y)
        elif lvl=="SARAY":
            top=(228,208,168); bottom=(208,188,148)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_saray(surf, cam_y)
        elif lvl=="KOY":
            top=(158,188,128); bottom=(132,162,102)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_koy(surf, cam_y)
        elif lvl=="SEHIR":
            top=(80,88,104); bottom=(60,68,84)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_sehir(surf, cam_y)
        elif lvl=="TOKYO":
            top=(28,28,48); bottom=(18,18,32)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_tokyo(surf, cam_y)
        elif lvl=="FRANSA":
            top=(188,208,238); bottom=(162,182,212)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_fransa(surf, cam_y)
        elif lvl=="FINAL":
            top=(14,14,34); bottom=(8,8,18)
            gfx.vertical_gradient(surf, top, bottom)
            self._draw_parallax_final(surf, cam_y)
        else:
            surf.fill(level_info["bg"])

        # 2) DERİNLİK ÇİZGİLERİ — faint horizon lines, parallax hissi
        start=int(cam_y//260)
        for i in range(-1, config.SCREEN_HEIGHT//260+2):
            wy=(start+i)*260; sy=int(wy-cam_y)
            alpha = 18 if lvl!="DERIN" else 12
            if lvl=="MAGMA": alpha = 14
            line_surf=pygame.Surface((config.SCREEN_WIDTH,1), pygame.SRCALPHA)
            line_surf.fill((0,0,0, alpha))
            surf.blit(line_surf, (0,sy))

        # 3) DUVARLAR — bevel + grain + iç gölge
        self._draw_walls(surf, cam_y, level_info)

        # 4) DEKOR — culling ile
        for d in self.decor:
            sy=int(round(d["y"]-cam_y))
            if -30 <= sy <= config.SCREEN_HEIGHT+30:
                self._draw_decor(surf, d["x"], sy, d["kind"], lvl)

        # 5) OBSTACLES — bevel + texture + soft shadow + glow per biome
        obs_color=level_info["obstacle"]; accent=level_info["accent"]
        for r, meta in zip(self.obstacles, self.obstacle_meta):
            sy=int(round(r.y - cam_y))
            if sy<-90 or sy>config.SCREEN_HEIGHT+90: continue
            self._draw_obstacle(surf, pygame.Rect(r.x, sy, r.width, r.height), meta, obs_color, accent, lvl, r)

        # 6) COINS — spin + bob + glow
        for c in self.coins:
            if c.collected: continue
            sy=int(round(c.y - cam_y))
            if sy<-36 or sy>config.SCREEN_HEIGHT+36: continue
            self._draw_coin(surf, int(round(c.x)), sy, c)

        # 7) POST LIGHTING — biome mood
        if lvl=="MAGMA":
            gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT+30), 240, (255,70,20), 24)
            # subtle flicker overlay
            flick = pygame.Surface((config.SCREEN_WIDTH,120), pygame.SRCALPHA)
            flick.fill((255,90,20, 10 + int(6*math.sin(pygame.time.get_ticks()*0.004))))
            surf.blit(flick,(0, config.SCREEN_HEIGHT-120))
        elif lvl=="DERIN":
            vig=pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
            vig.fill((0,0,16, 32))
            surf.blit(vig,(0,0))
            gfx.draw_vignette(surf, intensity=0.28)
        elif lvl=="BUZUL":
            vig=pygame.Surface((config.SCREEN_WIDTH, 130), pygame.SRCALPHA)
            vig.fill((200,232,255, 22))
            surf.blit(vig,(0,0))
            gfx.draw_vignette(surf, intensity=0.12)
        elif lvl=="HAVA":
            gfx.draw_vignette(surf, intensity=0.10)
        elif lvl=="KAYA":
            gfx.draw_vignette(surf, intensity=0.18)
        elif lvl=="FINAL":
            # FINAL — sinematik gold + dark glow
            gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2), 260, (255,215,0), 18)
            gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT+60), 200, (90,70,140), 14)
            gfx.draw_vignette(surf, intensity=0.32)
            # subtle star field
            for i in range(6):
                sx2 = (200 + i*130 + int(cam_y*0.03)) % 900
                sy2 = (40 + i*90) % 700
                pygame.draw.circle(surf, (255,255,255, 80), (sx2, sy2), 1)
                gfx.draw_glow(surf, (sx2, sy2), 8, (255,215,0), 12)
        # extra: horizon fog at bottom for depth
        if lvl not in ("DERIN","MAGMA"):
            fog = pygame.Surface((config.SCREEN_WIDTH, 90), pygame.SRCALPHA)
            for i in range(90):
                a = int(18*(1-i/90))
                pygame.draw.line(fog, (255,255,255,a), (0,i), (config.SCREEN_WIDTH,i))
            # very subtle
            surf.blit(fog, (0, config.SCREEN_HEIGHT-90))

    def _draw_parallax_hava(self, surf, cam_y):
        # LAYER 1: uzak dağ silüetleri (0.07x) — atmospheric perspective, 3 tone
        offset=int(cam_y*0.07)%420
        for i in range(-1,4):
            y = i*320 - offset
            # far mountains — muted, hazy
            pts=[(0,y+130),(110,y+44),(250,y+92),(400,y+34),(590,y+112),(860,y+62),(900,y+70),(900,y+170),(0,y+170)]
            pygame.draw.polygon(surf, (78,98,128, 70), pts)
            pygame.draw.polygon(surf, (96,116,148, 85), pts, 1)
            # closer ridge — warmer
            pts2=[(0,y+150),(180,y+68),(360,y+104),(560,y+48),(760,y+126),(900,y+88),(900,y+170),(0,y+170)]
            pygame.draw.polygon(surf, (92,112,142, 55), pts2)
        # LAYER 2: orta bulut katmanı (0.20x) — detailed, with shadow
        offset2=int(cam_y*0.20)%560
        for i in range(5):
            y = i*190 - offset2 + 20
            x = 90 + (i*170)%720
            scale = 0.85 + (i%3)*0.18
            gfx.draw_cloud(surf, x, y, scale=scale, alpha=112)
            if i%2==0:
                gfx.draw_cloud(surf, 700 - x%280, y+70, scale=scale*0.72, alpha=72)
            # distant birds (tiny V)
            bx = (x + int(cam_y*0.04)) % 900
            pygame.draw.lines(surf, (40,40,50,80), False, [(bx-6,y-8),(bx,y-12),(bx+6,y-8)], 1)
        # LAYER 3: ön rüzgar çizgileri + sun haze (0.42x)
        offset3=int(cam_y*0.42)%420
        for i in range(7):
            y = i*110 - offset3
            x = (i*130 + int(cam_y*0.06))%config.SCREEN_WIDTH
            pygame.draw.line(surf, (255,255,255, 48), (x, y+20), (x+44, y+18), 1)
            if i%3==0:
                gfx.draw_glow(surf, (x+22, y+12), 18, (255,255,220), 14)

    def _draw_parallax_toprak(self, surf, cam_y):
        # LAYER 1: derin toprak gölgesi (0.09x)
        offset=int(cam_y*0.09)%420
        for i in range(6):
            y = i*150 - offset
            x = 70 + (i*190)%760
            # roots — branching
            pygame.draw.line(surf, (52,30,12), (x, y), (x-14, y+38), 4)
            pygame.draw.line(surf, (78,46,22), (x+26, y+8), (x+12, y+42), 3)
            pygame.draw.line(surf, (92,62,30), (x-6, y+18), (x+8, y+28), 2)
            gfx.draw_glow(surf, (x-7, y+22), 10, (110,70,30), 18)
        # LAYER 2: taş taneleri (0.22x)
        offset2=int(cam_y*0.24)%520
        for i in range(7):
            y=i*140 - offset2
            cx = 120 + (i*118)%660
            pygame.draw.circle(surf, (96,66,30), (cx, y+28), 8)
            pygame.draw.circle(surf, (118,84,42), (cx, y+28), 5)
            pygame.draw.circle(surf, (80,54,26), (cx, y+28), 8, 1)
            pygame.draw.circle(surf, (255,255,255,42), (cx-2, y+26), 2)
        # LAYER 3: toz motes (0.38x)
        offset3=int(cam_y*0.38)%600
        for i in range(8):
            y=i*120 - offset3
            x=(i*160 + 40)%900
            pygame.draw.circle(surf, (255,220,160, 38), (x, y+14), 1)
            pygame.draw.circle(surf, (255,200,140, 28), (x+18, y+36), 1)

    def _draw_parallax_kaya(self, surf, cam_y):
        # LAYER 1: uzak kristal damarları (0.09x)
        offset=int(cam_y*0.09)%520
        for i in range(5):
            y=i*220 - offset
            for j in range(3):
                x= 90 + j*260 + (i*48)%140
                pygame.draw.polygon(surf, (118,118,152), [(x,y+18),(x-8,y+38),(x+8,y+38)])
                pygame.draw.polygon(surf, (70,70,85), [(x,y+18),(x-8,y+38),(x+8,y+38)], 1)
                gfx.draw_glow(surf, (x, y+30), 12, (150,180,255), 20)
                gfx.draw_glow(surf, (x, y+34), 6, (200,220,255), 28)
        # LAYER 2: stratum lines (0.24x)
        offset2=int(cam_y*0.24)%420
        for i in range(6):
            y=i*160 - offset2
            pygame.draw.line(surf, (44,44,50), (20, y+12), (880, y+14), 2)
            pygame.draw.line(surf, (68,68,78, 60), (40, y+8), (860, y+10), 1)
        # LAYER 3: floating dust + cracks (0.38x)
        offset3=int(cam_y*0.38)%600
        for i in range(6):
            y=i*150 - offset3
            x = (100 + i*140 + int(cam_y*0.02))%900
            pygame.draw.line(surf, (0,0,0, 55), (x, y+20), (x+18, y+28), 1)
            pygame.draw.circle(surf, (88,88,96, 44), (x+9, y+24), 1)

    def _draw_parallax_magma(self, surf, cam_y):
        # LAYER 1: magma veins deep (0.10x) — glowing cracks
        offset=int(cam_y*0.10)%520
        for i in range(6):
            y=i*180 - offset
            x= 60 + (i*150)%820
            pygame.draw.line(surf, (118,28,12), (x, y), (x+20, y+54), 5)
            pygame.draw.line(surf, (255,70,18), (x+2, y+4), (x+18, y+50), 2)
            gfx.draw_glow(surf, (x+10, y+26), 20, (255,70,20), 28)
            gfx.draw_glow(surf, (x+10, y+26), 8, (255,180,80), 44)
        # LAYER 2: smoke plumes (0.26x) — semi-volumetric
        offset2=int(cam_y*0.26)%640
        for i in range(5):
            y=i*200 - offset2
            x= 180 + (i*190)%640
            # puff stack
            for k, (dx,dr,a) in enumerate([(0,16,62),(10,12,44),( -8,10,36)]):
                pygame.draw.circle(surf, (64,32,22, a), (x+dx, y+16+k*8), dr)
                pygame.draw.circle(surf, (92,48,28, a-12), (x+dx+2, y+14+k*8), dr-4)
        # LAYER 3: rising sparks (0.42x)
        offset3=int(cam_y*0.42)%700
        for i in range(7):
            y=i*140 - offset3
            x=(i*150 + int(cam_y*0.08))%900
            gfx.draw_glow(surf, (x, y+20), 6, (255,150,40), 32)
            pygame.draw.circle(surf, (255,220,120), (x, y+20), 1)
        # bottom lava glow — soft ramp
        glow=pygame.Surface((config.SCREEN_WIDTH,150), pygame.SRCALPHA)
        for i in range(150):
            a=int(38*(1 - i/150)**1.2)
            pygame.draw.line(glow, (255,92,20, a), (0, 150-i),(config.SCREEN_WIDTH,150-i))
        surf.blit(glow,(0, config.SCREEN_HEIGHT-150), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_parallax_buzul(self, surf, cam_y):
        # LAYER 1: snow drift (0.10x)
        offset=int(cam_y*0.10)%520
        for i in range(6):
            y=i*180 - offset
            x= 80 + (i*160)%780
            pygame.draw.circle(surf, (255,255,255, 88), (x, y+18), 4)
            pygame.draw.circle(surf, (220,238,255, 68), (x, y+18), 2)
            pygame.draw.circle(surf, (255,255,255, 62), (x+20, y+38), 3)
            # ice glint
            pygame.draw.line(surf, (255,255,255,74), (x-4,y+16),(x+4,y+18),1)
        # LAYER 2: falling snow + clouds (0.22x)
        offset2=int(cam_y*0.22)%640
        for i in range(5):
            y=i*200 - offset2
            x= 400 + (i*200)%520
            gfx.draw_cloud(surf, x, y+20, scale=0.62, alpha=62)
            for k in range(2):
                sx = (x + k*90 + int(cam_y*0.05))%900
                sy = y + 10 + k*40
                pygame.draw.circle(surf, (255,255,255, 90), (sx, sy), 2)
                gfx.draw_glow(surf, (sx,sy), 6, (200,230,255), 22)
        # LAYER 3: wind streaks (0.40x)
        offset3=int(cam_y*0.40)%600
        for i in range(8):
            y=i*110 - offset3
            x=(i*120+60)%900
            pygame.draw.line(surf, (255,255,255, 42), (x, y+16), (x+36, y+14), 1)

    def _draw_parallax_derin(self, surf, cam_y):
        # LAYER 1: abyss lights (0.07x)
        offset=int(cam_y*0.07)%520
        for i in range(7):
            y=i*170 - offset
            x= 100 + (i*130)%720
            gfx.draw_glow(surf, (x, y+30), 22, (80,140,255), 16)
            pygame.draw.circle(surf, (42,72,148), (x, y+30), 4)
            pygame.draw.circle(surf, (120,180,255, 90), (x, y+30), 1)
            # faint tendrils
            pygame.draw.line(surf, (30,50,100, 55), (x, y+10), (x+12, y+44), 1)
        # LAYER 2: grid + depth fog (0.20x)
        offset2=int(cam_y*0.20)%420
        for i in range(6):
            y=i*150 - offset2
            pygame.draw.line(surf, (20,40,78), (0,y), (config.SCREEN_WIDTH,y),1)
            pygame.draw.line(surf, (30,60,110, 42), (0,y+1), (config.SCREEN_WIDTH,y+1),1)
        # LAYER 3: drifting motes (0.36x)
        offset3=int(cam_y*0.36)%700
        for i in range(7):
            y=i*130 - offset3
            x=(90 + i*120 + int(cam_y*0.04))%900
            gfx.draw_glow(surf, (x, y+18), 8, (80,140,255), 20)
            pygame.draw.circle(surf, (80,140,255, 70), (x, y+18), 1)

    def _draw_parallax_katman_kayasi(self, surf, cam_y):
        # Katman Kayası — sıkı katman çizgileri, taş damarları
        offset=int(cam_y*0.08)%520
        for i in range(6):
            y=i*160 - offset
            x= 80 + (i*140)%760
            pygame.draw.line(surf, (90,80,70), (x-30, y+20), (x+30, y+22), 3)
            pygame.draw.line(surf, (110,100,90), (x-20, y+14), (x+20, y+16), 2)
            gfx.draw_glow(surf, (x, y+18), 10, (160,140,120), 18)
        offset2=int(cam_y*0.24)%420
        for i in range(5):
            y=i*150 - offset2
            pygame.draw.line(surf, (78,68,58), (20, y+10), (880, y+12), 2)
        offset3=int(cam_y*0.38)%600
        for i in range(6):
            y=i*120 - offset3
            x=(90 + i*140)%900
            pygame.draw.circle(surf, (120,110,100), (x, y+16), 2)
            pygame.draw.circle(surf, (80,70,60), (x, y+16), 2, 1)

    def _draw_parallax_kanalizasyon(self, surf, cam_y):
        # Kanalizasyon — borular, damlalar, yeşil ışık
        offset=int(cam_y*0.09)%520
        for i in range(5):
            y=i*170 - offset
            x= 100 + (i*160)%700
            # boru
            pygame.draw.rect(surf, (60,70,55), pygame.Rect(x-40, y+12, 80, 14), border_radius=7)
            pygame.draw.rect(surf, (40,50,35), pygame.Rect(x-40, y+12, 80, 14), width=2, border_radius=7)
            pygame.draw.circle(surf, (90,110,80), (x+34, y+19), 3)
            gfx.draw_glow(surf, (x, y+19), 12, (120,180,80), 14)
        offset2=int(cam_y*0.25)%420
        for i in range(6):
            y=i*140 - offset2
            x=(120 + i*130)%900
            # damla
            pygame.draw.circle(surf, (90,140,70, 60), (x, y+16), 2)
            pygame.draw.line(surf, (110,160,90), (x, y+8), (x, y+16), 1)
        offset3=int(cam_y*0.39)%600
        for i in range(7):
            y=i*110 - offset3
            x=(80 + i*120)%900
            gfx.draw_glow(surf, (x, y+18), 8, (140,210,90), 16)

    def _draw_parallax_cafe(self, surf, cam_y):
        # Cafe — sıcak ahşap, bardaklar, buhar
        offset=int(cam_y*0.08)%520
        for i in range(5):
            y=i*160 - offset
            # raf
            pygame.draw.rect(surf, (160,120,80), pygame.Rect(40, y+18, 820, 10), border_radius=5)
            pygame.draw.rect(surf, (110,80,50), pygame.Rect(40, y+18, 820, 10), width=1, border_radius=5)
            for j in range(3):
                x= 120 + j*260
                # fincan
                pygame.draw.rect(surf, (245,240,230), pygame.Rect(x-14, y+4, 28, 16), border_radius=4)
                pygame.draw.rect(surf, (80,60,40), pygame.Rect(x-14, y+4, 28, 16), width=1, border_radius=4)
                # buhar
                pygame.draw.line(surf, (255,255,255, 50), (x-6, y+2), (x-8, y-6), 1)
                pygame.draw.line(surf, (255,255,255, 40), (x+6, y+2), (x+8, y-6), 1)
        offset2=int(cam_y*0.26)%420
        for i in range(5):
            y=i*150 - offset2
            pygame.draw.circle(surf, (255,220,180, 30), (200 + i*150, y+20), 18)
        offset3=int(cam_y*0.40)%600
        for i in range(6):
            y=i*120 - offset3
            x=(100 + i*140)%900
            gfx.draw_glow(surf, (x, y+16), 12, (255,200,140), 12)

    def _draw_parallax_ofis(self, surf, cam_y):
        # Ofis — floresan, grid tavan, monitör ışığı
        offset=int(cam_y*0.07)%520
        for i in range(5):
            y=i*160 - offset
            # floresan ışık
            pygame.draw.rect(surf, (230,235,240), pygame.Rect(60, y+12, 780, 6), border_radius=3)
            pygame.draw.rect(surf, (180,185,190), pygame.Rect(60, y+12, 780, 6), width=1, border_radius=3)
            gfx.draw_glow(surf, (450, y+15), 40, (200,220,255), 14)
        offset2=int(cam_y*0.24)%420
        for i in range(5):
            y=i*150 - offset2
            # monitör
            x= 120 + (i*180)%700
            pygame.draw.rect(surf, (30,35,40), pygame.Rect(x-30, y+8, 60, 36), border_radius=4)
            pygame.draw.rect(surf, (90,130,210), pygame.Rect(x-26, y+12, 52, 22))
            gfx.draw_glow(surf, (x, y+23), 16, (90,130,210), 18)
        offset3=int(cam_y*0.38)%600
        for i in range(6):
            y=i*110 - offset3
            x=(90 + i*140)%900
            pygame.draw.line(surf, (200,205,210, 40), (x, y+16), (x+20, y+16), 1)

    def _draw_parallax_backrooms(self, surf, cam_y):
        # Backrooms — sarı floresan, halı deseni
        offset=int(cam_y*0.07)%520
        for i in range(5):
            y=i*160 - offset
            pygame.draw.rect(surf, (220,200,140), pygame.Rect(50, y+14, 800, 8), border_radius=2)
            for x in range(80, 820, 120):
                pygame.draw.line(surf, (180,160,100), (x, y+14), (x, y+22), 1)
            gfx.draw_glow(surf, (450, y+18), 30, (255,240,160), 12)
        offset2=int(cam_y*0.24)%420
        for i in range(6):
            y=i*150 - offset2
            pygame.draw.circle(surf, (255,255,180, 20), (100 + i*140, y+20), 22)

    def _draw_parallax_guc_santrali(self, surf, cam_y):
        # Güç Santrali — borular, uyarı şeritleri
        offset=int(cam_y*0.08)%520
        for i in range(5):
            y=i*170 - offset
            x= 120 + (i*150)%700
            pygame.draw.rect(surf, (60,62,66), pygame.Rect(x-50, y+10, 100, 16), border_radius=4)
            for s in range(0, 100, 20):
                col = (255,220,0) if (s//20)%2==0 else (30,30,30)
                pygame.draw.rect(surf, col, pygame.Rect(x-50+s, y+10, 10, 16))
            gfx.draw_glow(surf, (x, y+18), 10, (255,220,0), 10)
        offset2=int(cam_y*0.26)%420
        for i in range(5):
            y=i*150 - offset2
            pygame.draw.circle(surf, (255,100,40, 30), (200 + i*160, y+22), 8)
            gfx.draw_glow(surf, (200+i*160, y+22), 14, (255,100,40), 18)

    def _draw_parallax_muze(self, surf, cam_y):
        # Müze — sütunlar, tablolar
        offset=int(cam_y*0.07)%520
        for i in range(4):
            y=i*180 - offset
            for x in [180, 450, 720]:
                pygame.draw.rect(surf, (200,195,180), pygame.Rect(x-18, y+8, 36, 48), border_radius=3)
                pygame.draw.rect(surf, (140,130,110), pygame.Rect(x-18, y+8, 36, 48), width=1, border_radius=3)
                pygame.draw.rect(surf, (80,60,40), pygame.Rect(x-12, y+14, 24, 18))
                pygame.draw.rect(surf, (180,160,120), pygame.Rect(x-12, y+14, 24, 18), width=1)
        offset2=int(cam_y*0.25)%420
        for i in range(5):
            y=i*150 - offset2
            gfx.draw_glow(surf, (450, y+20), 20, (255,230,160), 8)

    def _draw_parallax_sinif(self, surf, cam_y):
        # Sınıf — sıralar, tahta
        offset=int(cam_y*0.08)%520
        for i in range(5):
            y=i*160 - offset
            pygame.draw.rect(surf, (110,80,50), pygame.Rect(60, y+18, 780, 10), border_radius=3)
            for x in range(100, 800, 140):
                pygame.draw.rect(surf, (90,60,30), pygame.Rect(x-20, y+4, 40, 16), border_radius=2)
            # tahta
            pygame.draw.rect(surf, (40,70,40), pygame.Rect(300, y-20, 300, 28), border_radius=2)
            pygame.draw.rect(surf, (80,80,80), pygame.Rect(300, y-20, 300, 28), width=1, border_radius=2)
        offset2=int(cam_y*0.26)%420
        for i in range(4):
            y=i*150 - offset2
            pygame.draw.circle(surf, (255,255,255, 20), (150+i*180, y+18), 16)

    def _draw_parallax_fabrika(self, surf, cam_y):
        # Fabrika — dişliler, duman
        offset=int(cam_y*0.08)%520
        for i in range(5):
            y=i*170 - offset
            x= 140 + (i*160)%680
            # dişli
            pygame.draw.circle(surf, (70,70,76), (x, y+18), 18)
            pygame.draw.circle(surf, (50,50,56), (x, y+18), 10)
            for a in range(0, 360, 60):
                import math
                rad=math.radians(a + cam_y*0.05)
                pygame.draw.rect(surf, (70,70,76), pygame.Rect(int(x+math.cos(rad)*14-4), int(y+18+math.sin(rad)*14-4), 8, 8))
            gfx.draw_glow(surf, (x, y+18), 14, (255,100,40), 12)
        offset2=int(cam_y*0.26)%420
        for i in range(4):
            y=i*160 - offset2
            pygame.draw.circle(surf, (80,80,80, 40), (300 + i*180, y+12), 14)

    def _draw_parallax_poligan(self, surf, cam_y):
        # Poligan — low-poly dağlar
        offset=int(cam_y*0.07)%520
        for i in range(4):
            y=i*180 - offset
            pts=[(0,y+40),(180,y+12),(360,y+36),(520,y+8),(700,y+38),(900,y+16),(900,y+60),(0,y+60)]
            pygame.draw.polygon(surf, (100,70,140, 60), pts)
            pygame.draw.polygon(surf, (140,100,180), pts, 1)
            for x in [200,500,750]:
                gfx.draw_glow(surf, (x, y+24), 10, (255,80,180), 10)

    def _draw_parallax_orman(self, surf, cam_y):
        # Orman — ağaçlar, yaprak
        offset=int(cam_y*0.08)%520
        for i in range(5):
            y=i*160 - offset
            for x in [140, 360, 580, 780]:
                # gövde
                pygame.draw.rect(surf, (60,40,20), pygame.Rect(x-8, y+8, 16, 28))
                # yaprak
                pygame.draw.circle(surf, (40,100,50), (x, y+6), 22)
                pygame.draw.circle(surf, (60,130,70), (x, y+2), 14)
                gfx.draw_glow(surf, (x, y+6), 12, (120,200,80), 8)

    def _draw_parallax_saray(self, surf, cam_y):
        # Saray — sütun, altın
        offset=int(cam_y*0.07)%520
        for i in range(4):
            y=i*180 - offset
            for x in [200, 700]:
                pygame.draw.rect(surf, (200,180,140), pygame.Rect(x-14, y+6, 28, 52), border_radius=4)
                pygame.draw.rect(surf, (255,215,0), pygame.Rect(x-16, y+4, 32, 8), border_radius=2)
                gfx.draw_glow(surf, (x, y+10), 12, (255,215,0), 10)
        offset2=int(cam_y*0.25)%420
        for i in range(4):
            y=i*150 - offset2
            pygame.draw.circle(surf, (255,215,0, 20), (450, y+20), 28)

    def _draw_parallax_koy(self, surf, cam_y):
        # Köy — evler, saman
        offset=int(cam_y*0.08)%520
        for i in range(5):
            y=i*160 - offset
            for x in [180, 550]:
                # çatı
                pygame.draw.polygon(surf, (140,80,40), [(x-30,y+18),(x,y-6),(x+30,y+18)])
                pygame.draw.rect(surf, (200,180,140), pygame.Rect(x-24, y+18, 48, 22))
                pygame.draw.rect(surf, (0,0,0), pygame.Rect(x-24, y+18, 48, 22),1)
                # pencere
                pygame.draw.rect(surf, (255,230,140), pygame.Rect(x-8, y+24, 16, 12))
        offset2=int(cam_y*0.26)%420
        for i in range(4):
            y=i*150 - offset2
            gfx.draw_glow(surf, (180, y+30), 10, (255,200,100), 8)

    def _draw_parallax_sehir(self, surf, cam_y):
        # Şehir — gökdelen silueti
        offset=int(cam_y*0.07)%520
        for i in range(4):
            y=i*180 - offset
            for x, h in [(80,48),(180,62),(320,44),(500,58),(640,50),(780,60)]:
                pygame.draw.rect(surf, (50,60,78), pygame.Rect(x-18, y+60-h, 36, h))
                for wy in range(y+60-h+8, y+60, 12):
                    if (x+wy)%3==0:
                        pygame.draw.rect(surf, (255,220,100), pygame.Rect(x-10, wy, 8, 6))
                gfx.draw_glow(surf, (x, y+60-h), 8, (100,180,255), 6)

    def _draw_parallax_tokyo(self, surf, cam_y):
        # Tokyo — neon, tabelalar
        offset=int(cam_y*0.07)%520
        for i in range(5):
            y=i*160 - offset
            for x in [140, 360, 580, 780]:
                pygame.draw.rect(surf, (30,30,60), pygame.Rect(x-20, y+8, 40, 46))
                # neon
                col = (255,50,150) if x%2==0 else (50,200,255)
                pygame.draw.rect(surf, col, pygame.Rect(x-18, y+14, 36, 4))
                pygame.draw.rect(surf, col, pygame.Rect(x-18, y+22, 36, 4))
                gfx.draw_glow(surf, (x, y+18), 12, col, 16)
        offset2=int(cam_y*0.25)%420
        for i in range(6):
            y=i*140 - offset2
            pygame.draw.circle(surf, (255,80,150, 30), (100+i*140, y+20), 6)

    def _draw_parallax_fransa(self, surf, cam_y):
        # Fransa — Eyfel silueti, bulut
        offset=int(cam_y*0.07)%520
        for i in range(3):
            y=i*180 - offset
            x=450
            # kule
            pygame.draw.polygon(surf, (120,130,150), [(x, y+8),(x-18, y+52),(x+18, y+52)])
            pygame.draw.rect(surf, (120,130,150), pygame.Rect(x-6, y+52, 12, 12))
            gfx.draw_glow(surf, (x, y+20), 18, (255,200,200), 8)
            # bulut
            gfx.draw_cloud(surf, x-120, y+18, scale=0.6, alpha=60)
            gfx.draw_cloud(surf, x+120, y+22, scale=0.7, alpha=50)

    def _draw_parallax_final(self, surf, cam_y):
        # FINAL — karanlık void + altın ışık, yüzen kristaller, END yazısı için hazırlık
        offset=int(cam_y*0.06)%520
        for i in range(4):
            y=i*180 - offset
            x = 200 + (i*180)%600
            # yüzen kristal
            pygame.draw.polygon(surf, (90,70,140), [(x,y+14),(x-10,y+36),(x+10,y+36)])
            pygame.draw.polygon(surf, (140,110,200), [(x,y+14),(x-6,y+28),(x+6,y+28)])
            gfx.draw_glow(surf, (x, y+26), 18, (255,215,0), 22)
            gfx.draw_glow(surf, (x, y+26), 8, (180,140,255), 18)
            # alt halka
            pygame.draw.ellipse(surf, (255,215,0, 30), pygame.Rect(x-18, y+38, 36, 8))
        offset2=int(cam_y*0.22)%420
        for i in range(5):
            y=i*150 - offset2
            gfx.draw_glow(surf, (450, y+20), 26, (255,215,0), 10)
            pygame.draw.circle(surf, (255,255,255, 40), (450, y+20), 2)
        offset3=int(cam_y*0.38)%600
        for i in range(6):
            y=i*110 - offset3
            x=(90 + i*140 + int(cam_y*0.04))%900
            pygame.draw.circle(surf, (255,215,0, 50), (x, y+16), 2)
            gfx.draw_glow(surf, (x, y+16), 10, (255,215,0), 14)

    def _draw_walls(self, surf, cam_y, level_info):
        lvl=level_info["name"]
        wall_color=level_info["wall"]
        hi = tuple(min(255,c+36) for c in wall_color)
        lo = tuple(max(0,c-28) for c in wall_color)
        # SOL duvar — bevel + grain
        left_rect=pygame.Rect(0,0,config.WALL_THICKNESS, config.SCREEN_HEIGHT)
        pygame.draw.rect(surf, wall_color, left_rect)
        # grain
        gfx.noise_texture(surf, left_rect, alpha=9, color=(0,0,0))
        for y in range(0, config.SCREEN_HEIGHT, 18):
            off = (int(cam_y*0.5) + y) % 36
            pygame.draw.line(surf, (0,0,0,62), (3, y - off//3), (config.WALL_THICKNESS-5, y+7 - off//3), 1)
            if lvl=="KAYA":
                pygame.draw.circle(surf, (0,0,0,88), (9, y+5 - off//3), 1)
            elif lvl=="MAGMA":
                if y%36==0:
                    pygame.draw.line(surf, (255,90,20), (2, y), (config.WALL_THICKNESS-2, y), 2)
                    gfx.draw_glow(surf, (config.WALL_THICKNESS//2, y), 8, (255,70,20), 18)
            elif lvl=="BUZUL":
                pygame.draw.line(surf, (216,238,255,86), (3, y+5), (config.WALL_THICKNESS-6, y+5), 1)
            elif lvl=="TOPRAK":
                pygame.draw.line(surf, (60,36,16), (4, y+6 - off//3), (config.WALL_THICKNESS-6, y+8 - off//3), 1)
        # bevel highlights
        pygame.draw.line(surf, hi, (0,0), (config.WALL_THICKNESS,0), 2)
        pygame.draw.line(surf, hi, (0,0), (0, config.SCREEN_HEIGHT), 2)
        # SAĞ duvar — mirror
        right_rect=pygame.Rect(config.SCREEN_WIDTH-config.WALL_THICKNESS,0,config.WALL_THICKNESS,config.SCREEN_HEIGHT)
        pygame.draw.rect(surf, wall_color, right_rect)
        gfx.noise_texture(surf, right_rect, alpha=9, color=(0,0,0))
        for y in range(0, config.SCREEN_HEIGHT, 18):
            off=(int(cam_y*0.5)+y)%36
            pygame.draw.line(surf, (0,0,0,62), (config.SCREEN_WIDTH-config.WALL_THICKNESS+4, y+6 - off//3),(config.SCREEN_WIDTH-4, y - off//3),1)
        pygame.draw.line(surf, hi, (config.SCREEN_WIDTH-config.WALL_THICKNESS,0),(config.SCREEN_WIDTH,0),2)
        pygame.draw.line(surf, hi, (config.SCREEN_WIDTH-1,0),(config.SCREEN_WIDTH-1, config.SCREEN_HEIGHT),2)
        # iç gölge + ambient occlusion (8px)
        shadow_left=pygame.Surface((12, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        for x in range(12):
            a=int(62*(1 - x/12)**1.4)
            pygame.draw.line(shadow_left, (0,0,0,a), (x,0),(x,config.SCREEN_HEIGHT))
        surf.blit(shadow_left,(config.WALL_THICKNESS,0))
        shadow_right=pygame.Surface((12, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        for x in range(12):
            a=int(62*(x/12)**1.4)
            pygame.draw.line(shadow_right, (0,0,0,a), (x,0),(x,config.SCREEN_HEIGHT))
        surf.blit(shadow_right,(config.SCREEN_WIDTH-config.WALL_THICKNESS-12,0))

    def _draw_decor(self, surf, x, y, kind, lvl):
        if kind=="stone":
            pygame.draw.circle(surf, (0,0,0,70), (int(x)+1,y+1),6)
            col=(120,120,125) if lvl=="KAYA" else (110,90,70) if lvl=="TOPRAK" else (100,100,110)
            pygame.draw.circle(surf, col, (int(x),y),5)
            pygame.draw.circle(surf, (0,0,0), (int(x),y),5,1)
            pygame.draw.circle(surf, (255,255,255,90), (int(x)-2,y-2),1)
        elif kind=="crack":
            pygame.draw.line(surf, (0,0,0), (x,y),(x+14,y+8),2)
            pygame.draw.line(surf, (0,0,0), (x+6,y+3),(x+10,y+12),1)
        elif kind=="moss":
            pygame.draw.circle(surf, (50,110,50), (int(x),y),6)
            pygame.draw.circle(surf, (80,150,80), (int(x),y),4)
            pygame.draw.circle(surf, (0,0,0), (int(x),y),6,1)
        elif kind=="crystal":
            pygame.draw.polygon(surf, (140,180,255), [(x,y-8),(x-6,y+6),(x+6,y+6)])
            pygame.draw.polygon(surf, (0,0,0), [(x,y-8),(x-6,y+6),(x+6,y+6)],1)
            gfx.draw_glow(surf,(x,y),10,(140,200,255),30)

    def _draw_obstacle(self, surf, rect, meta, base_color, accent, lvl, world_rect):
        # soft drop shadow — depth
        gfx.draw_soft_shadow(surf, rect, radius=10, alpha=34)
        # ana renk varyasyonu
        col=base_color
        if meta["kind"]=="zigzag": col=tuple(min(255,c+18) for c in base_color)
        elif meta["kind"]=="step_deco": col=tuple(max(0,c-18) for c in base_color)
        elif meta["kind"]=="narrow": col=tuple(max(0,c-12) for c in base_color)
        # bevel body + texture
        gfx.draw_bevel_rect(surf, rect, col, radius=8)
        self._fill_obstacle_texture(surf, rect, col, lvl, meta)
        # üst specular 3D highlight
        pygame.draw.line(surf, tuple(min(255,c+52) for c in col), (rect.x+6, rect.y+1),(rect.x+rect.width-6, rect.y+1),3)
        pygame.draw.line(surf, (255,255,255,58), (rect.x+8, rect.y+3),(rect.x+rect.width-8, rect.y+3),1)
        pygame.draw.line(surf, accent, (rect.x+8, rect.y+6),(rect.x+rect.width-8, rect.y+6),1)
        # ambient occlusion bottom
        ao=pygame.Surface((rect.width-12, 4), pygame.SRCALPHA)
        ao.fill((0,0,0,54))
        surf.blit(ao,(rect.x+6, rect.bottom-5))
        # dış çerçeve crisp
        pygame.draw.rect(surf,(0,0,0,180),rect,width=2,border_radius=8)
        # kind detay — 3D his
        if meta["kind"]=="stepped":
            pygame.draw.line(surf,(0,0,0,120),(rect.x+10, rect.centery),(rect.x+rect.width-10, rect.centery),2)
            pygame.draw.line(surf,tuple(min(255,c+24) for c in col),(rect.x+10, rect.centery+1),(rect.x+rect.width-10, rect.centery+1),1)
            # step depth line
            pygame.draw.line(surf,(0,0,0,70),(rect.x+14, rect.centery+3),(rect.x+rect.width-14, rect.centery+3),1)
        elif meta["kind"]=="notch":
            is_left=world_rect.x==0
            nx=rect.right-7 if is_left else rect.x+7
            # carved notch — inner shadow
            pygame.draw.polygon(surf,(0,0,0,110),[(nx, rect.centery-7),(nx+ ( -8 if is_left else 8), rect.centery),(nx, rect.centery+7)])
            pygame.draw.polygon(surf, tuple(min(255,c+30) for c in col),[(nx, rect.centery-5),(nx+ ( -5 if is_left else 5), rect.centery),(nx, rect.centery+5)])
        elif meta["kind"]=="zigzag":
            # subtle serration
            for x in range(rect.x+12, rect.right-12, 18):
                pygame.draw.line(surf,(0,0,0,52),(x, rect.y+4),(x+6, rect.y+10),1)
        # magma glow on obstacle itself
        if lvl=="MAGMA":
            gfx.draw_glow(surf, rect.center, 18, (255,70,20), 16)

    def _fill_obstacle_texture(self,surf,rect,col,lvl,meta):
        pygame.draw.rect(surf,col,rect,border_radius=7)
        # iç doku katmanı
        rnd=random.Random(hash((rect.x,rect.y,rect.width))%99999)
        if lvl=="HAVA":
            # tuğla
            for y in range(rect.y+8, rect.bottom-6, 9):
                pygame.draw.line(surf,(0,0,0, 70),(rect.x+4,y),(rect.x+rect.width-4,y),1)
                for x in range(rect.x+10, rect.x+rect.width-10, 28):
                    if rnd.random()<0.5:
                        pygame.draw.line(surf,(0,0,0, 60),(x,y),(x,y+9),1)
        elif lvl=="TOPRAK":
            for _ in range(6 if rect.width>100 else 3):
                x=_safe_randint(rnd, rect.x+6, rect.x+rect.width-8); y=_safe_randint(rnd, rect.y+4, rect.bottom-5)
                pygame.draw.circle(surf,tuple(max(0,c-18) for c in col),(x,y),_safe_randint(rnd, 2,4))
                pygame.draw.line(surf,(60,35,15),(x,y),(x+rnd.randint(-8,8),y+rnd.randint(-5,5)),1)
        elif lvl=="KAYA":
            for _ in range(7 if rect.width>90 else 4):
                x=_safe_randint(rnd, rect.x+6, rect.right-6); y=_safe_randint(rnd, rect.y+5, rect.bottom-5)
                pygame.draw.line(surf,(0,0,0),(x,y),(x+rnd.randint(-10,10),y+rnd.randint(-6,6)),1)
                if rnd.random()<0.4: pygame.draw.circle(surf,(80,80,85),(x,y),2)
            # kenar kristal
            if rnd.random()<0.5:
                cx=rect.x+rect.width//2; cy=rect.centery
                pygame.draw.polygon(surf,(160,190,255),[(cx,cy-6),(cx-4,cy+4),(cx+4,cy+4)])
        elif lvl=="MAGMA":
            # çatlak + damarlar
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+4, rect.bottom-4)
                pygame.draw.line(surf,(0,0,0), (x,y),(x+rnd.randint(-12,12), y+rnd.randint(-7,7)),1)
            # magma damar glow
            vx=rect.x+rect.width//2
            for i in range(2):
                px=vx+rnd.randint(-16,16)
                pygame.draw.line(surf,(255,90,20),(px,rect.y+3),(px+rnd.randint(-5,5), rect.bottom-3),2)
                gfx.draw_glow(surf,(px, rect.centery),13,(255,70,20),44)
        elif lvl=="BUZUL":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf,(255,255,255),(x,y),2)
                pygame.draw.line(surf,(180,220,255),(x-4,y),(x+4,y),1)
            pygame.draw.line(surf,(255,255,255,120),(rect.x+4,rect.y+3),(rect.x+rect.width-4,rect.y+3),2)
        elif lvl=="DERIN":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                gfx.draw_glow(surf,(x,y),8,(80,140,255),28)
                pygame.draw.circle(surf,(40,70,130),(x,y),2)
        elif lvl=="KATMAN KAYASI":
            for _ in range(5 if rect.width>90 else 3):
                x=_safe_randint(rnd, rect.x+6, rect.right-6); y=_safe_randint(rnd, rect.y+5, rect.bottom-5)
                pygame.draw.circle(surf, tuple(max(0,c-18) for c in col), (x,y), 2)
                pygame.draw.line(surf, (40,30,20), (x, y), (x+rnd.randint(-8,8), y+rnd.randint(-4,4)), 1)
                if rnd.random()<0.3:
                    gfx.draw_glow(surf, (x,y), 6, (180,160,130), 18)
        elif lvl=="KANALIZASYON":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+4, rect.bottom-4)
                pygame.draw.line(surf, (0,0,0), (x,y), (x+rnd.randint(-10,10), y+rnd.randint(-6,6)), 1)
                pygame.draw.circle(surf, (70,90,60), (x,y), 2)
            for _ in range(2):
                px=rect.x+rect.width//2 + rnd.randint(-18,18)
                pygame.draw.line(surf, (110,160,90), (px, rect.y+2), (px, rect.bottom-2), 1)
                gfx.draw_glow(surf, (px, rect.centery), 8, (140,210,90), 22)
        elif lvl=="CAFE":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (180,140,100), (x,y), 2)
                pygame.draw.line(surf, (120,80,50), (x-4, y), (x+4, y), 1)
            pygame.draw.line(surf, (255,255,255, 70), (rect.x+6, rect.y+3), (rect.x+rect.width-6, rect.y+3), 1)
        elif lvl=="OFIS":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (200,205,210), (x,y), 2)
                pygame.draw.line(surf, (140,150,160), (x-6, y), (x+6, y), 1)
            pygame.draw.line(surf, (255,255,255, 60), (rect.x+6, rect.y+3), (rect.x+rect.width-6, rect.y+3), 1)
            # monitör parıltısı
            if rnd.random()<0.4:
                gfx.draw_glow(surf, (rect.centerx, rect.centery), 10, (90,130,210), 16)
        elif lvl=="BACKROOMS":
            for y in range(rect.y+6, rect.bottom-6, 8):
                pygame.draw.line(surf, (185,165,105, 60), (rect.x+6, y), (rect.x+rect.width-6, y), 1)
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (210,190,130), (x,y), 2)
        elif lvl=="GUC SANTRALI":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.rect(surf, (80,80,84), pygame.Rect(x-6, y-3, 12, 6))
                pygame.draw.rect(surf, (0,0,0), pygame.Rect(x-6, y-3, 12, 6), 1)
            for i in range(2):
                px=rect.x+rect.width//2 + rnd.randint(-16,16)
                pygame.draw.line(surf, (255,220,0), (px, rect.y+2), (px, rect.bottom-2), 2)
                gfx.draw_glow(surf, (px, rect.centery), 8, (255,220,0), 18)
        elif lvl=="MUZE":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (200,190,170), (x,y), 2)
                pygame.draw.line(surf, (160,140,120), (x-5, y), (x+5, y), 1)
            pygame.draw.line(surf, (255,255,255, 50), (rect.x+6, rect.y+3), (rect.x+rect.width-6, rect.y+3), 1)
        elif lvl=="SINIF":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.rect(surf, (100,70,40), pygame.Rect(x-5, y-2, 10, 6), border_radius=2)
                pygame.draw.rect(surf, (0,0,0), pygame.Rect(x-5, y-2, 10, 6), 1)
        elif lvl=="FABRIKA":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (90,90,94), (x,y), 3)
                pygame.draw.circle(surf, (60,60,64), (x,y), 3, 1)
            for i in range(2):
                px=rect.x+rect.width//2 + rnd.randint(-14,14)
                gfx.draw_glow(surf, (px, rect.centery), 8, (255,100,40), 20)
        elif lvl=="POLIGAN":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pts=[(x, y-4),(x-4, y+4),(x+4, y+4)]
                pygame.draw.polygon(surf, (140,100,180), pts)
                pygame.draw.polygon(surf, (0,0,0), pts, 1)
                gfx.draw_glow(surf, (x,y), 6, (255,80,180), 16)
        elif lvl=="ORMAN":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (60,110,70), (x,y), 3)
                pygame.draw.circle(surf, (30,70,40), (x,y), 3, 1)
            pygame.draw.line(surf, (90,60,30), (rect.centerx-6, rect.y+6), (rect.centerx-6, rect.bottom-4), 2)
        elif lvl=="SARAY":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (220,200,150), (x,y), 2)
                gfx.draw_glow(surf, (x,y), 6, (255,215,0), 18)
            pygame.draw.line(surf, (255,215,0, 40), (rect.x+8, rect.y+4), (rect.x+rect.width-8, rect.y+4), 2)
        elif lvl=="KOY":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (180,160,120), (x,y), 2)
                pygame.draw.line(surf, (120,90,60), (x-4, y), (x+4, y), 1)
        elif lvl=="SEHIR":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.rect(surf, (80,90,108), pygame.Rect(x-4, y-2, 8, 4))
                pygame.draw.rect(surf, (255,220,100), pygame.Rect(x-3, y-1, 6, 2))
                gfx.draw_glow(surf, (x,y), 6, (100,180,255), 14)
        elif lvl=="TOKYO":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                col = (255,50,150) if rnd.random()<0.5 else (50,200,255)
                pygame.draw.circle(surf, col, (x,y), 2)
                gfx.draw_glow(surf, (x,y), 6, col, 22)
        elif lvl=="FRANSA":
            for _ in range(3):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (200,180,200), (x,y), 2)
                pygame.draw.line(surf, (160,140,180), (x-4, y), (x+4, y), 1)
            pygame.draw.line(surf, (255,255,255, 40), (rect.x+6, rect.y+3), (rect.x+rect.width-6, rect.y+3), 1)
        elif lvl=="FINAL":
            for _ in range(4):
                x=_safe_randint(rnd, rect.x+8, rect.right-8); y=_safe_randint(rnd, rect.y+6, rect.bottom-6)
                pygame.draw.circle(surf, (90,70,140), (x,y), 3)
                pygame.draw.circle(surf, (140,110,200), (x,y), 1)
                gfx.draw_glow(surf, (x,y), 8, (255,215,0), 20)
            pygame.draw.line(surf, (255,215,0), (rect.x+8, rect.y+3), (rect.x+rect.width-8, rect.y+3), 2)
            gfx.draw_glow(surf, rect.center, 14, (255,215,0), 16)

    def _draw_coin(self,surf,sx,sy,c):
        # bob + spin — dolgun, Tetris+ polish
        bob_y=sy+int(3.2*math.sin(pygame.time.get_ticks()/285 + c.bob*2.2))
        spin_scale=abs(math.cos(c.spin))
        # perspective squash on spin
        w=max(7,int(c.r*2*(0.58+0.42*spin_scale))); h=c.r*2
        # glow — value'ye göre
        if c.value>=5:
            gfx.draw_glow(surf,(sx,bob_y), c.r+10,(255,215,0), 38)
            gfx.draw_glow(surf,(sx,bob_y), c.r+5,(255,235,110), 22)
        else:
            gfx.draw_glow(surf,(sx,bob_y), c.r+6,(255,235,120), 20)
        # shadow under coin
        pygame.draw.ellipse(surf, (0,0,0,44), pygame.Rect(sx-7, bob_y+7, 14, 6))
        ellipse=pygame.Rect(sx-w//2,bob_y-h//2,w,h)
        pygame.draw.ellipse(surf,(255,215,0),ellipse)
        # inner bevel gradient (top light → bottom dark)
        inner=ellipse.inflate(-4,-4)
        pygame.draw.ellipse(surf,(255,238,130),inner)
        pygame.draw.ellipse(surf,(255,180,0),ellipse,2)
        pygame.draw.ellipse(surf,(0,0,0,120),ellipse,1)
        # top specular
        pygame.draw.ellipse(surf,(255,255,220, 196),pygame.Rect(sx-w//3,bob_y-h//2+3,w//2+1,h//3))
        pygame.draw.ellipse(surf,(255,255,255, 88),pygame.Rect(sx-w//4,bob_y-h//2+5,w//3, h//4))
        # value — crisp with outline
        if spin_scale>0.42:
            font=pygame.font.SysFont("Arial", 12, bold=True)
            txt=font.render(str(c.value),True,(96,48,0))
            sh_col=(255,255,255)
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1)]:
                surf.blit(font.render(str(c.value),True,sh_col),(sx-txt.get_width()//2+dx, bob_y-txt.get_height()//2+dy))
            surf.blit(txt,(sx-txt.get_width()//2, bob_y-txt.get_height()//2))
        if c.value>=5:
            # sparkle
            sx2=sx+5; sy2=bob_y-7
            pygame.draw.circle(surf,(255,255,255,220),(sx2,sy2),2)
            gfx.draw_glow(surf,(sx2,sy2),4,(255,255,255), 28)
