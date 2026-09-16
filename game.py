import pygame
import config
from player import Player
from camera import Camera
from world import World
import save_system
from particles import ParticleSystem
from audio import audio
import graphics as gfx
import math
from monster import Monster
import random as _rnd
try:
    from online import OnlineManager
except:
    OnlineManager = None
try:
    from bot import BotPlayer
except:
    BotPlayer = None

class Game:
    def __init__(self, save):
        self.save = save
        self.player = Player(config.SCREEN_WIDTH//2 - config.PLAYER_W//2, 120)
        self.camera = Camera()
        self.camera.reset(self.player.y)
        self.world = World()
        self.world.reset()
        self.particles = ParticleSystem()

        self.state = "menu"
        self.prev_state = "menu"
        self.paused = False
        self.death_timer = 0.0
        self.izmir_marsi_playing = False
        self.izmir_marsi_timer = 0.0

        self.level = 1
        self.level_info = config.LEVELS[0]
        self.level_up_anim = 0.0
        self.just_unlocked = None  # karakter id

        # canavar + bölüm sistemi
        self.monster = Monster()
        self.level_mode = None  # None=sonsuz, int=1..22 bölüm
        self.level_target_px = None
        self.level_start_y = 0
        self.level_complete_timer = 0.0
        self.level_complete_data = None  # dict for screen
        self.ending_anim = 0.0
        self.ending_timer = 0.0
        self.levels_index = 0  # seçim ekranı cursor
        self.levels_scroll = 0

        # profil — kalıcı 5 haneli ID
        self.profile_nick_input = ""
        self.profile_error = ""
        self.profile_active = False
        # VS / Online
        self.play_select_index = 0  # 0 ONLINE, 1 BOT
        self.online_input = ""  # 5 haneli ID giriş
        self.online_error = ""
        self.online_info = None  # bulunan rakip dict
        self.online_searching = False
        self.vs_mode = None  # None, "bot", "online"
        self.vs_opponent_nick = None
        self.vs_opponent_id = None
        self.vs_bot = None
        self.vs_remote = None  # online rakip state
        self.online_mgr = OnlineManager(self.save) if OnlineManager else None
        self.vs_race_timer = 0.0
        self.vs_result = None

        # ilk açılışta sadece Nickname yoksa profil ekranına zorla — ID server'da ONLINE'da oluşur
        import save_system as _ss
        try:
            if not _ss.is_valid_nick(self.save.get("nickname") or ""):
                self.state = "profile_create"
                self.profile_nick_input = ""
                self.profile_error = ""
            # NOT: ana menü ve offline sistemler için server bağlantısı GEREKMEZ
            # Server'a sadece OYNA->ONLINE'da bağlanılacak
        except:
            pass

        self.menu_index = 0
        self.menu_options = ["OYNA", "BÖLÜMLER", "KARAKTERLER", "MAGAZA", "ENVANTER", "TEMALAR", "AYARLAR", "CIKIS"]
        self.shop_tab = 0
        self.shop_index = 0
        self.char_index = 0
        self.inv_tab = 0
        self.inv_index = 0
        self.theme_index = 0

        # settings slider index
        self.settings_index = 0  # 0 master,1 music,2 sfx,3 tutorial toggle,4 geri
        self.settings_items = ["MASTER", "MUSIC", "SFX", "TUTORIAL", "GERI"]

        self.font_small = None
        self.font_med = None
        self.font_big = None
        self.font_huge = None
        self.font_tiny = None

        self.transition = 0.0  # 0-1 fade
        self.transition_target = None

        self.hover_index = -1  # for hover sound

        # apply saved audio settings
        try:
            s = self.save.get("settings", {})
            audio.set_master(s.get("master", 0.7))
            audio.set_music(s.get("music", 0.5))
            audio.set_sfx(s.get("sfx", 0.8))
        except:
            pass
        audio.load_or_generate()

    def init_fonts(self):
        # cache fonts once
        try:
            self.font_tiny = pygame.font.SysFont("Arial", 12)
            self.font_small = pygame.font.SysFont("Arial", 16)
            self.font_med = pygame.font.SysFont("Arial", 20, bold=True)
            self.font_big = pygame.font.SysFont("Arial", 28, bold=True)
            self.font_huge = pygame.font.SysFont("Arial", 42, bold=True)
        except Exception as e:
            print(f"font fail {e}")
            # fallback
            self.font_small = pygame.font.Font(None, 18)
            self.font_med = pygame.font.Font(None, 22)
            self.font_big = pygame.font.Font(None, 30)
            self.font_huge = pygame.font.Font(None, 44)

    def _return_to_menu(self):
        """ESC ile ana menüye dönüş — tüm döngüleri temizle, save et."""
        self.paused = False
        self.state = "menu"
        self.death_timer = 0.0
        self.level_up_anim = 0.0
        self.level_mode = None
        self.ending_anim = 0.0
        self.ending_timer = 0.0
        self.level_complete_timer = 0.0
        try:
            audio.stop_izmir_marsi()
        except: pass
        # ses/efekt temizliği — pause'taki timer'lar durur, update artık çalışmaz
        try:
            save_system.save_game(self.save)
        except:
            pass
        try:
            audio.play("click")
        except:
            pass

    def _complete_level(self):
        lvl = self.level_mode
        if lvl is None:
            return
        # yıldız hesapla: coin + canavar mesafesi
        coins = self.player.coins
        stars = 1
        if coins >= 6:
            stars = 2
        if coins >= 13:
            stars = 3
        # canavar uzaksa bonus
        try:
            gap = self.player.y - self.monster.y
            if gap > 320 and stars < 3:
                stars = min(3, stars+1)
        except: pass
        # save
        if lvl not in self.save.get("completed_levels", []):
            self.save["completed_levels"].append(lvl)
        if "level_stars" not in self.save:
            self.save["level_stars"] = {}
        prev = self.save["level_stars"].get(str(lvl), 0)
        if stars > prev:
            self.save["level_stars"][str(lvl)] = stars
            self.save["level_stars"][lvl] = stars  # int key de
        # bir sonrakini aç
        try:
            save_system.unlock_next_level(self.save, lvl)
        except:
            nxt = lvl+1
            if nxt <= len(config.LEVELS) and nxt not in self.save["unlocked_levels"]:
                self.save["unlocked_levels"].append(nxt)
        save_system.save_game(self.save)
        # level_complete verisi
        self.level_complete_data = {
            "level": lvl,
            "name": self.level_info["name"],
            "coins": coins,
            "total_coins": self.save.get("total_coins",0),
            "distance": self.player.distance_px / config.PIXELS_PER_METER,
            "stars": stars,
            "is_final": lvl >= len(config.LEVELS),
        }
        # canavar durdur
        try:
            audio.play("levelup")
            self.particles.emit_levelup(self.player.x + self.player.w//2, self.player.y)
        except: pass
        if lvl >= len(config.LEVELS):
            self.state = "ending"
            self.ending_anim = 0.0
            self.ending_timer = 0.0
            self.camera.y -= 12  # hafif sinematik başla
        else:
            self.state = "level_complete"
            self.level_complete_timer = 0.0
            self.level_up_anim = 0.0

    def start_game(self):
        # Sonsuz mod — canavar yok
        self.player.reset(config.SCREEN_WIDTH//2 - config.PLAYER_W//2, 80)
        self.camera.reset(self.player.y)
        self.world.reset()
        self.particles = ParticleSystem()
        self.death_timer = 0.0
        self.paused = False
        self.state = "playing"
        self.level_mode = None
        self.level_target_px = None
        self.level_complete_timer = 0.0
        self.ending_anim = 0.0
        self.level_up_anim = 0
        self.just_unlocked = None
        self.update_level(force=True)

    def get_level_target_px(self, lvl):
        # lvl 1..22 -> bitiş mesafesi (px)
        if lvl < len(config.LEVELS):
            return config.LEVELS[lvl]["distance"]  # bir sonraki levelin başlangıcı = bu levelin bitişi
        else:
            return config.LEVELS[-1]["distance"] + 12000

    def start_level(self, lvl):
        """Bölümlü kaçış — canavarlı"""
        lvl = max(1, min(len(config.LEVELS), int(lvl)))
        self.level = lvl
        for e in config.LEVELS:
            if e["level"] == lvl:
                self.level_info = e
                break
        self.player.reset(config.SCREEN_WIDTH//2 - config.PLAYER_W//2, 80)
        self.camera.reset(self.player.y)
        self.world.reset()
        # world'ün level_name'i doğru olsun diye next_gen_y'yi level başlangıcına ayarla
        # ama procedural sıfırdan başlasın, sadece görsel seviye zorla
        self.world.last_gap_start = None
        self.particles = ParticleSystem()
        self.monster = Monster()
        self.monster.reset(self.player.y, lvl, self.level_info["name"])
        self.death_timer = 0.0
        self.paused = False
        self.state = "playing"
        self.level_mode = lvl
        self.level_start_y = self.player.y
        self.level_target_px = self.get_level_target_px(lvl)
        self.level_complete_timer = 0.0
        self.level_complete_data = None
        self.ending_anim = 0.0
        self.ending_timer = 0.0
        self.level_up_anim = 0
        self.just_unlocked = None
        # save'te unlocked zaten var, ama garanti et
        if lvl not in self.save.get("unlocked_levels", []):
            self.save["unlocked_levels"].append(lvl)
            self.save["unlocked_levels"] = sorted(set(self.save["unlocked_levels"]))
            save_system.save_game(self.save)

    def update_level(self, force=False):
        dist_m = self.player.distance_px / config.PIXELS_PER_METER
        old_level = self.level
        new_level = save_system.update_level_and_unlocks(self.save, dist_m)
        # 75 engelde bir seviye ilerlet (uzatıldı - seviyeler daha uzun yoldan sonra)
        try:
            count_level = min(len(config.LEVELS), self.world.generated_sections // 75 + 1)
            if count_level > new_level:
                new_level = save_system.update_level_and_unlocks(self.save, config.LEVELS[count_level-1]["distance"]/100.0 + 0.1)
                # unlock için save'e yaz, level_info da güncellenecek
                new_level = max(new_level, count_level)
                if new_level > self.save.get("level",1):
                    self.save["level"] = new_level
                    for ch in config.CHARACTERS:
                        if ch["level"] == new_level and ch["id"] not in self.save["unlocked_characters"]:
                            self.save["unlocked_characters"].append(ch["id"])
        except:
            pass
        if new_level != self.level or force:
            self.level = new_level
            for e in config.LEVELS:
                if e["level"] == self.level:
                    self.level_info = e
                    break
            else:
                self.level_info = config.LEVELS[-1]
            if not force and new_level > old_level:
                self.level_up_anim = 2.2
                audio.play("levelup")
                # hangi karakter açıldı?
                for ch in config.CHARACTERS:
                    if ch["level"] == new_level:
                        self.just_unlocked = ch["name"]
                        audio.play("unlock")
                        break
                # partikül
                self.particles.emit_levelup(self.player.x + self.player.w//2, self.player.y)
        return new_level

    def get_equipped(self):
        return {
            "hat": self.save.get("selected_hat"),
            "bag": self.save.get("selected_bag"),
            "glasses": self.save.get("selected_glasses"),
            "cane": self.save.get("selected_cane"),
        }

    def get_char_data(self):
        sel = self.save.get("selected_character", "cop_adam")
        for c in config.CHARACTERS:
            if c["id"] == sel:
                return c
        return config.CHARACTERS[0]

    def update(self, dt, keys_held):
        # transition alpha
        if self.transition_target is not None:
            self.transition += dt*6
            if self.transition >= 1:
                self.transition = 0
                self.transition_target = None
        # İzmir Marşı timer — her durumda akar
        if self.izmir_marsi_timer > 0:
            self.izmir_marsi_timer -= dt
            if self.izmir_marsi_timer <= 0:
                self.izmir_marsi_playing = False
                try: audio.stop_izmir_marsi()
                except: pass

        # Bölüm tamamlama / final ekranları — input bekle, timer ilerlet
        if self.state == "level_complete":
            self.level_complete_timer += dt
            self.particles.update(dt, self.camera.y, self.level_info["name"])
            if self.level_up_anim > 0:
                self.level_up_anim -= dt
            return
        if self.state == "ending":
            self.ending_timer += dt
            self.ending_anim += dt
            self.particles.update(dt, self.camera.y, self.level_info["name"])
            # sinematik kamera — yavaşça yukarı kaydır
            self.camera.y -= 42 * dt
            if self.camera.y < 0:
                self.camera.y = 0
            return
        if self.state == "playing":
            if self.paused:
                # tutorial kapama vs yine de input alabilir
                return
            self.player.handle_input(keys_held, dt)
            self.world.ensure_generated(self.camera.y)
            self.world.update_coins(dt)
            evt = self.player.update_physics(dt, self.world.obstacles)
            if evt == "land":
                self.particles.emit_land(self.player.x + self.player.w//2, self.player.y + self.player.h)
                audio.play("jump", 0.5)  # iniş sesi hafif
            elif evt == "death":
                audio.play("death")
                self.particles.emit_death(self.player.x + self.player.w//2, self.player.y + self.player.h//2)

            gained = self.world.check_coin_collection(self.player.rect)
            if gained:
                self.save["total_coins"] += gained
                self.player.coins += gained
                # coin sesi ve parçacık — value'ye göre yoğunluk
                self.particles.emit_coin(self.player.x + self.player.w//2, self.player.y + self.player.h//2, gained)
                if gained >= 5:
                    audio.play("coin5")
                elif gained >= 3:
                    audio.play("coin5", 0.7)
                else:
                    audio.play("coin")

            self.camera.update(dt, self.player.y, self.player.alive)
            # Bölümlü kaçış modunda canavar ve bitiş
            if self.level_mode is not None:
                # canavar takip — gerçek tehdit
                try:
                    self.monster.update(dt, self.player, self.camera.y)
                    if self.monster.check_catch(self.player) and self.player.alive:
                        self.player.alive = False
                        self.player.state = "death"
                        audio.play("death")
                        self.particles.emit_death(self.player.x + self.player.w//2, self.player.y + self.player.h//2)
                        # canavar ısırma efekti
                        for _ in range(12):
                            self.particles.emit_coin(self.monster.x+self.monster.w//2, self.monster.y+self.monster.h//2, 1)
                except Exception as e:
                    print(f"[Monster] {e}")
                # bölüm bitiş kontrolü — mesafe hedefi
                if self.player.alive and self.player.y >= self.level_target_px - 80:
                    # bölüm tamamlandı
                    self._complete_level()
                    return
            else:
                self.update_level()
            dist_m = self.player.distance_px / config.PIXELS_PER_METER
            if dist_m > self.save.get("best_distance", 0):
                self.save["best_distance"] = dist_m

            if not self.player.alive:
                self.death_timer += dt
                if self.death_timer > 1.0:
                    self.state = "gameover"
                    save_system.save_game(self.save)

            # particles
            self.particles.update(dt, self.camera.y, self.level_info["name"])
            if self.level_up_anim > 0:
                self.level_up_anim -= dt

            # tutorial ilk oyunda 8sn sonra otomatik kapanacak veya ESC
            if self.save.get("settings", {}).get("show_tutorial", True) and not self.save.get("tutorial_done", False):
                if dist_m > 4:
                    # 4m sonra tutorial bitti say
                    self.save["tutorial_done"] = True
                    save_system.save_game(self.save)
        # VS modları — BOT / ONLINE yarış
        if self.state in ("vs_bot","vs_online"):
            if self.paused:
                return
            self.vs_race_timer += dt
            # player
            self.player.handle_input(keys_held, dt)
            # bot AI
            if self.state=="vs_bot" and self.vs_bot and self.vs_bot.alive:
                self.vs_bot.handle_ai(self.world.obstacles, dt)
            # world
            self.world.ensure_generated(self.camera.y)
            self.world.update_coins(dt)
            evt = self.player.update_physics(dt, self.world.obstacles)
            if evt=="land":
                self.particles.emit_land(self.player.x+self.w//2, self.player.y+self.h)
                audio.play("jump",0.5)
            elif evt=="death":
                audio.play("death")
                self.particles.emit_death(self.player.x+self.w//2, self.player.y+self.h//2)
            # bot physics
            bot_evt=None
            if self.state=="vs_bot" and self.vs_bot:
                bot_evt=self.vs_bot.update_physics(dt, self.world.obstacles)
                # bot coin toplama (görsel)
                for c in self.world.coins:
                    if not c.collected and self.vs_bot.rect.colliderect(c.rect()):
                        c.collected=True
                        self.vs_bot.coins+=c.value
            # online remote state güncelle
            if self.state=="vs_online" and self.online_mgr:
                try:
                    remote=self.online_mgr.get_remote_state()
                    if remote:
                        self.vs_remote=remote
                except:
                    self.vs_remote=None
                # bağlantı kopma simülasyonu: eğer 5sn'de hiç veri yoksa uyarı
            gained=self.world.check_coin_collection(self.player.rect)
            if gained:
                self.save["total_coins"]+=gained
                self.player.coins+=gained
                self.particles.emit_coin(self.player.x+self.w//2, self.player.y+self.h//2, gained)
                audio.play("coin5" if gained>=5 else "coin")
            self.camera.update(dt, self.player.y, self.player.alive)
            # monster her ikisini de tehdit etsin (ortadaki)
            try:
                self.monster.update(dt, self.player, self.camera.y)
                # bot'u da kontrol et — bot ölürse player kazanır
                bot_caught=False
                if self.state=="vs_bot" and self.vs_bot and self.vs_bot.alive:
                    if self.monster.check_catch(self.vs_bot):
                        self.vs_bot.alive=False
                        self.vs_bot.state="death"
                if self.monster.check_catch(self.player) and self.player.alive:
                    self.player.alive=False; self.player.state="death"
                    audio.play("death")
                    self.particles.emit_death(self.player.x+self.w//2, self.player.y+self.h//2)
            except: pass
            if not self.player.alive:
                self.death_timer+=dt
                if self.death_timer>1.2:
                    self.vs_result="lose"
                    self.state="gameover"
                    save_system.save_game(self.save)
            elif self.state=="vs_bot" and self.vs_bot and not self.vs_bot.alive:
                # bot öldü — player kazandı (otomatik bitiş değil, devam edebilir)
                pass
            self.particles.update(dt, self.camera.y, self.level_info["name"])
            # VS'de mesafe rekoru
            dist_m=self.player.distance_px/config.PIXELS_PER_METER
            if dist_m>self.save.get("best_distance",0):
                self.save["best_distance"]=dist_m

    # ---------- event handling ----------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            # İzmir Marşı toggle — M tuşu her yerde çalışır (menu/oyun/duraklatıldı)
            if event.key == pygame.K_m and self.state in ("menu","playing","paused","shop","characters","inventory","themes","settings"):
                # gameover'da M zaten menu'ye döner, orada marş çalma değil
                if self.state != "gameover":
                    self.izmir_marsi_playing = not self.izmir_marsi_playing
                    if self.izmir_marsi_playing:
                        audio.play_izmir_marsi(loop=False)
                        self.izmir_marsi_timer = 13.5
                    else:
                        audio.stop_izmir_marsi()
                        self.izmir_marsi_timer = 0
                    audio.play("click")
                    return
            # global hover/click sound
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                audio.play("hover", 0.6)
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                # menü onayı sesi
                if self.state in ("menu","characters","shop","inventory","themes","settings","paused","gameover"):
                    audio.play("click")

            if self.state == "playing":
                # paused overlay içindeyken özel tuşlar — ESC artık pause açmaz, doğrudan menu
                if self.paused:
                    if event.key == pygame.K_SPACE:
                        # SPACE hala devam et
                        self.paused = False
                        audio.play("click")
                    elif event.key == pygame.K_ESCAPE:
                        # ESC doğrudan ana menü — pause'ı tamamen temizle
                        self._return_to_menu()
                    elif event.key == pygame.K_q:
                        self.state = "menu"
                        self.paused = False
                        save_system.save_game(self.save)
                        audio.play("click")
                    elif event.key == pygame.K_s:
                        self.state = "settings"
                        self.prev_state = "paused"
                        audio.play("click")
                    elif event.key == pygame.K_h and self.save.get("settings", {}).get("show_tutorial"):
                        self.save["settings"]["show_tutorial"] = False
                        save_system.save_game(self.save)
                    return
                # normal oyun input — ESC asla pause açmaz
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                    audio.play("click")
                elif event.key == pygame.K_UP or event.key == pygame.K_w:
                    jumped = self.player.try_jump()
                    if jumped:
                        self.particles.emit_jump(self.player.x + self.player.w//2, self.player.y + self.player.h)
                        audio.play("jump")
                    else:
                        pass
                elif event.key == pygame.K_ESCAPE:
                    self._return_to_menu()
                elif event.key == pygame.K_h and self.save.get("settings", {}).get("show_tutorial"):
                    self.save["settings"]["show_tutorial"] = False
                    save_system.save_game(self.save)

            elif self.state == "menu":
                if event.key == pygame.K_UP:
                    self.menu_index = (self.menu_index - 1) % len(self.menu_options)
                elif event.key == pygame.K_DOWN:
                    self.menu_index = (self.menu_index + 1) % len(self.menu_options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.activate_menu()
                elif event.key == pygame.K_ESCAPE:
                    pass

            elif self.state == "gameover":
                if event.key == pygame.K_r:
                    self.start_game()
                elif event.key == pygame.K_m or event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    save_system.save_game(self.save)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_game()

            elif self.state == "shop":
                self.handle_shop_keys(event)
            elif self.state == "characters":
                self.handle_char_keys(event)
            elif self.state == "inventory":
                self.handle_inv_keys(event)
            elif self.state == "themes":
                self.handle_theme_keys(event)
            elif self.state == "settings":
                self.handle_settings_keys(event)
            elif self.state == "levels":
                self.handle_levels_keys(event)
            elif self.state == "level_complete":
                self.handle_level_complete_keys(event)
            elif self.state == "ending":
                self.handle_ending_keys(event)
            elif self.state == "profile_create":
                self.handle_profile_keys(event)
            elif self.state == "play_select":
                self.handle_play_select_keys(event)
            elif self.state == "online_menu":
                self.handle_online_keys(event)
            elif self.state in ("vs_bot", "vs_online"):
                self.handle_vs_keys(event)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.pos:
            self.handle_mouse(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.handle_mouse_hover(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            # shop/inventory/levels scroll
            if self.state == "shop":
                if event.y > 0:
                    self.shop_index = max(0, self.shop_index-1)
                else:
                    lst,_ = self.current_shop_list()
                    self.shop_index = min(len(lst)-1, self.shop_index+1)
            elif self.state == "inventory":
                if event.y > 0:
                    self.inv_index = max(0, self.inv_index-1)
                else:
                    tabs=["hat","bag","glasses","cane"]
                    key=tabs[self.inv_tab]
                    owned = [it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
                    self.inv_index = min(max(0,len(owned)-1), self.inv_index+1)
            elif self.state == "levels":
                if event.y > 0:
                    self.levels_index = max(0, self.levels_index-1)
                else:
                    self.levels_index = min(len(config.LEVELS)-1, self.levels_index+1)

    def activate_menu(self):
        opt = self.menu_options[self.menu_index]
        if opt == "OYNA":
            # VS seçim ekranı — ONLINE / BİLGİSAYARA KARŞI
            self.state = "play_select"
            self.play_select_index = 0
            self.online_input = ""
            self.online_error = ""
            self.online_info = None
            return
        elif opt == "BÖLÜMLER":
            self.state = "levels"
            self.levels_index = 0
            # ilk açık bölüme odaklan
            unlocked = self.save.get("unlocked_levels", [1])
            if unlocked:
                self.levels_index = 0
                # en son açığa git
                max_unlocked = max(unlocked)
                for i, e in enumerate(config.LEVELS):
                    if e["level"] == max_unlocked:
                        self.levels_index = i
                        break
            self.levels_scroll = 0
        elif opt == "KARAKTERLER":
            self.state = "characters"
            self.char_index = 0
        elif opt == "ENVANTER":
            self.state = "inventory"
            self.inv_tab = 0; self.inv_index = 0
        elif opt == "MAGAZA":
            self.state = "shop"
            self.shop_tab = 0; self.shop_index = 0
        elif opt == "TEMALAR":
            self.state = "themes"
            cur = self.save.get("theme","beyaz")
            for i,t in enumerate(config.THEMES):
                if t["id"]==cur:
                    self.theme_index=i; break
        elif opt == "AYARLAR":
            self.state = "settings"
            self.prev_state = "menu"
            self.settings_index = 0
        elif opt == "CIKIS":
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ---- shop ----
    def current_shop_list(self):
        tabs = ["hat","bag","glasses","cane"]
        key = tabs[self.shop_tab]
        return config.SHOP_ITEMS[key], key

    def handle_shop_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"; save_system.save_game(self.save); return
        if event.key == pygame.K_LEFT:
            self.shop_tab = (self.shop_tab -1) % 4; self.shop_index = 0; audio.play("hover",0.6)
        elif event.key == pygame.K_RIGHT:
            self.shop_tab = (self.shop_tab +1) %4; self.shop_index = 0; audio.play("hover",0.6)
        elif event.key == pygame.K_UP:
            self.shop_index = max(0, self.shop_index-1)
        elif event.key == pygame.K_DOWN:
            lst,_ = self.current_shop_list()
            self.shop_index = min(len(lst)-1, self.shop_index+1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            lst,key = self.current_shop_list()
            if 0 <= self.shop_index < len(lst):
                item = lst[self.shop_index]
                owned = item["id"] in self.save["owned_items"]
                if owned:
                    sel_key = {"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                    if self.save.get(sel_key) == item["id"]:
                        self.save[sel_key] = None
                    else:
                        self.save[sel_key] = item["id"]
                    save_system.save_game(self.save)
                else:
                    if self.save["total_coins"] >= item["price"]:
                        self.save["total_coins"] -= item["price"]
                        self.save["owned_items"].append(item["id"])
                        sel_key = {"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                        self.save[sel_key] = item["id"]
                        save_system.save_game(self.save)
                        audio.play("coin")
                    else:
                        audio.play("death",0.4)

    def handle_char_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"; save_system.save_game(self.save); return
        n = len(config.CHARACTERS); cols = 6 if n > 12 else 3
        if event.key == pygame.K_LEFT:
            self.char_index = (self.char_index -1) % n
        elif event.key == pygame.K_RIGHT:
            self.char_index = (self.char_index +1) % n
        elif event.key == pygame.K_UP:
            self.char_index = (self.char_index - cols) % n
        elif event.key == pygame.K_DOWN:
            self.char_index = (self.char_index + cols) % n
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            ch = config.CHARACTERS[self.char_index]
            if ch["id"] in self.save["unlocked_characters"]:
                self.save["selected_character"] = ch["id"]
                save_system.save_game(self.save)
                audio.play("click")

    def handle_inv_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state="menu"; return
        if event.key == pygame.K_LEFT:
            self.inv_tab = (self.inv_tab -1) %4; self.inv_index=0; audio.play("hover",0.6)
        elif event.key == pygame.K_RIGHT:
            self.inv_tab = (self.inv_tab+1)%4; self.inv_index=0; audio.play("hover",0.6)
        elif event.key == pygame.K_UP:
            self.inv_index = max(0, self.inv_index-1)
        elif event.key == pygame.K_DOWN:
            tabs=["hat","bag","glasses","cane"]
            key=tabs[self.inv_tab]
            owned = [it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
            self.inv_index = min(max(0,len(owned)-1), self.inv_index+1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            tabs=["hat","bag","glasses","cane"]
            key=tabs[self.inv_tab]
            owned = [it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
            if owned and 0 <= self.inv_index < len(owned):
                item = owned[self.inv_index]
                sel_key = {"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                if self.save.get(sel_key)==item["id"]:
                    self.save[sel_key]=None
                else:
                    self.save[sel_key]=item["id"]
                save_system.save_game(self.save)
                audio.play("click")

    def handle_theme_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state="menu"; save_system.save_game(self.save); return
        if event.key == pygame.K_LEFT:
            self.theme_index = (self.theme_index -1) % len(config.THEMES)
        elif event.key == pygame.K_RIGHT:
            self.theme_index = (self.theme_index +1) % len(config.THEMES)
        elif event.key == pygame.K_UP:
            self.theme_index = (self.theme_index -4) % len(config.THEMES)
        elif event.key == pygame.K_DOWN:
            self.theme_index = (self.theme_index +4) % len(config.THEMES)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.save["theme"] = config.THEMES[self.theme_index]["id"]
            save_system.save_game(self.save)
            audio.play("click")

    def handle_settings_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            # geri - paused ise playing+paused bayrağı ile dön
            if self.prev_state == "paused":
                self.state = "playing"
                self.paused = True
            else:
                self.state = self.prev_state if self.prev_state in ("menu",) else "menu"
            save_system.save_game(self.save)
            return
        if event.key == pygame.K_UP:
            self.settings_index = (self.settings_index -1) % len(self.settings_items)
            audio.play("hover",0.5)
        elif event.key == pygame.K_DOWN:
            self.settings_index = (self.settings_index +1) % len(self.settings_items)
            audio.play("hover",0.5)
        elif event.key == pygame.K_LEFT:
            self.adjust_setting(-0.1)
        elif event.key == pygame.K_RIGHT:
            self.adjust_setting(0.1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.settings_index == 3:  # tutorial toggle
                cur = self.save["settings"].get("show_tutorial", True)
                self.save["settings"]["show_tutorial"] = not cur
                save_system.save_game(self.save)
                audio.play("click")
            elif self.settings_index == 4:
                if self.prev_state == "paused":
                    self.state = "playing"; self.paused = True
                else:
                    self.state = self.prev_state if self.prev_state in ("menu",) else "menu"
                save_system.save_game(self.save)

    def adjust_setting(self, delta):
        s = self.save["settings"]
        if self.settings_index == 0:
            s["master"] = round(max(0, min(1, s["master"]+delta)), 2)
            audio.set_master(s["master"])
        elif self.settings_index == 1:
            s["music"] = round(max(0, min(1, s["music"]+delta)), 2)
            audio.set_music(s["music"])
        elif self.settings_index == 2:
            s["sfx"] = round(max(0, min(1, s["sfx"]+delta)), 2)
            audio.set_sfx(s["sfx"])
        save_system.save_game(self.save)

    def handle_levels_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"; return
        n = len(config.LEVELS)
        # 4 sütun grid için cols=4
        cols = 4
        if event.key == pygame.K_LEFT:
            self.levels_index = (self.levels_index - 1) % n
            audio.play("hover", 0.5)
        elif event.key == pygame.K_RIGHT:
            self.levels_index = (self.levels_index + 1) % n
            audio.play("hover", 0.5)
        elif event.key == pygame.K_UP:
            self.levels_index = (self.levels_index - cols) % n
            audio.play("hover", 0.5)
        elif event.key == pygame.K_DOWN:
            self.levels_index = (self.levels_index + cols) % n
            audio.play("hover", 0.5)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            lvl = config.LEVELS[self.levels_index]["level"]
            unlocked = self.save.get("unlocked_levels", [1])
            if lvl in unlocked:
                self.start_level(lvl)
                audio.play("click")
            else:
                audio.play("death", 0.4)

    def handle_level_complete_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "levels"
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            data = self.level_complete_data or {}
            lvl = data.get("level", 1)
            if data.get("is_final"):
                self.state = "menu"
            else:
                # bir sonraki bölüme geç veya seviye seçime dön
                nxt = lvl + 1
                if nxt in self.save.get("unlocked_levels", []):
                    self.start_level(nxt)
                else:
                    self.state = "levels"
            audio.play("click")

    def handle_ending_keys(self, event):
        if event.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
            # skip
            self.state = "menu"
            self.ending_anim = 0
            self.ending_timer = 0
            audio.play("click")

    # ---- profil / vs / online ----
    def _try_create_profile(self):
        nick = self.profile_nick_input.strip()
        import save_system as _ss
        if not _ss.is_valid_nick(nick):
            self.profile_error = "Nick 2-16 karakter olmalı (harf/sayı/_)"
            audio.play("death",0.4)
            return
        # Sadece Nickname'i yerel save'e kaydet — ID SERVER'da ONLINE'da oluşacak
        self.save["nickname"] = nick
        # player_id henüz yoksa None bırak (ilk ONLINE'da server üretecek)
        save_system.save_game(self.save)
        audio.play("levelup")
        self.state = "menu"
        self.profile_error = ""

    def _enter_online(self):
        """OYNA->ONLINE'da server'a bağlan, gerekirse ilk ID'yi server'dan al."""
        self.online_input = ""
        self.online_error = ""
        self.online_info = None
        self.online_searching = False
        # Bağlantı dene
        if not self.online_mgr:
            self.online_error = "Sunucuya bağlanılamadı."
            return
        # Eğer henüz ID yoksa server'dan iste
        pid = str(self.save.get("player_id") or "").strip()
        nick = str(self.save.get("nickname") or "").strip()
        import save_system as _ss
        if not _ss.is_valid_player_id(pid):
            # İlk ONLINE — server ID üretsin
            ok, result = self.online_mgr.register_new(nick)
            if not ok:
                if "Sunucuya bağlanılamadı" in str(result):
                    self.online_error = "Sunucuya bağlanılamadı."
                else:
                    self.online_error = result
                return
            # ok -> save zaten güncellendi (register_new içinde)
            self.online_error = ""
        else:
            # Mevcut ID ile login (online duruma geç)
            ok, msg = self.online_mgr.login()
            if not ok:
                # login başarısızsa (eski ID DB'de yoksa) yeni ID dene
                if "bulunamadı" in str(msg):
                    ok2, res2 = self.online_mgr.register_new(nick)
                    if not ok2:
                        self.online_error = res2 if "Sunucuya" in str(res2) else "Sunucuya bağlanılamadı."
                        return
                elif "Sunucuya bağlanılamadı" in str(msg):
                    self.online_error = "Sunucuya bağlanılamadı."
                    return
                else:
                    # login hatası ama offline değilse yine de devam et
                    self.online_error = ""
            else:
                self.online_error = ""
        self.profile_error = ""

    def handle_profile_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            # ESC ile çıkılamaz — profil zorunlu
            return
        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            self._try_create_profile()
        elif event.key == pygame.K_BACKSPACE:
            self.profile_nick_input = self.profile_nick_input[:-1]
        else:
            # printable unicode
            ch = getattr(event, 'unicode', '')
            if ch and ch.isprintable() and len(self.profile_nick_input) < 16:
                # sadece izin verilen karakterler
                if ch not in ('\n','\r','\t'):
                    self.profile_nick_input += ch

    def handle_play_select_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"; return
        if event.key == pygame.K_UP:
            self.play_select_index = (self.play_select_index -1) % 3
            audio.play("hover",0.5)
        elif event.key == pygame.K_DOWN:
            self.play_select_index = (self.play_select_index +1) % 3
            audio.play("hover",0.5)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.play_select_index == 0:
                # ONLINE — sadece burada server'a bağlan
                self.state = "online_menu"
                audio.play("click")
                self._enter_online()
            elif self.play_select_index == 1:
                # BİLGİSAYARA KARŞI
                self.start_vs_bot()
                audio.play("click")
            else:
                self.state = "menu"

    def handle_online_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "play_select"; self.online_error=""; return
        if event.key == pygame.K_BACKSPACE:
            self.online_input = self.online_input[:-1]
            self.online_error=""
        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            # ara
            self._online_search()
        else:
            ch = getattr(event,'unicode','')
            if ch and ch.isdigit() and len(self.online_input) < 5:
                self.online_input += ch
            elif ch and ch.isdigit()==False and ch.isprintable():
                # geçersiz karakter — hata
                pass
        # yön tuşları ile MAÇ BAŞLAT tetiklenebilir (online_info varsa)
        if self.online_info and event.key in (pygame.K_RETURN, pygame.K_SPACE) and len(self.online_input)==5:
            # zaten _online_search içinde maç başlatma ayrı buton, burada ek shortcut
            pass

    def _online_search(self):
        tid = self.online_input.strip()
        import save_system as _ss
        if not _ss.is_valid_player_id(tid):
            self.online_error = "ID 5 rakam olmalı (örn: 48217)"
            audio.play("death",0.4)
            return
        if not self.online_mgr:
            self.online_error = "Online modül yüklenemedi"
            return
        # kendi ID'n mi?
        if tid == str(self.save.get("player_id")):
            self.online_error = "Kendi ID'nizi giremezsiniz"
            audio.play("death",0.4)
            return
        self.online_searching = True
        self.online_error = "Aranıyor..."
        audio.play("hover",0.5)
        info, msg = self.online_mgr.search_player(tid)
        self.online_searching = False
        if info:
            self.online_info = info
            self.online_error = ""
            audio.play("levelup")
        else:
            self.online_info = None
            self.online_error = msg if msg else "Oyuncu bulunamadı."
            audio.play("death",0.4)

    def start_vs_bot(self):
        self.vs_mode = "bot"
        self.vs_opponent_nick = "BOT"
        self.vs_opponent_id = "BOT01"
        # bot karakteri rastgele
        import random
        bot_char = random.choice(config.CHARACTERS)
        self.vs_bot_char = bot_char
        self.vs_remote = None
        # VS yarış — aynı dünya, bot arkada
        self.player.reset(config.SCREEN_WIDTH//2 - config.PLAYER_W//2, 80)
        self.camera.reset(self.player.y)
        self.world.reset()
        self.particles = ParticleSystem()
        self.death_timer=0; self.paused=False
        self.state="vs_bot"
        self.level_mode=None
        self.level_target_px=None
        self.level_start_y=self.player.y
        self.vs_race_timer=0.0
        self.vs_result=None
        self.level = 1
        self.level_info=config.LEVELS[0]
        if BotPlayer:
            self.vs_bot = BotPlayer(config.SCREEN_WIDTH//2 + 24, 80)
        else:
            self.vs_bot=None
        # monster da VS'de aktif — her ikisini de kovalasın
        self.monster = Monster()
        self.monster.reset(self.player.y, 1, "HAVA")

    def start_vs_online(self):
        if not self.online_info:
            self.online_error="Önce oyuncu bulun"
            return
        self.vs_mode="online"
        self.vs_opponent_nick=self.online_info.get("nick","Rakip")
        self.vs_opponent_id=self.online_info.get("id","?????")
        # eşleşme oluştur
        if self.online_mgr:
            ok, sess = self.online_mgr.create_match(self.vs_opponent_id)
            if not ok:
                self.online_error="Eşleşme oluşturulamadı"
                audio.play("death",0.4)
                return
            # sync başlat
            def _get_local():
                return {"x": self.player.x, "y": self.player.y, "vy": self.player.vy, "alive": self.player.alive, "coins": self.player.coins, "char": self.save.get("selected_character")}
            try:
                self.online_mgr.start_sync(_get_local)
            except:
                pass
        self.player.reset(config.SCREEN_WIDTH//2 - config.PLAYER_W//2, 80)
        self.camera.reset(self.player.y)
        self.world.reset()
        self.particles=ParticleSystem()
        self.death_timer=0; self.paused=False
        self.state="vs_online"
        self.level_start_y=self.player.y
        self.vs_race_timer=0.0
        self.vs_result=None
        self.level=1
        self.level_info=config.LEVELS[0]
        self.monster=Monster()
        self.monster.reset(self.player.y, 1, "HAVA")
        audio.play("levelup")

    def handle_vs_keys(self, event):
        if event.key==pygame.K_ESCAPE:
            # VS'den çık — online sync durdur
            try:
                if self.online_mgr: self.online_mgr.stop_sync()
            except: pass
            self.state="play_select"
            self.vs_mode=None
            self.vs_bot=None
            audio.play("click")
        elif event.key==pygame.K_SPACE:
            self.paused= not self.paused

    def handle_mouse(self, pos):
        mx,my = pos
        if self.state=="menu":
            # draw_menu ile aynı geometri: btn 320x42 start_y 182 gap 48
            btn_w, btn_h = 320, 42; start_y = 182; gap = 48
            for i in range(len(self.menu_options)):
                bx = config.SCREEN_WIDTH//2 - btn_w//2; by = start_y + i*gap
                if bx <= mx <= bx+btn_w and by <= my <= by+btn_h:
                    self.menu_index = i; audio.play("hover",0.4); self.activate_menu(); break
        elif self.state=="gameover":
            # draw_gameover: box W//2-250,H//2-170,500,360 -> b1 box.x+50,box.y+285 190x44
            box = pygame.Rect(config.SCREEN_WIDTH//2-250, config.SCREEN_HEIGHT//2-170, 500, 360)
            b1 = pygame.Rect(box.x+50, box.y+285, 190, 44)
            b2 = pygame.Rect(box.x+260, box.y+285, 190, 44)
            if b1.collidepoint(mx,my): self.start_game(); audio.play("click")
            elif b2.collidepoint(mx,my): self.state="menu"; save_system.save_game(self.save); audio.play("click")
        elif self.state=="paused":
            # draw_pause: box W//2-200,H//2-120,400,240 -> r = box.x+20, box.y+78+i*48, 360x38
            box = pygame.Rect(config.SCREEN_WIDTH//2-200, config.SCREEN_HEIGHT//2-120, 400, 240)
            for i in range(3):
                r = pygame.Rect(box.x+20, box.y+78 + i*48, box.width-40, 38)
                if r.collidepoint(mx,my):
                    if i==0: self.paused=False; audio.play("click")
                    elif i==1: self.state="settings"; self.prev_state="paused"; audio.play("click")
                    elif i==2: self.state="menu"; self.paused=False; save_system.save_game(self.save); audio.play("click")
                    break
        elif self.state=="settings":
            # draw_settings ile birebir: card 80,80,740,360; bar y=120+idx*62 bar 260,y+18 380x14
            card = pygame.Rect(80, 80, config.SCREEN_WIDTH-160, 360)
            for idx in range(3):
                y = 120 + idx*62
                bar = pygame.Rect(260, y+18, 380, 14)
                # bar ve knob çevresini büyüt (tıklaması kolay)
                hit = bar.inflate(0, 10)
                if hit.collidepoint(mx,my):
                    rel = round(max(0,min(1,(mx - bar.x)/bar.width)), 2)
                    key = ["master","music","sfx"][idx]
                    self.save["settings"][key]=rel
                    if key=="master": audio.set_master(rel)
                    elif key=="music": audio.set_music(rel)
                    elif key=="sfx": audio.set_sfx(rel)
                    save_system.save_game(self.save)
                    audio.play("hover",0.3)
            # tutorial checkbox draw: cb Rect(card.x+card.width-46,316) 22x22
            cb = pygame.Rect(card.x+card.width-46, 316, 22, 22)
            # toggle için tüm satır hit
            toggle_row = pygame.Rect(card.x+14, 306, card.width-28, 36)
            if toggle_row.collidepoint(mx,my) or cb.collidepoint(mx,my):
                cur = self.save["settings"].get("show_tutorial", True)
                self.save["settings"]["show_tutorial"]=not cur
                save_system.save_game(self.save)
                audio.play("click")
            # geri butonu draw: card.centerx-90, card.bottom-44 180x34
            back = pygame.Rect(card.centerx-90, card.bottom-44, 180, 34)
            if back.collidepoint(mx,my):
                if self.prev_state == "paused":
                    self.state = "playing"; self.paused = True
                else:
                    self.state = self.prev_state if self.prev_state in ("menu",) else "menu"
                audio.play("click")
        elif self.state=="shop":
            # tab hit
            tabs = ["SAPKA","CANTA","GOZLUK","BASTON"]
            tab_w=110; gap=12; total_w=len(tabs)*tab_w+(len(tabs)-1)*gap; start_x=config.SCREEN_WIDTH//2-total_w//2
            for i in range(len(tabs)):
                r=pygame.Rect(start_x+i*(tab_w+gap),68,tab_w,30)
                if r.collidepoint(mx,my):
                    self.shop_tab=i; self.shop_index=0; audio.play("click"); return
            # liste item hit
            lst,_ = self.current_shop_list()
            list_y=108
            for idx in range(len(lst)):
                y=list_y+idx*86; r=pygame.Rect(60,y,config.SCREEN_WIDTH-120,76)
                if r.collidepoint(mx,my):
                    self.shop_index=idx
                    # çift tık gibi: satın al/kuşan
                    lst2,key=self.current_shop_list()
                    item=lst2[idx]
                    owned=item["id"] in self.save["owned_items"]
                    sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                    if owned:
                        if self.save.get(sel_key)==item["id"]: self.save[sel_key]=None
                        else: self.save[sel_key]=item["id"]
                        save_system.save_game(self.save); audio.play("click")
                    else:
                        if self.save["total_coins"]>=item["price"]:
                            self.save["total_coins"]-=item["price"]; self.save["owned_items"].append(item["id"])
                            self.save[sel_key]=item["id"]; save_system.save_game(self.save); audio.play("coin")
                    break
        elif self.state=="characters":
            n=len(config.CHARACTERS); cols=6 if n>12 else 3
            if cols==6:
                card_w,card_h=135,118; gap_x,gap_y=10,12
            else:
                card_w,card_h=220,150; gap_x,gap_y=24,18
            start_x=config.SCREEN_WIDTH//2 - (cols*card_w + (cols-1)*gap_x)//2; start_y=88
            for idx,ch in enumerate(config.CHARACTERS):
                row=idx//cols; col=idx%cols
                x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y)
                r=pygame.Rect(x,y,card_w,card_h)
                if r.collidepoint(mx,my):
                    self.char_index=idx
                    if ch["id"] in self.save["unlocked_characters"]:
                        self.save["selected_character"]=ch["id"]; save_system.save_game(self.save); audio.play("click")
                    else: audio.play("death",0.4)
                    break
        elif self.state=="inventory":
            tabs=["SAPKA","CANTA","GOZLUK","BASTON"]
            tab_w=110; gap=12; total_w=len(tabs)*tab_w+(len(tabs)-1)*gap; start_x=config.SCREEN_WIDTH//2-total_w//2
            for i in range(len(tabs)):
                r=pygame.Rect(start_x+i*(tab_w+gap),68,tab_w,28)
                if r.collidepoint(mx,my):
                    self.inv_tab=i; self.inv_index=0; audio.play("click"); return
            tabs_key=["hat","bag","glasses","cane"]
            key=tabs_key[self.inv_tab]
            owned=[it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
            list_y=108
            for idx,item in enumerate(owned):
                y=list_y+idx*84; r=pygame.Rect(60,y,config.SCREEN_WIDTH-120,74)
                if r.collidepoint(mx,my):
                    self.inv_index=idx
                    sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                    if self.save.get(sel_key)==item["id"]: self.save[sel_key]=None
                    else: self.save[sel_key]=item["id"]
                    save_system.save_game(self.save); audio.play("click")
                    break
        elif self.state=="themes":
            cols=4; card_w,card_h=190,108; gap_x,gap_y=18,16
            start_x=config.SCREEN_WIDTH//2 - (cols*card_w+(cols-1)*gap_x)//2; start_y=88
            for idx,t in enumerate(config.THEMES):
                row=idx//cols; col=idx%cols
                x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y)
                r=pygame.Rect(x,y,card_w,card_h)
                if r.collidepoint(mx,my):
                    self.theme_index=idx; self.save["theme"]=t["id"]; save_system.save_game(self.save); audio.play("click"); break
        elif self.state=="levels":
            cols=4; card_w,card_h=190,92; gap_x,gap_y=14,12
            start_x=config.SCREEN_WIDTH//2 - (cols*card_w+(cols-1)*gap_x)//2; start_y=88
            for idx, e in enumerate(config.LEVELS):
                row=idx//cols; col=idx%cols
                x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y)
                r=pygame.Rect(x,y,card_w,card_h)
                if r.collidepoint(mx,my):
                    self.levels_index=idx
                    lvl=e["level"]
                    if lvl in self.save.get("unlocked_levels",[1]):
                        self.start_level(lvl)
                        audio.play("click")
                    else:
                        audio.play("death",0.4)
                    break
        elif self.state=="level_complete":
            # ortadaki butonlar: DEVAM (sonraki) ve MENÜ
            box = pygame.Rect(config.SCREEN_WIDTH//2-220, config.SCREEN_HEIGHT//2-110, 440, 220)
            b1 = pygame.Rect(box.x+20, box.bottom-52, 190, 38)
            b2 = pygame.Rect(box.x+230, box.bottom-52, 190, 38)
            if b1.collidepoint(mx,my) or b2.collidepoint(mx,my):
                data=self.level_complete_data or {}
                lvl=data.get("level",1)
                if b1.collidepoint(mx,my):
                    # sonraki bölüm
                    nxt=lvl+1
                    if nxt in self.save.get("unlocked_levels",[]):
                        self.start_level(nxt)
                    else:
                        self.state="levels"
                else:
                    self.state="levels"
                audio.play("click")
        elif self.state=="ending":
            self.state="menu"
            audio.play("click")
        elif self.state=="profile_create":
            box = pygame.Rect(config.SCREEN_WIDTH//2-260, config.SCREEN_HEIGHT//2-150, 520, 300)
            btn = pygame.Rect(box.centerx-110, box.y+210, 220, 44)
            inp = pygame.Rect(box.x+30, box.y+118, box.width-60, 46)
            if btn.collidepoint(mx,my):
                self._try_create_profile()
            elif inp.collidepoint(mx,my):
                pass  # focus (klavye zaten aktif)
        elif self.state=="play_select":
            for i in range(3):
                y = 132 + i*86
                r = pygame.Rect(config.SCREEN_WIDTH//2-200, y, 400, 68)
                if r.collidepoint(mx,my):
                    self.play_select_index=i
                    if i==0:
                        self.state="online_menu"
                        self._enter_online()
                        audio.play("click")
                    elif i==1:
                        self.start_vs_bot()
                        audio.play("click")
                    else:
                        self.state="menu"
                        audio.play("click")
                    break
        elif self.state=="online_menu":
            box = pygame.Rect(config.SCREEN_WIDTH//2-260, 106, 520, 306)
            btn = pygame.Rect(box.x+24, box.y+118, box.width-48, 42)
            if btn.collidepoint(mx,my):
                self._online_search()
            if self.online_info:
                mbtn = pygame.Rect(box.x+24, box.bottom-48, box.width-48, 36)
                if mbtn.collidepoint(mx,my):
                    self.start_vs_online()
            # geri — ESC ile de, ama ekstra tıklama: üst bar
        elif self.state in ("vs_bot","vs_online"):
            # ESC ile menü — click boş
            pass

    def handle_mouse_hover(self, pos):
        mx,my = pos
        if self.state=="menu":
            btn_w, btn_h = 320,42; start_y=182; gap=48
            for i in range(len(self.menu_options)):
                bx=config.SCREEN_WIDTH//2 - btn_w//2; by=start_y+i*gap
                if bx <= mx <= bx+btn_w and by <= my <= by+btn_h:
                    if self.hover_index != i:
                        self.hover_index=i
                        audio.play("hover",0.3)
                    return
            self.hover_index=-1

    # ---------- draw ----------
    def draw(self, surf):
        theme = next((t for t in config.THEMES if t["id"]==self.save.get("theme","beyaz")), config.THEMES[0])
        try:
            if self.state in ("playing","paused","gameover","level_complete","ending"):
                self.world.draw(surf, self.camera.y, self.level_info)
                # bölüm bitiş portalı — canavar modunda
                if self.level_mode is not None and self.level_target_px is not None:
                    finish_sy = int(self.level_target_px - self.camera.y)
                    if -60 <= finish_sy <= config.SCREEN_HEIGHT+60:
                        # portal — geniş ışıklı çizgi
                        portal_rect = pygame.Rect(28, finish_sy-8, config.SCREEN_WIDTH-56, 16)
                        gfx.draw_glow(surf, portal_rect.center, 40, (255,215,0), 30)
                        pygame.draw.rect(surf, (255,215,0), portal_rect, border_radius=8)
                        pygame.draw.rect(surf, (255,255,255), portal_rect, width=2, border_radius=8)
                        label = self.font_small.render("BÖLÜM BİTİŞİ →", True, (40,20,0))
                        surf.blit(label, (portal_rect.centerx - label.get_width()//2, portal_rect.y+1))
                        # oklar
                        for dx in [-36,-12,12,36]:
                            pygame.draw.polygon(surf, (255,255,255), [(portal_rect.centerx+dx, finish_sy-14),(portal_rect.centerx+dx-6, finish_sy-4),(portal_rect.centerx+dx+6, finish_sy-4)])
                # canavar — dünya sonrası, oyuncudan önce (arkadan gelir)
                if self.level_mode is not None and hasattr(self, 'monster'):
                    try:
                        self.monster.draw(surf, self.camera.y)
                    except: pass
                # atmosfer parçacıkları vs dünya çiziminden sonra ama oyuncudan önce
                self.particles.draw(surf, self.camera.y)
                self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
                self.draw_hud(surf, theme)
                # tutorial overlay
                if self.state=="playing" and not self.paused and self.save.get("settings",{}).get("show_tutorial",True) and not self.save.get("tutorial_done",False):
                    self.draw_tutorial(surf)
                if self.level_up_anim > 0:
                    self.draw_levelup(surf)
                # İzmir Marşı göstergesi
                if self.izmir_marsi_playing:
                    bar = pygame.Rect(config.SCREEN_WIDTH//2-140, 62, 280, 22)
                    s = pygame.Surface((bar.width, bar.height), pygame.SRCALPHA)
                    s.fill((200,20,30, 210))
                    surf.blit(s, bar.topleft)
                    pygame.draw.rect(surf, (255,215,0), bar, width=2, border_radius=8)
                    pygame.draw.rect(surf, (255,255,255), bar, width=1, border_radius=8)
                    txt = self.font_small.render("♫ İzmir Marşı ♫  (M ile kapat)", True, (255,255,255))
                    surf.blit(txt, (bar.centerx - txt.get_width()//2, bar.centery - txt.get_height()//2))
                    # küçük nota animasyonu
                    note_x = bar.x + 14 + int((pygame.time.get_ticks()/180) % (bar.width-28))
                    pygame.draw.circle(surf, (255,215,0), (note_x, bar.y-8), 4)
                if self.state=="paused" or self.paused:
                    self.draw_pause(surf, theme)
                if self.state=="gameover":
                    self.draw_gameover(surf, theme)
            elif self.state=="menu":
                self.draw_menu(surf, theme)
            elif self.state=="shop":
                self.draw_shop(surf, theme)
            elif self.state=="characters":
                self.draw_characters(surf, theme)
            elif self.state=="inventory":
                self.draw_inventory(surf, theme)
            elif self.state=="themes":
                self.draw_themes(surf, theme)
            elif self.state=="settings":
                self.draw_settings(surf, theme)
            elif self.state=="levels":
                self.draw_levels(surf, theme)
            elif self.state=="level_complete":
                # arka planı da çiz (donmuş oyun)
                self.world.draw(surf, self.camera.y, self.level_info)
                self.particles.draw(surf, self.camera.y)
                if hasattr(self, 'monster'):
                    try: self.monster.draw(surf, self.camera.y)
                    except: pass
                self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
                self.draw_hud(surf, theme)
                self.draw_level_complete(surf, theme)
            elif self.state=="ending":
                self.world.draw(surf, self.camera.y, self.level_info)
                self.particles.draw(surf, self.camera.y)
                if hasattr(self, 'monster'):
                    try: self.monster.draw(surf, self.camera.y)
                    except: pass
                self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
                self.draw_ending(surf, theme)
            elif self.state=="profile_create":
                self.draw_profile(surf, theme)
            elif self.state=="play_select":
                self.draw_play_select(surf, theme)
            elif self.state=="online_menu":
                self.draw_online(surf, theme)
            elif self.state in ("vs_bot","vs_online"):
                # VS yarış — aynı dünya + rakip
                self.world.draw(surf, self.camera.y, self.level_info)
                if hasattr(self, 'monster'):
                    try: self.monster.draw(surf, self.camera.y)
                    except: pass
                self.particles.draw(surf, self.camera.y)
                # rakip çiz (bot veya remote)
                if self.state=="vs_bot" and self.vs_bot:
                    try:
                        bot_char = getattr(self, 'vs_bot_char', self.get_char_data())
                        self.vs_bot.draw(surf, self.camera.y, bot_char, self.get_equipped(), theme)
                    except: pass
                elif self.state=="vs_online" and self.vs_remote:
                    try:
                        # remote ghost — basit rect
                        rx = int(self.vs_remote.get("x", self.player.x+30))
                        ry = int(self.vs_remote.get("y", self.player.y) - self.camera.y)
                        # ghost card
                        ghost_rect = pygame.Rect(rx, ry, self.player.w, self.player.h)
                        gfx.draw_glow(surf, ghost_rect.center, 18, (90,140,255), 22)
                        pygame.draw.rect(surf, (90,140,255), ghost_rect, border_radius=8)
                        pygame.draw.rect(surf, (0,0,0), ghost_rect, width=2, border_radius=8)
                        nick = self.vs_opponent_nick or "Rakip"
                        tag = self.font_tiny.render(nick, True, (255,255,255))
                        surf.blit(tag, (ghost_rect.centerx - tag.get_width()//2, ghost_rect.y - 14))
                    except: pass
                self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
                self.draw_hud(surf, theme)
                self.draw_vs_hud(surf, theme)
                if self.paused:
                    self.draw_pause(surf, theme)
        except Exception as e:
            print(f"[Draw error] {e}")
            surf.fill((20,20,20))
            err = self.font_small.render(f"Cizim hatasi: {e}", True, (255,80,80))
            surf.blit(err, (20,20))

        # transition fade (basit)
        if self.transition > 0:
            alpha = int(255 * self.transition)
            over = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
            over.fill((0,0,0, alpha//4))
            surf.blit(over, (0,0))

    def draw_hud(self, surf, theme):
        hud_h = 56
        # glass HUD — professional layered
        hud_surf = pygame.Surface((config.SCREEN_WIDTH, hud_h), pygame.SRCALPHA)
        gfx.vertical_gradient(hud_surf, (18,18,24), (10,10,16))
        surf.blit(hud_surf, (0,0))
        # soft bottom shadow
        sh = pygame.Surface((config.SCREEN_WIDTH, 8), pygame.SRCALPHA)
        for i in range(8):
            a=int(52*(1-i/8))
            pygame.draw.line(sh,(0,0,0,a),(0,i),(config.SCREEN_WIDTH,i))
        surf.blit(sh,(0,hud_h))
        pygame.draw.line(surf, (255,215,0, 200), (0, hud_h-1), (config.SCREEN_WIDTH, hud_h-1), 2)
        pygame.draw.line(surf, (255,255,255, 26), (0, 1), (config.SCREEN_WIDTH, 1), 1)
        dist_m = self.player.distance_px / config.PIXELS_PER_METER
        # seviye kutusu — glass + bevel
        lvl_bg = pygame.Rect(12, 8, 214, 24)
        gfx.draw_soft_shadow(surf, lvl_bg, radius=8, alpha=28)
        pygame.draw.rect(surf, (255,255,255, 18), lvl_bg, border_radius=8)
        pygame.draw.rect(surf, (255,215,0, 110), lvl_bg, width=1, border_radius=8)
        pygame.draw.line(surf,(255,255,255,42),(lvl_bg.x+8,lvl_bg.y+3),(lvl_bg.right-8,lvl_bg.y+3),1)
        txt1 = self.font_med.render(f"LVL {self.level} — {self.level_info['name']}", True, (255,218,70))
        surf.blit(txt1, (20, 11))
        txt2 = self.font_tiny.render(f"{dist_m:.1f} m  •  BEST {self.save.get('best_distance',0):.1f} m", True, (216,216,222))
        surf.blit(txt2, (18, 32))
        # coin kutusu sağ — gold bevel + glow
        coin_bg = pygame.Rect(config.SCREEN_WIDTH-196, 8, 186, 36)
        gfx.draw_soft_shadow(surf, coin_bg, radius=10, alpha=36)
        pygame.draw.rect(surf, (48,38,14), coin_bg, border_radius=9)
        pygame.draw.rect(surf, (255,215,0), coin_bg, width=2, border_radius=9)
        pygame.draw.line(surf,(255,255,255,56),(coin_bg.x+8,coin_bg.y+4),(coin_bg.right-8,coin_bg.y+4),1)
        gfx.draw_glow(surf, (coin_bg.x+22, coin_bg.centery), 16, (255,215,0), 40)
        pygame.draw.circle(surf, (255,215,0), (coin_bg.x+22, coin_bg.centery), 11)
        pygame.draw.circle(surf, (255,165,0), (coin_bg.x+22, coin_bg.centery), 11, 2)
        pygame.draw.circle(surf, (255,255,220), (coin_bg.x+19, coin_bg.centery-3), 4)
        pygame.draw.circle(surf, (255,255,255,120), (coin_bg.x+19, coin_bg.centery-3), 1)
        coin_txt = self.font_big.render(f"{self.save.get('total_coins',0)}", True, (255,255,255))
        surf.blit(coin_txt, (coin_bg.x+40, coin_bg.y+6))
        plus = self.font_small.render(f"+{self.player.coins}", True, (255,238,130))
        surf.blit(plus, (coin_bg.x+40+coin_txt.get_width()+8, coin_bg.y+13))
        # progress bar — shimmer (bölümde bitişe kadar, sonsuzda sonraki seviyeye)
        if self.level_mode is not None and self.level_target_px is not None:
            start_m = self.level_start_y / config.PIXELS_PER_METER
            target_m = self.level_target_px / config.PIXELS_PER_METER
            prog = (dist_m - start_m) / max(1, target_m - start_m)
            prog = max(0, min(1, prog))
            bar = pygame.Rect(14, hud_h-8, 220, 6)
            pygame.draw.rect(surf, (44,44,52), bar, border_radius=3)
            pygame.draw.rect(surf, (0,0,0,160), bar, width=1, border_radius=3)
            fill = pygame.Rect(bar.x+1, bar.y+1, int((bar.width-2)*prog), bar.height-2)
            if fill.width>0:
                for x in range(fill.width):
                    t=x/max(1,fill.width)
                    c=int(255*t + 180*(1-t))
                    h=int(255 - (1-t)*18)
                    pygame.draw.line(surf,(h,c,12),(fill.x+x, fill.y),(fill.x+x, fill.bottom))
                shimmer_x = int(fill.x + (pygame.time.get_ticks()*0.22)%fill.width) if fill.width>20 else fill.x
                pygame.draw.line(surf,(255,255,255,70),(shimmer_x, fill.y),(shimmer_x, fill.bottom),2)
            pygame.draw.rect(surf,(255,255,255,58), bar, width=1, border_radius=3)
            pct = self.font_tiny.render(f"{int(prog*100)}% → BİTİŞ", True, (255,222,70))
            surf.blit(pct, (bar.right+8, bar.y-3))
            # canavar mesafe uyarısı
            try:
                gap = self.player.y - self.monster.y
                # gap 220 ideal, <140 tehlikeli
                if gap < 180:
                    warn_col = (255,60,40) if gap < 120 else (255,180,40)
                    warn_bg = pygame.Rect(config.SCREEN_WIDTH//2-90, hud_h-22, 180, 16)
                    pygame.draw.rect(surf, (*warn_col, 180), warn_bg, border_radius=7)
                    pygame.draw.rect(surf, (0,0,0), warn_bg, width=1, border_radius=7)
                    warn_txt = self.font_tiny.render(f"! CANAVAR {int(gap)}px ARKANDA !", True, (255,255,255))
                    surf.blit(warn_txt, (warn_bg.centerx - warn_txt.get_width()//2, warn_bg.centery - warn_txt.get_height()//2))
                    if gap < 90:
                        # ekran kenarı kırmızı vignette
                        vig = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                        vig.fill((255,0,0, 22 + int(18*math.sin(pygame.time.get_ticks()*0.012))))
                        surf.blit(vig, (0,0))
            except: pass
        else:
            next_dist = None
            for e in config.LEVELS:
                if e["level"] == self.level+1:
                    next_dist = e["distance"]/100.0; break
            if next_dist:
                cur = dist_m
                prev_dist = next((x["distance"]/100 for x in config.LEVELS if x["level"]==self.level), 0)
                prog = (cur - prev_dist) / max(1, next_dist - prev_dist)
                prog = max(0, min(1, prog))
                bar = pygame.Rect(14, hud_h-8, 220, 6)
                pygame.draw.rect(surf, (44,44,52), bar, border_radius=3)
                pygame.draw.rect(surf, (0,0,0,160), bar, width=1, border_radius=3)
                fill = pygame.Rect(bar.x+1, bar.y+1, int((bar.width-2)*prog), bar.height-2)
                if fill.width>0:
                    for x in range(fill.width):
                        t=x/max(1,fill.width)
                        c=int(255*t + 180*(1-t))
                        h=int(255 - (1-t)*18)
                        pygame.draw.line(surf,(h,c,12),(fill.x+x, fill.y),(fill.x+x, fill.bottom))
                    shimmer_x = int(fill.x + (pygame.time.get_ticks()*0.22)%fill.width) if fill.width>20 else fill.x
                    pygame.draw.line(surf,(255,255,255,70),(shimmer_x, fill.y),(shimmer_x, fill.bottom),2)
                pygame.draw.rect(surf,(255,255,255,58), bar, width=1, border_radius=3)
                pct = self.font_tiny.render(f"{int(prog*100)}%", True, (255,222,70))
                surf.blit(pct, (bar.right+8, bar.y-3))
        # ortada kontrol ipucu — subtle pill
        hint_bg = pygame.Rect(config.SCREEN_WIDTH//2-152, 30, 304, 17)
        pygame.draw.rect(surf,(0,0,0, 88), hint_bg, border_radius=9)
        pygame.draw.rect(surf,(255,255,255,18), hint_bg, width=1, border_radius=9)
        pause_hint = self.font_tiny.render("SPACE Pause  •  ↑ Jump  •  ↓ Roll  •  H Tutorial", True, (196,196,202))
        surf.blit(pause_hint, (config.SCREEN_WIDTH//2 - pause_hint.get_width()//2, 33))

    def draw_tutorial(self, surf):
        box = pygame.Rect(18, 62, 286, 96)
        gfx.draw_soft_shadow(surf, box, radius=12, alpha=32)
        gfx.glass_panel(surf, box, fill=(255,255,242,230), border=(0,0,0,160), radius=11)
        title = self.font_small.render("NASIL OYNANIR?  (H ile kapat)", True, (22,22,22))
        surf.blit(title, (box.x+12, box.y+10))
        pygame.draw.line(surf,(0,0,0,18),(box.x+10, box.y+26),(box.right-10, box.y+26),1)
        lines = ["← → : Hareket  — akıcı, ivmeli", "↑ : Zıpla (engel üstünde)", "↓ : Hızlı düş / Yuvarlan", "Boşluklardan süzül — sıkışma!"]
        y = box.y+30
        for l in lines:
            dot = self.font_tiny.render("• "+l, True, (48,48,48))
            surf.blit(dot, (box.x+12, y)); y+=14

    def draw_levelup(self, surf):
        t = self.level_up_anim / 2.2
        a = int(255 * min(1, t*1.25))
        banner_h = 74
        banner = pygame.Rect(20, config.SCREEN_HEIGHT//2 - 90, config.SCREEN_WIDTH-40, banner_h)
        # glow behind
        gfx.draw_glow(surf, banner.center, 90, (255,215,0), int(42*t))
        # glass banner
        gfx.draw_soft_shadow(surf, banner, radius=18, alpha=int(36*t))
        sh = pygame.Surface((banner.width, banner.height), pygame.SRCALPHA)
        sh.fill((255,218,70, int(236*t)))
        surf.blit(sh, banner.topleft)
        # bevel
        pygame.draw.rect(surf,(255,255,255, int(120*t)), banner, width=2, border_radius=10)
        pygame.draw.rect(surf,(0,0,0, int(200*t)), banner, width=2, border_radius=10)
        pygame.draw.line(surf,(255,255,255, int(90*t)),(banner.x+10,banner.y+6),(banner.right-10,banner.y+6),2)
        title = self.font_big.render(f"SEVIYE {self.level}!  {self.level_info['name']}", True, (22,18,6))
        surf.blit(title, (banner.centerx - title.get_width()//2, banner.y+12))
        if self.just_unlocked:
            sub_bg = pygame.Rect(banner.centerx-160, banner.y+40, 320, 20)
            pygame.draw.rect(surf,(0,0,0, int(140*t)), sub_bg, border_radius=8)
            t2 = self.font_small.render(f"Yeni karakter: {self.just_unlocked}!", True, (255,255,255))
            surf.blit(t2, (banner.centerx - t2.get_width()//2, banner.y+42))
        if int(self.level_up_anim*10)%2==0 and t>0.4:
            pygame.draw.rect(surf,(255,255,255, int(160*t)), banner, width=2, border_radius=10)

    def draw_pause(self, surf, theme):
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,148))
        surf.blit(overlay, (0,0))
        gfx.draw_vignette(surf, intensity=0.22)
        box = pygame.Rect(config.SCREEN_WIDTH//2-210, config.SCREEN_HEIGHT//2-124, 420, 248)
        gfx.draw_soft_shadow(surf, box, radius=22, alpha=64)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=16)
        t = self.font_big.render("DURDURULDU", True, (18,18,20))
        surf.blit(t, (box.centerx - t.get_width()//2, box.y+20))
        pygame.draw.line(surf,(0,0,0,14),(box.x+18, box.y+50),(box.right-18, box.y+50),1)
        hint = self.font_small.render(f"Mesafe: {self.player.distance_px/config.PIXELS_PER_METER:.1f} m  •  Coin: {self.player.coins}", True, (86,86,90))
        surf.blit(hint, (box.centerx - hint.get_width()//2, box.y+56))
        btns = [("DEVAM ET  (SPACE)", 0), ("AYARLAR", 1), ("ANA MENU", 2)]
        mx,my = pygame.mouse.get_pos()
        for i,(label,_) in enumerate(btns):
            r = pygame.Rect(box.x+22, box.y+82 + i*50, box.width-44, 40)
            hover = r.collidepoint(mx,my)
            base = (92,208,92) if i==0 else (36,36,40)
            top = tuple(min(255,c+28) for c in base)
            hover_col = (255,218,70) if hover else base
            # use button helper for bevel
            gfx.draw_soft_shadow(surf, r, radius=10, alpha=22 if hover else 14)
            # gradient
            btn_surf = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            for y in range(r.height):
                ts = y/r.height
                col = tuple(int(top[k]*(1-ts)+base[k]*ts) for k in range(3)) if not hover else (255,218,70) if y<r.height//2 else (255,192,0)
                pygame.draw.line(btn_surf, col,(0,y),(r.width,y))
            mask = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            pygame.draw.rect(mask,(255,255,255),(0,0,r.width,r.height), border_radius=10)
            btn_surf.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(btn_surf, r.topleft)
            pygame.draw.rect(surf,(0,0,0,160), r, width=2, border_radius=10)
            if hover:
                gfx.draw_glow(surf, r.center, 18, (255,215,0), 22)
                pygame.draw.rect(surf,(255,215,0), r, width=2, border_radius=10)
            txt = self.font_med.render(label, True, (0,0,0) if hover or i==0 else (255,255,255))
            surf.blit(txt, (r.centerx - txt.get_width()//2, r.centery - txt.get_height()//2))

    def draw_gameover(self, surf, theme):
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,178))
        surf.blit(overlay, (0,0))
        gfx.draw_vignette(surf, intensity=0.30)
        box = pygame.Rect(config.SCREEN_WIDTH//2-252, config.SCREEN_HEIGHT//2-172, 504, 364)
        gfx.draw_soft_shadow(surf, box, radius=24, alpha=70)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(44,0,0,120), radius=18)
        # top red accent
        pygame.draw.rect(surf,(200,36,36), pygame.Rect(box.x, box.y, box.width, 6), border_radius=4)
        title = self.font_huge.render("GAME OVER", True, (192,18,18))
        sh = self.font_huge.render("GAME OVER", True, (0,0,0,44))
        surf.blit(sh, (box.centerx - title.get_width()//2+2, box.y+18))
        surf.blit(title, (box.centerx - title.get_width()//2, box.y+16))
        sub = self.font_small.render("Sıkıştın! Tek can hakkın vardı.", True, (96,96,96))
        surf.blit(sub, (box.centerx - sub.get_width()//2, box.y+66))
        dist = self.player.distance_px / config.PIXELS_PER_METER
        is_new_record = dist >= self.save.get("best_distance",0)-0.01 and dist>1
        if is_new_record and dist>0:
            rec_bg = pygame.Rect(box.centerx-122, box.y+88, 244, 28)
            pygame.draw.rect(surf,(255,215,0), rec_bg, border_radius=8)
            pygame.draw.rect(surf,(0,0,0,140), rec_bg, width=2, border_radius=8)
            rec = self.font_big.render("★ YENİ REKOR! ★", True, (22,12,0))
            surf.blit(rec, (box.centerx - rec.get_width()//2, box.y+92))
            dy = 128
        else:
            dy = 100
        # stats card
        card = pygame.Rect(box.x+22, box.y+dy, box.width-44, 112)
        pygame.draw.rect(surf,(245,245,248), card, border_radius=11)
        pygame.draw.rect(surf,(0,0,0,18), card, width=1, border_radius=11)
        dtxt = self.font_big.render(f"Mesafe: {dist:.1f} m", True, (18,18,20))
        surf.blit(dtxt, (box.centerx - dtxt.get_width()//2, box.y+dy+10))
        mid = "  •  ".join([f"En İyi: {self.save.get('best_distance',0):.1f} m", f"Coin: +{self.player.coins}", f"Toplam: {self.save.get('total_coins',0)}"])
        ctxt = self.font_small.render(mid, True, (92,72,16))
        surf.blit(ctxt, (box.centerx - ctxt.get_width()//2, box.y+dy+42))
        ltxt = self.font_small.render(f"Seviye: {self.level} ({self.level_info['name']})", True, (88,88,92))
        surf.blit(ltxt, (box.centerx - ltxt.get_width()//2, box.y+dy+68))
        # buttons — bevel + glow
        b1 = pygame.Rect(box.x+52, box.y+290, 190, 46)
        b2 = pygame.Rect(box.x+262, box.y+290, 190, 46)
        mx,my = pygame.mouse.get_pos()
        for b, txt in [(b1,"TEKRAR OYNA"), (b2,"ANA MENÜ")]:
            hover = b.collidepoint(mx,my)
            base = (28,148,68) if txt=="TEKRAR OYNA" else (48,48,54)
            top = tuple(min(255,c+26) for c in base)
            hover_base = (36,168,78) if txt=="TEKRAR OYNA" else (72,72,80)
            col = hover_base if hover else base
            gfx.draw_soft_shadow(surf, b, radius=10, alpha=28 if hover else 18)
            btn = pygame.Surface((b.width,b.height), pygame.SRCALPHA)
            for y in range(b.height):
                ts=y/b.height
                r=int((hover_base if hover else top)[0]*(1-ts)+col[0]*ts) if False else None
                # simple gradient
                rr=int(top[0]*(1-ts)+col[0]*ts) if not hover else int((255 if txt=="TEKRAR OYNA" else 96)*(1-ts)+col[0]*ts)
                gg=int(top[1]*(1-ts)+col[1]*ts) if not hover else int((220 if txt=="TEKRAR OYNA" else 96)*(1-ts)+col[1]*ts)
                bb=int(top[2]*(1-ts)+col[2]*ts) if not hover else int((40 if txt=="TEKRAR OYNA" else 96)*(1-ts)+col[2]*ts)
                if hover and txt=="TEKRAR OYNA":
                    rr,gg,bb = int(42+(255-42)*(1-ts)), int(180+(220-180)*(1-ts)), int(72+(40-72)*(1-ts))
                pygame.draw.line(btn,(rr,gg,bb),(0,y),(b.width,y))
            m2=pygame.Surface((b.width,b.height), pygame.SRCALPHA)
            pygame.draw.rect(m2,(255,255,255),(0,0,b.width,b.height), border_radius=10)
            btn.blit(m2,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(btn,b.topleft)
            pygame.draw.rect(surf,(0,0,0,160), b, width=2, border_radius=10)
            if hover:
                gfx.draw_glow(surf,b.center,18,(255,215,0),24)
                pygame.draw.rect(surf,(255,215,0),b,width=2,border_radius=10)
            t = self.font_med.render(txt, True, (255,255,255))
            surf.blit(t, (b.centerx - t.get_width()//2, b.centery - t.get_height()//2))
        hint = self.font_small.render("R / SPACE : Tekrar  •  M / ESC : Menü", True, (112,112,116))
        surf.blit(hint, (box.centerx - hint.get_width()//2, box.y+340))

    def draw_menu(self, surf, theme):
        # zengin gradient bg + vignette
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        gfx.draw_vignette(surf, intensity=0.13 if theme["id"]=="beyaz" else 0.22)
        # subtle top glow
        glow = pygame.Surface((config.SCREEN_WIDTH, 180), pygame.SRCALPHA)
        for i in range(90):
            a=int(16*(1-i/90))
            pygame.draw.line(glow,(255,255,255,a),(0,i),(config.SCREEN_WIDTH,i))
        surf.blit(glow,(0,0))
        # başlık — 3D extrusion
        title = self.font_huge.render("FREEFALL", True, theme["hud"])
        for off, col in [(3,(0,0,0,64)),(2,(0,0,0,92))]:
            sh = self.font_huge.render("FREEFALL", True, (0,0,0))
            sh.set_alpha(col[3] if len(col)==4 else 80)
            surf.blit(sh, (config.SCREEN_WIDTH//2 - title.get_width()//2 + off, 44+off))
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 42))
        gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, 62), 56, (255,215,0), 18 if theme["id"]!="siyah" else 10)
        sub = self.font_med.render("Dikey Düşüş  —  Aşağı İn, Sıkışma, Hayatta Kal", True, theme["hud"])
        surf.blit(sub, (config.SCREEN_WIDTH//2 - sub.get_width()//2, 92))
        # info pill — glass
        info_text = f"COIN: {self.save.get('total_coins',0)}   •   SEVİYE: {self.save.get('level',1)}   •   En İyi: {self.save.get('best_distance',0):.1f} m   •   {self.get_char_data()['name']}"
        info = self.font_small.render(info_text, True, (255,255,255) if theme["id"] in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (30,30,34))
        pill = pygame.Rect(config.SCREEN_WIDTH//2 - info.get_width()//2 -16, 120, info.get_width()+32, 22)
        bg_col = (255,255,255,22) if theme["id"]=="beyaz" else (0,0,0,42) if "siyah" in theme["id"] else (255,255,255,26)
        pygame.draw.rect(surf, bg_col if len(bg_col)==4 else bg_col, pill, border_radius=8)
        pygame.draw.rect(surf,(255,255,255,24) if theme["id"]!="beyaz" else (0,0,0,16), pill, width=1, border_radius=8)
        surf.blit(info, (pill.centerx - info.get_width()//2, pill.centery - info.get_height()//2))
        # profil rozeti — nick + 5 haneli ID
        nick = self.save.get("nickname") or "?"
        pid = self.save.get("player_id") or "?????"
        prof_txt = f"{nick}  •  ID: {pid}"
        prof = self.font_small.render(prof_txt, True, (255,255,255) if "siyah" in theme["id"] else (30,30,34))
        prof_box = pygame.Rect(config.SCREEN_WIDTH- prof.get_width()-28, 8, prof.get_width()+16, 22)
        pygame.draw.rect(surf, (0,0,0,48) if "siyah" in theme["id"] else (255,255,255,200), prof_box, border_radius=8)
        pygame.draw.rect(surf, (255,215,0,90), prof_box, width=1, border_radius=8)
        surf.blit(prof, (prof_box.centerx - prof.get_width()//2, prof_box.centery - prof.get_height()//2))
        # mini karakter önizleme — glass card
        ch = self.get_char_data()
        eq = self.get_equipped()
        preview_box = pygame.Rect(config.SCREEN_WIDTH//2 - 76, 148, 152, 38)
        gfx.draw_soft_shadow(surf, preview_box, radius=10, alpha=22)
        gfx.glass_panel(surf, preview_box, fill=(255,255,255,210) if theme["id"]=="beyaz" else (38,38,44,210), border=(0,0,0,36), radius=9)
        cx = preview_box.centerx; cy = preview_box.centery
        gfx.draw_glow(surf,(cx,cy-4),14,ch["accent"],22)
        pygame.draw.rect(surf, ch["color"], pygame.Rect(cx-13, cy-8, 26, 19), border_radius=5)
        pygame.draw.rect(surf,(0,0,0,160), pygame.Rect(cx-13, cy-8, 26, 19), width=1, border_radius=5)
        pygame.draw.circle(surf, (255,220,180), (cx, cy-12), 9)
        pygame.draw.circle(surf,(0,0,0,160),(cx, cy-12), 9, 1)
        if eq["hat"]:
            pygame.draw.rect(surf, (200,30,30), pygame.Rect(cx-11, cy-21, 22, 6), border_radius=3)
        btn_w, btn_h = 326, 44; start_y = 194; gap = 50
        mx,my = pygame.mouse.get_pos()
        for i, opt in enumerate(self.menu_options):
            bx = config.SCREEN_WIDTH//2 - btn_w//2; by = start_y + i*gap
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            hover = rect.collidepoint(mx,my)
            selected = i==self.menu_index
            is_exit = opt=="CIKIS"
            base = theme["button"]
            # selected → gold gradient
            if selected or hover:
                # soft shadow
                gfx.draw_soft_shadow(surf, rect, radius=12, alpha=26)
                # gold bevel for selected
                top = (255,228,110) if selected else tuple(min(255,c+18) for c in base)
                bot = (255,185,0) if selected else tuple(max(0,c-14) for c in base)
                btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                for y in range(rect.height):
                    ts=y/rect.height
                    rr=int(top[0]*(1-ts)+bot[0]*ts); gg=int(top[1]*(1-ts)+bot[1]*ts); bb=int(top[2]*(1-ts)+bot[2]*ts)
                    pygame.draw.line(btn_surf,(rr,gg,bb),(0,y),(rect.width,y))
                mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                pygame.draw.rect(mask,(255,255,255),(0,0,rect.width,rect.height), border_radius=11)
                btn_surf.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
                surf.blit(btn_surf, rect.topleft)
                pygame.draw.rect(surf,(255,215,0) if selected else (255,255,255,140), rect, width=3 if selected else 2, border_radius=11)
                pygame.draw.line(surf,(255,255,255,92),(rect.x+10,rect.y+5),(rect.right-10,rect.y+5),1)
                if selected:
                    gfx.draw_glow(surf, rect.center, 20, (255,215,0), 22)
                    arrow = self.font_med.render("►", True, (255,215,0,220))
                    # glow arrow
                    surf.blit(arrow, (bx-26, rect.centery - arrow.get_height()//2))
            else:
                pygame.draw.rect(surf, base, rect, border_radius=11)
                pygame.draw.rect(surf,(0,0,0,110), rect, width=2, border_radius=11)
                pygame.draw.line(surf,(255,255,255,44),(rect.x+10,rect.y+5),(rect.right-10,rect.y+5),1)
            txt_col = (28,18,4) if (selected or hover) else ((255,255,255) if theme["id"] in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (30,30,34))
            if is_exit and not (selected or hover):
                txt_col=(168,24,24) if "siyah" not in theme["id"] else (255,104,104)
            t = self.font_med.render(opt, True, txt_col)
            surf.blit(t, (rect.centerx - t.get_width()//2, rect.centery - t.get_height()//2))
        hint = self.font_small.render("↑↓ Seç  •  ENTER/SPACE Onayla  •  Mouse & Scroll", True, (theme["hud"][0],theme["hud"][1],theme["hud"][2], 210) if len(theme["hud"])==3 else theme["hud"])
        # ensure tuple
        hint_col = tuple(max(0,min(255,c)) for c in theme["hud"]) if isinstance(theme["hud"],(list,tuple)) else (30,30,30)
        hint_col = (hint_col[0],hint_col[1],hint_col[2])
        hint_surf = self.font_small.render("↑↓ Seç  •  ENTER/SPACE Onayla  •  Mouse & Scroll", True, hint_col)
        hint_surf.set_alpha(180)
        surf.blit(hint_surf, (config.SCREEN_WIDTH//2 - hint_surf.get_width()//2, config.SCREEN_HEIGHT-28))
        ver = self.font_tiny.render("v1.2  •  Tek Can  •  Sonsuz Dünya  •  60 FPS", True, hint_col)
        ver.set_alpha(140)
        surf.blit(ver, (10, config.SCREEN_HEIGHT-15))
        # İzmir Marşı ipucu
        mars_hint = self.font_tiny.render("M: ♫ İzmir Marşı", True, hint_col)
        mars_hint.set_alpha(170)
        # seçiliyse vurgula
        if self.izmir_marsi_playing:
            mars_hint = self.font_tiny.render("M: ♫ Çalıyor... (tekrar M)", True, (200,20,30))
        surf.blit(mars_hint, (config.SCREEN_WIDTH - mars_hint.get_width() - 10, config.SCREEN_HEIGHT-15))

    def draw_shop(self, surf, theme):
        surf.fill(theme["bg"])
        title = self.font_big.render("MAGAZA", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        coin = self.font_med.render(f"COIN: {self.save['total_coins']}", True, (120,90,0))
        surf.blit(coin, (config.SCREEN_WIDTH-160, 18))
        hint = self.font_small.render("←→ Kategori  |  ↑↓ Sec  |  ENTER Satın Al/Kuşan  |  ESC Menu", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 46))
        tabs = ["SAPKA","CANTA","GOZLUK","BASTON"]
        tab_w = 110; gap=12; total_w=len(tabs)*tab_w+(len(tabs)-1)*gap; start_x=config.SCREEN_WIDTH//2-total_w//2
        mx,my = pygame.mouse.get_pos()
        for i,t in enumerate(tabs):
            r=pygame.Rect(start_x+i*(tab_w+gap), 68, tab_w, 30)
            sel=i==self.shop_tab
            col=theme["button_hover"] if sel else theme["button"]
            if r.collidepoint(mx,my) and not sel:
                col = theme["button_hover"]
            pygame.draw.rect(surf, col, r, border_radius=8)
            pygame.draw.rect(surf, (0,0,0), r, width=2, border_radius=8)
            if sel: pygame.draw.rect(surf, (255,215,0), r, width=3, border_radius=8)
            txt=self.font_small.render(t, True, (0,0,0) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (255,255,255))
            surf.blit(txt, (r.centerx - txt.get_width()//2, r.centery - txt.get_height()//2))
        lst,key = self.current_shop_list()
        list_y=108
        for idx,item in enumerate(lst):
            y=list_y+idx*86
            r=pygame.Rect(60, y, config.SCREEN_WIDTH-120, 76)
            sel=idx==self.shop_index
            # shadow + bevel polish
            gfx.draw_soft_shadow(surf, r, radius=10, alpha=22 if sel else 14)
            col=(255,255,210) if sel else (255,255,255)
            if theme["id"] in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi"):
                col=(62,62,64) if not sel else (84,84,58)
            pygame.draw.rect(surf, col, r, border_radius=11)
            pygame.draw.rect(surf, (0,0,0,150), r, width=2, border_radius=11)
            if sel:
                gfx.draw_glow(surf, r.center, 16, (255,215,0), 18)
                pygame.draw.rect(surf, (255,215,0), r, width=3, border_radius=11)
            pygame.draw.line(surf,(255,255,255,52),(r.x+10,r.y+5),(r.right-10,r.y+5),1)
            icon_r=pygame.Rect(r.x+12, r.y+11, 54, 54)
            gfx.draw_soft_shadow(surf, icon_r, radius=6, alpha=18)
            pygame.draw.rect(surf, (242,242,245), icon_r, border_radius=9)
            pygame.draw.rect(surf, (0,0,0,120), icon_r, width=1, border_radius=9)
            gfx.draw_glow(surf, icon_r.center, 10, (255,215,0), 14 if item["id"] in self.save["owned_items"] else 6)
            ic=self.font_big.render(item["icon"], True, (28,28,30))
            surf.blit(ic, (icon_r.centerx-ic.get_width()//2, icon_r.centery-ic.get_height()//2))
            name=self.font_med.render(item["name"], True, (18,18,22) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (238,238,242))
            surf.blit(name, (r.x+80, r.y+14))
            owned=item["id"] in self.save["owned_items"]
            if owned:
                sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                using=self.save.get(sel_key)==item["id"]
                status="● KULLANILIYOR" if using else "SATIN ALINDI — ENTER ile Kuşan"
                col_s=(16,148,52) if using else (92,92,96)
                st=self.font_small.render(status, True, col_s)
                surf.blit(st, (r.x+80, r.y+40))
                pill=pygame.Rect(r.right-118, r.y+12, 104, 22)
                pygame.draw.rect(surf,(40,168,70) if using else (62,62,66), pill, border_radius=7)
                price=self.font_small.render("Sahip Olunuyor", True, (255,255,255))
                surf.blit(price, (pill.centerx - price.get_width()//2, pill.centery - price.get_height()//2))
            else:
                enough=self.save["total_coins"]>=item["price"]
                pill=pygame.Rect(r.right-110, r.y+12, 96, 24)
                pygame.draw.rect(surf,(22,144,60) if enough else (168,32,32), pill, border_radius=7)
                pygame.draw.rect(surf,(0,0,0,90), pill, width=1, border_radius=7)
                price=self.font_med.render(f"{item['price']}  C", True, (255,255,255))
                surf.blit(price, (pill.centerx - price.get_width()//2, pill.centery - price.get_height()//2))
                can="ENTER ile Satın Al" if enough else "Yetersiz Coin"
                st=self.font_small.render(can, True, (58,58,62) if enough else (168,32,32))
                surf.blit(st, (r.x+80, r.y+42))
                if enough:
                    # tiny coin icon
                    pygame.draw.circle(surf,(255,215,0),(r.x+82+self.font_small.size(can)[0]+10, r.y+48),5)
                    pygame.draw.circle(surf,(255,165,0),(r.x+82+self.font_small.size(can)[0]+10, r.y+48),5,1)

    def draw_characters(self, surf, theme):
        surf.fill(theme["bg"])
        title=self.font_big.render("KARAKTERLER", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint=self.font_small.render("Yön: Sec  |  ENTER: Seç  |  ESC: Menu", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 42))
        info=self.font_small.render(f"Seviye: {self.save.get('level',1)}  |  Seçili: {self.get_char_data()['name']}", True, theme["hud"])
        surf.blit(info, (config.SCREEN_WIDTH//2 - info.get_width()//2, 62))
        n=len(config.CHARACTERS)
        if n > 12:
            cols=6; card_w,card_h=135,118; gap_x,gap_y=10,12
        else:
            cols=3; card_w,card_h=220,150; gap_x,gap_y=24,18
        start_x=config.SCREEN_WIDTH//2 - (cols*card_w + (cols-1)*gap_x)//2; start_y=88
        for idx,ch in enumerate(config.CHARACTERS):
            row=idx//cols; col=idx%cols
            x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y)
            r=pygame.Rect(x,y,card_w,card_h)
            unlocked=ch["id"] in self.save["unlocked_characters"]
            selected_char=self.save.get("selected_character")==ch["id"]
            is_cursor=idx==self.char_index
            bg_col=(255,255,255) if unlocked else (150,150,150)
            if theme["id"] in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi"):
                bg_col=(52,52,56) if unlocked else (38,38,40)
            gfx.draw_soft_shadow(surf, r, radius=10, alpha=22 if is_cursor else 14)
            pygame.draw.rect(surf, bg_col, r, border_radius=11)
            pygame.draw.rect(surf, (0,0,0,140), r, width=2, border_radius=11)
            if selected_char:
                gfx.draw_glow(surf, r.center, 18, (0,180,0), 18)
                pygame.draw.rect(surf, (0,186,70), r, width=4, border_radius=11)
            if is_cursor:
                gfx.draw_glow(surf, r.center, 16, (255,215,0), 18)
                pygame.draw.rect(surf, (255,215,0), r, width=3, border_radius=11)
            pygame.draw.line(surf,(255,255,255,38),(r.x+10,r.y+5),(r.right-10,r.y+5),1)
            preview_r=pygame.Rect(r.x+14, r.y+14, 52, 52)
            pygame.draw.rect(surf, ch["color"], preview_r, border_radius=8)
            pygame.draw.rect(surf, (0,0,0), preview_r, width=2, border_radius=8)
            pygame.draw.circle(surf, ch["accent"], (preview_r.right-10, preview_r.bottom-10), 7)
            # kafa ikonu
            pygame.draw.circle(surf, (255,220,180), (preview_r.centerx, preview_r.centery+2), 9)
            name=self.font_med.render(ch["name"], True, (0,0,0) if unlocked and theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (230,230,230) if unlocked else (80,80,80))
            surf.blit(name, (r.x+78, r.y+16))
            if unlocked:
                st=self.font_small.render("✓ SEÇİLİ" if selected_char else "AÇIK — ENTER ile Seç", True, (0,130,0) if selected_char else (0,110,0))
                surf.blit(st, (r.x+78, r.y+42))
            else:
                st=self.font_small.render(f"🔒 Seviye {ch['level']}", True, (150,0,0))
                surf.blit(st, (r.x+78, r.y+42))
                pygame.draw.rect(surf, (80,80,80), pygame.Rect(preview_r.centerx-8, preview_r.centery-1, 16, 12), border_radius=3)
                pygame.draw.circle(surf, (60,60,60), (preview_r.centerx, preview_r.centery-4), 6, 2)
            desc=self.font_tiny.render(f"Seviye {ch['level']} ile açılır", True, (90,90,90))
            surf.blit(desc, (r.x+14, r.y+84))
            if selected_char:
                eq=self.get_equipped()
                cosmetic=[]
                if eq["hat"]: cosmetic.append("Şapka")
                if eq["glasses"]: cosmetic.append("Gözlük")
                if eq["bag"]: cosmetic.append("Çanta")
                if eq["cane"]: cosmetic.append("Baston")
                cos_txt=", ".join(cosmetic) if cosmetic else "Kozmetik yok"
                ct=self.font_tiny.render(cos_txt, True, (60,60,60))
                surf.blit(ct, (r.x+14, r.y+106))

    def draw_inventory(self, surf, theme):
        surf.fill(theme["bg"])
        title=self.font_big.render("ENVANTER", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint=self.font_small.render("←→ Kategori  |  ↑↓ Seç  |  ENTER Kuşan/Çıkar  |  ESC Menu", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 44))
        tabs=["SAPKA","CANTA","GOZLUK","BASTON"]
        tab_w=110; gap=12; total_w=len(tabs)*tab_w+(len(tabs)-1)*gap; start_x=config.SCREEN_WIDTH//2-total_w//2
        for i,t in enumerate(tabs):
            r=pygame.Rect(start_x+i*(tab_w+gap),68,tab_w,28)
            sel=i==self.inv_tab
            col=theme["button_hover"] if sel else theme["button"]
            pygame.draw.rect(surf,col,r,border_radius=8)
            pygame.draw.rect(surf,(0,0,0),r,width=2,border_radius=8)
            if sel: pygame.draw.rect(surf,(255,215,0),r,width=3,border_radius=8)
            txt=self.font_small.render(t, True, (0,0,0) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (255,255,255))
            surf.blit(txt, (r.centerx-txt.get_width()//2, r.centery-txt.get_height()//2))
        tabs_key=["hat","bag","glasses","cane"]
        key=tabs_key[self.inv_tab]
        owned=[it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
        sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
        if not owned:
            msg=self.font_med.render("Bu kategoride eşyan yok — Mağazaya git!", True, theme["hud"])
            surf.blit(msg, (config.SCREEN_WIDTH//2 - msg.get_width()//2, 220))
            tip=self.font_small.render("Coin topla ve Mağazadan satın al", True, theme["hud"])
            surf.blit(tip, (config.SCREEN_WIDTH//2 - tip.get_width()//2, 250))
        else:
            list_y=108
            for idx,item in enumerate(owned):
                y=list_y+idx*84
                r=pygame.Rect(60,y,config.SCREEN_WIDTH-120,74)
                sel=idx==self.inv_index
                col=(255,255,210) if sel else (255,255,255)
                if theme["id"] in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi"):
                    col=(60,60,60) if not sel else (80,80,50)
                pygame.draw.rect(surf,col,r,border_radius=10)
                pygame.draw.rect(surf,(0,0,0),r,width=2,border_radius=10)
                if sel: pygame.draw.rect(surf,(255,215,0),r,width=3,border_radius=10)
                icon_r=pygame.Rect(r.x+12,r.y+10,54,54)
                pygame.draw.rect(surf,(240,240,240),icon_r,border_radius=8)
                pygame.draw.rect(surf,(0,0,0),icon_r,width=1,border_radius=8)
                ic=self.font_big.render(item["icon"], True, (0,0,0))
                surf.blit(ic, (icon_r.centerx-ic.get_width()//2, icon_r.centery-ic.get_height()//2))
                name=self.font_med.render(item["name"], True, (0,0,0) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (255,255,255))
                surf.blit(name, (r.x+80,r.y+14))
                using=self.save.get(sel_key)==item["id"]
                st=self.font_small.render("● KULLANILIYOR" if using else "ENTER ile Kuşan", True, (0,150,0) if using else (90,90,90))
                surf.blit(st, (r.x+80,r.y+40))

    def draw_themes(self, surf, theme):
        surf.fill(theme["bg"])
        title=self.font_big.render("TEMALAR", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint=self.font_small.render("Yön: Seç  |  ENTER: Uygula  |  ESC: Menu", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 42))
        cur_txt=self.font_small.render(f"Seçili: {theme['name']}", True, theme["hud"])
        surf.blit(cur_txt, (config.SCREEN_WIDTH//2 - cur_txt.get_width()//2, 62))
        cols=4; card_w,card_h=190,110; gap_x,gap_y=18,16
        start_x=config.SCREEN_WIDTH//2 - (cols*card_w+(cols-1)*gap_x)//2; start_y=88
        for idx,t in enumerate(config.THEMES):
            row=idx//cols; col=idx%cols
            x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y)
            r=pygame.Rect(x,y,card_w,card_h)
            is_cur=t["id"]==self.save.get("theme","beyaz")
            is_cursor=idx==self.theme_index
            gfx.draw_soft_shadow(surf, r, radius=10, alpha=22 if is_cursor or is_cur else 14)
            pygame.draw.rect(surf, t["bg"], r, border_radius=11)
            pygame.draw.rect(surf, (0,0,0,130), r, width=2, border_radius=11)
            if is_cur:
                gfx.draw_glow(surf, r.center, 16, (0,180,0), 18)
                pygame.draw.rect(surf,(0,188,72), r, width=4, border_radius=11)
            if is_cursor:
                gfx.draw_glow(surf, r.center, 14, (255,215,0), 18)
                pygame.draw.rect(surf,(255,215,0), r, width=3, border_radius=11)
            pygame.draw.line(surf,(255,255,255,42),(r.x+8,r.y+5),(r.right-8,r.y+5),1)
            btn_preview=pygame.Rect(r.x+12, r.y+34, r.width-24, 24)
            pygame.draw.rect(surf, t["button"], btn_preview, border_radius=6)
            pygame.draw.rect(surf,(0,0,0), btn_preview, width=1, border_radius=6)
            name=self.font_small.render(t["name"], True, t["ui_text"])
            surf.blit(name, (r.centerx - name.get_width()//2, r.y+10))
            btn_txt=self.font_tiny.render("Buton Önizleme", True, (0,0,0) if t["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (255,255,255))
            surf.blit(btn_txt, (btn_preview.centerx - btn_txt.get_width()//2, btn_preview.centery - btn_txt.get_height()//2))
            status=self.font_tiny.render("✓ SEÇİLİ" if is_cur else "ENTER ile Seç", True, (0,120,0) if is_cur else (60,60,60))
            surf.blit(status, (r.centerx - status.get_width()//2, r.y+70))
            if is_cur:
                check=self.font_med.render("✓", True, (0,150,0))
                surf.blit(check, (r.right-18, r.y+6))

    def draw_settings(self, surf, theme):
        surf.fill(theme["bg"])
        title=self.font_big.render("AYARLAR", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 20))
        hint=self.font_small.render("↑↓ Seç  |  ←→ Ayarla  |  ENTER Onayla  |  ESC Geri  |  Mouse ile sürükle", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 52))
        # kart arka plan
        card = pygame.Rect(80, 80, config.SCREEN_WIDTH-160, 360)
        pygame.draw.rect(surf, (255,255,255), card, border_radius=12)
        pygame.draw.rect(surf, (0,0,0), card, width=2, border_radius=12)
        s = self.save["settings"]
        labels = [("MASTER SES", s["master"], "Genel ses seviyesi"), ("MÜZİK", s["music"], "Arka plan müziği"), ("EFEKTLER", s["sfx"], "Coin / zıplama / ölüm efektleri")]
        mx,my = pygame.mouse.get_pos()
        for i,(label, val, desc) in enumerate(labels):
            y = 120 + i*62
            is_sel = self.settings_index == i
            # label
            txt = self.font_med.render(label, True, (0,0,0) if is_sel else (60,60,60))
            surf.blit(txt, (card.x+18, y))
            # bar
            bar = pygame.Rect(260, y+18, 380, 14)
            pygame.draw.rect(surf, (220,220,220), bar, border_radius=7)
            fill = pygame.Rect(bar.x, bar.y, int(bar.width*val), bar.height)
            col = (255,215,0) if is_sel else (120,180,255) if i==1 else (100,200,100)
            pygame.draw.rect(surf, col, fill, border_radius=7)
            pygame.draw.rect(surf, (0,0,0), bar, width=1, border_radius=7)
            # knob
            kx = bar.x + int(bar.width*val)
            pygame.draw.circle(surf, (0,0,0), (kx, bar.centery), 9)
            pygame.draw.circle(surf, (255,255,255), (kx, bar.centery), 6)
            if is_sel:
                pygame.draw.rect(surf, (255,215,0), pygame.Rect(bar.x-2, bar.y-2, bar.width+4, bar.height+4), width=2, border_radius=8)
            # değer
            vtxt = self.font_small.render(f"{int(val*100)}%", True, (0,0,0))
            surf.blit(vtxt, (bar.right+12, bar.y-2))
            d = self.font_tiny.render(desc, True, (100,100,100))
            surf.blit(d, (card.x+18, y+28))
        # tutorial toggle
        y = 310
        is_sel = self.settings_index == 3
        pygame.draw.rect(surf, (255,215,0) if is_sel else (0,0,0), pygame.Rect(card.x+14, y-4, card.width-28, 36), width=2, border_radius=8)
        tlbl = self.font_med.render("TUTORIAL GÖSTER", True, (0,0,0))
        surf.blit(tlbl, (card.x+18, y+6))
        cb = pygame.Rect(card.x+card.width-46, y+6, 22, 22)
        checked = s.get("show_tutorial", True)
        pygame.draw.rect(surf, (255,255,255), cb, border_radius=4)
        pygame.draw.rect(surf, (0,0,0), cb, width=2, border_radius=4)
        if checked:
            pygame.draw.rect(surf, (0,180,0), pygame.Rect(cb.x+3, cb.y+3, 16, 16), border_radius=3)
            chk = self.font_small.render("✓", True, (255,255,255))
            surf.blit(chk, (cb.centerx - chk.get_width()//2, cb.centery - chk.get_height()//2))
        # geri butonu
        is_back_sel = self.settings_index == 4
        back = pygame.Rect(card.centerx-90, card.bottom-44, 180, 34)
        hover = back.collidepoint(mx,my)
        col = (255,215,0) if is_back_sel or hover else (230,230,230)
        pygame.draw.rect(surf, col, back, border_radius=8)
        pygame.draw.rect(surf, (0,0,0), back, width=2, border_radius=8)
        if is_back_sel: pygame.draw.rect(surf, (255,215,0), back, width=3, border_radius=8)
        btxt = self.font_med.render("GERİ (ESC)", True, (0,0,0))
        surf.blit(btxt, (back.centerx - btxt.get_width()//2, back.centery - btxt.get_height()//2))
        # alt bilgi
        info = self.font_tiny.render("Ayarlar save.json'a kaydedilir — eksik dosya olursa varsayılana dönülür.", True, theme["hud"])
        surf.blit(info, (config.SCREEN_WIDTH//2 - info.get_width()//2, config.SCREEN_HEIGHT-22))
        # kontroller kutusu
        ctrl_y = card.bottom + 14
        ctrl = pygame.Rect(80, ctrl_y, config.SCREEN_WIDTH-160, 38)
        pygame.draw.rect(surf, (255,255,240), ctrl, border_radius=8)
        pygame.draw.rect(surf, (0,0,0), ctrl, width=1, border_radius=8)
        ct = self.font_tiny.render("Kontroller: ←→ Hareket  ↑ Zıpla  ↓ Hızlı Düş  SPACE Pause  ESC Menü  |  Tek Can — Sıkışırsan ölürsün!", True, (60,60,60))
        surf.blit(ct, (ctrl.centerx - ct.get_width()//2, ctrl.centery - ct.get_height()//2))

    def draw_levels(self, surf, theme):
        surf.fill(theme["bg"])
        gfx.draw_vignette(surf, intensity=0.18)
        title = self.font_big.render("BÖLÜMLER", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint = self.font_small.render("Yön: Seç  |  ENTER: Oyna  |  ESC: Menü  |  Canavardan Kaç!", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 42))
        prog_txt = self.font_small.render(f"Açık: {len(self.save.get('unlocked_levels',[1]))}/{len(config.LEVELS)}  •  Tamamlanan: {len(self.save.get('completed_levels',[]))}", True, theme["hud"])
        surf.blit(prog_txt, (config.SCREEN_WIDTH//2 - prog_txt.get_width()//2, 62))
        cols=4; card_w,card_h=190,92; gap_x,gap_y=14,12
        start_x=config.SCREEN_WIDTH//2 - (cols*card_w+(cols-1)*gap_x)//2; start_y=88
        for idx, e in enumerate(config.LEVELS):
            row=idx//cols; col=idx%cols
            x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y)
            r=pygame.Rect(x,y,card_w,card_h)
            lvl=e["level"]; unlocked=lvl in self.save.get("unlocked_levels",[1])
            completed=lvl in self.save.get("completed_levels",[])
            is_cursor=idx==self.levels_index
            stars=self.save.get("level_stars",{}).get(str(lvl), self.save.get("level_stars",{}).get(lvl,0))
            # kart
            bg = (255,255,255) if unlocked else (130,130,130)
            if theme["id"] in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi"):
                bg=(52,52,56) if unlocked else (38,38,40)
            gfx.draw_soft_shadow(surf, r, radius=10, alpha=22 if is_cursor else 14)
            pygame.draw.rect(surf, bg, r, border_radius=11)
            pygame.draw.rect(surf, (0,0,0,140), r, width=2, border_radius=11)
            if completed:
                gfx.draw_glow(surf, r.center, 16, (0,180,0), 18)
                pygame.draw.rect(surf, (0,186,70), r, width=3, border_radius=11)
            elif is_cursor and unlocked:
                gfx.draw_glow(surf, r.center, 14, (255,215,0), 18)
                pygame.draw.rect(surf, (255,215,0), r, width=3, border_radius=11)
            elif is_cursor and not unlocked:
                pygame.draw.rect(surf, (200,40,40), r, width=3, border_radius=11)
            # üst renk barı seviye rengine göre
            bar_col=e["obstacle"]
            pygame.draw.rect(surf, bar_col, pygame.Rect(r.x, r.y, r.width, 6), border_radius=4)
            # isim
            num_col=(0,0,0) if unlocked else (80,80,80)
            if theme["id"] in ("siyah","kirmizi_siyah",):
                num_col=(240,240,240) if unlocked else (110,110,110)
            tnum=self.font_small.render(f"BÖLÜM {lvl}", True, num_col)
            surf.blit(tnum, (r.x+10, r.y+12))
            tname=self.font_small.render(e["name"], True, num_col)
            surf.blit(tname, (r.x+10, r.y+28))
            # durum
            if not unlocked:
                lock=self.font_big.render("🔒", True, (60,60,60))
                surf.blit(lock, (r.centerx - lock.get_width()//2, r.centery-6))
                need=self.font_tiny.render(f"Bölüm {lvl-1} bitir", True, (150,40,40))
                surf.blit(need, (r.centerx - need.get_width()//2, r.bottom-16))
            else:
                # yıldızlar
                star_y=r.bottom-18
                for s in range(3):
                    col=(255,215,0) if s < stars else (200,200,200)
                    sx=r.x+12+s*18
                    pygame.draw.polygon(surf, col, [(sx+6, star_y),(sx+2, star_y+6),(sx+6, star_y+12),(sx+10, star_y+6)])
                    pygame.draw.polygon(surf, (0,0,0), [(sx+6, star_y),(sx+2, star_y+6),(sx+6, star_y+12),(sx+10, star_y+6)],1)
                if completed:
                    chk=self.font_tiny.render("✓ TAMAMLANDI", True, (0,140,0))
                    surf.blit(chk, (r.right - chk.get_width() -8, r.y+12))
                else:
                    dist_txt=self.font_tiny.render(f"{e['distance']/100:.0f}m", True, (90,90,90))
                    surf.blit(dist_txt, (r.right - dist_txt.get_width() -8, r.y+12))
                # canavar mini ikon
                gfx.draw_glow(surf, (r.right-16, r.centery), 10, (90,90,110), 12)
                pygame.draw.circle(surf, (60,60,70), (r.right-16, r.centery), 7)
                pygame.draw.circle(surf, (255,40,40), (r.right-16, r.centery), 3)

    def draw_level_complete(self, surf, theme):
        overlay=pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0, 168))
        surf.blit(overlay, (0,0))
        gfx.draw_vignette(surf, intensity=0.22)
        data=self.level_complete_data or {}
        lvl=data.get("level",1); name=data.get("name",""); stars=data.get("stars",1)
        is_final=data.get("is_final", False)
        box=pygame.Rect(config.SCREEN_WIDTH//2-220, config.SCREEN_HEIGHT//2-120, 440, 240)
        gfx.draw_soft_shadow(surf, box, radius=22, alpha=64)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=16)
        # üst şerit
        pygame.draw.rect(surf, (0,186,70) if not is_final else (90,40,180), pygame.Rect(box.x, box.y, box.width, 6), border_radius=4)
        title=self.font_big.render("BÖLÜM TAMAMLANDI!" if not is_final else "TÜM BÖLÜMLER BİTTİ!", True, (18,18,20))
        surf.blit(title, (box.centerx - title.get_width()//2, box.y+16))
        sub=self.font_med.render(f"BÖLÜM {lvl} — {name}", True, (60,60,70))
        surf.blit(sub, (box.centerx - sub.get_width()//2, box.y+48))
        # yıldızlar
        for s in range(3):
            sx=box.centerx -28 + s*28; sy=box.y+82
            col=(255,215,0) if s < stars else (220,220,220)
            star_sz=16 if s < stars else 12
            pts=[(sx, sy-star_sz),(sx-6, sy+4),(sx-10, sy+star_sz),(sx, sy+8),(sx+10, sy+star_sz),(sx+6, sy+4)]
            # basit yıldız
            pygame.draw.polygon(surf, col, [(sx, sy-10),(sx-4, sy-2),(sx-10, sy),(sx-4, sy+6),(sx, sy+12),(sx+4, sy+6),(sx+10, sy),(sx+4, sy-2)])
            pygame.draw.polygon(surf, (0,0,0), [(sx, sy-10),(sx-4, sy-2),(sx-10, sy),(sx-4, sy+6),(sx, sy+12),(sx+4, sy+6),(sx+10, sy),(sx+4, sy-2)],1)
            if s < stars:
                gfx.draw_glow(surf, (sx, sy+2), 12, (255,215,0), 18)
        # stats
        dist=data.get("distance",0); coins=data.get("coins",0)
        stat=self.font_small.render(f"Mesafe: {dist:.1f} m  •  Coin: +{coins}  •  Toplam: {self.save.get('total_coins',0)}", True, (80,80,90))
        surf.blit(stat, (box.centerx - stat.get_width()//2, box.y+118))
        # butonlar
        if is_final:
            b1=pygame.Rect(box.x+60, box.bottom-52, 320, 38)
            hover=b1.collidepoint(pygame.mouse.get_pos())
            col=(90,40,180) if hover else (120,60,200)
            gfx.draw_soft_shadow(surf, b1, radius=10, alpha=22)
            pygame.draw.rect(surf, col, b1, border_radius=10)
            pygame.draw.rect(surf, (0,0,0), b1, width=2, border_radius=10)
            txt=self.font_med.render("FİNALİ İZLE →", True, (255,255,255))
            surf.blit(txt, (b1.centerx - txt.get_width()//2, b1.centery - txt.get_height()//2))
        else:
            b1=pygame.Rect(box.x+20, box.bottom-52, 190, 38)
            b2=pygame.Rect(box.x+230, box.bottom-52, 190, 38)
            mx,my=pygame.mouse.get_pos()
            for b, txt_str in [(b1, "SONRAKİ BÖLÜM"), (b2, "BÖLÜMLER")]:
                hover=b.collidepoint(mx,my)
                base=(0,150,70) if b==b1 else (60,60,70)
                col=(0,180,90) if hover and b==b1 else (80,80,90) if hover else base
                gfx.draw_soft_shadow(surf, b, radius=10, alpha=22 if hover else 14)
                pygame.draw.rect(surf, col, b, border_radius=10)
                pygame.draw.rect(surf, (0,0,0), b, width=2, border_radius=10)
                if hover: pygame.draw.rect(surf, (255,215,0), b, width=2, border_radius=10)
                t=self.font_med.render(txt_str, True, (255,255,255))
                surf.blit(t, (b.centerx - t.get_width()//2, b.centery - t.get_height()//2))

    def draw_ending(self, surf, theme):
        # sinematik final — canavar son anda yetişemez
        # arka karartma
        surf.fill((8,10,18))
        # parlayan END
        t = self.ending_timer
        # ışık
        gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2), 220, (255,215,0), int(22 + 10*math.sin(t*3)))
        gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2+40), 140, (90,130,255), 18)
        # dünya arka planda hafif (son seviye)
        try:
            self.world.draw(surf, self.camera.y, self.level_info)
            self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
            if hasattr(self, 'monster'):
                # canavar geride kalsın (sinematik)
                self.monster.y = self.player.y - 180 - math.sin(t*2)*8
                self.monster.draw(surf, self.camera.y)
        except: pass
        # büyük END yazısı — scale animasyonu
        scale = 1.0 + 0.12*math.sin(t*2.2)
        # skip hint
        if t < 8:
            hint=self.font_small.render("ESC / SPACE ile geç", True, (180,180,190))
            surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 22))
        # END
        end_font = self.font_huge
        # gölge
        sh = end_font.render("END", True, (0,0,0))
        surf.blit(sh, (config.SCREEN_WIDTH//2 - sh.get_width()//2 + 4, config.SCREEN_HEIGHT//2 - 40 + 4))
        txt_col = (255,215,0) if int(t*4)%2==0 else (255,255,255)
        txt = end_font.render("END", True, txt_col)
        # scale via smoothscale
        w,h = txt.get_size()
        sw, sh2 = int(w*scale), int(h*scale)
        if sw>0 and sh2>0:
            big = pygame.transform.smoothscale(txt, (sw, sh2))
            surf.blit(big, (config.SCREEN_WIDTH//2 - sw//2, config.SCREEN_HEIGHT//2 - 40 - sh2//2 + 18))
        sub=self.font_med.render("Tüm bölümler tamamlandı!", True, (220,220,230))
        surf.blit(sub, (config.SCREEN_WIDTH//2 - sub.get_width()//2, config.SCREEN_HEIGHT//2 + 56))
        # oyuncu mesafe/coin
        if self.level_complete_data:
            d=self.level_complete_data
            stat=self.font_small.render(f"Toplam {d.get('total_coins',0)} coin  •  En iyi {self.save.get('best_distance',0):.1f} m", True, (180,180,190))
            surf.blit(stat, (config.SCREEN_WIDTH//2 - stat.get_width()//2, config.SCREEN_HEIGHT//2 + 86))
        # alt buton
        if t > 1.2:
            btn=pygame.Rect(config.SCREEN_WIDTH//2-110, config.SCREEN_HEIGHT-70, 220, 38)
            hover=btn.collidepoint(pygame.mouse.get_pos())
            col=(255,215,0) if hover else (220,220,220)
            pygame.draw.rect(surf, col, btn, border_radius=10)
            pygame.draw.rect(surf, (0,0,0), btn, width=2, border_radius=10)
            txt2=self.font_med.render("ANA MENÜ", True, (0,0,0))
            surf.blit(txt2, (btn.centerx - txt2.get_width()//2, btn.centery - txt2.get_height()//2))

    # ---------- yeni ekranlar: profil / play_select / online / vs ----------
    def draw_profile(self, surf, theme):
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        gfx.draw_vignette(surf, intensity=0.18)
        box = pygame.Rect(config.SCREEN_WIDTH//2-260, config.SCREEN_HEIGHT//2-150, 520, 300)
        gfx.draw_soft_shadow(surf, box, radius=18, alpha=48)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=16)
        pygame.draw.rect(surf, (255,215,0), pygame.Rect(box.x, box.y, box.width, 6), border_radius=4)
        title = self.font_big.render("OYUNCU PROFİLİ OLUŞTUR", True, (18,18,20))
        surf.blit(title, (box.centerx - title.get_width()//2, box.y+18))
        sub = self.font_small.render("Kalıcı 5 haneli ID otomatik verilecek", True, (90,90,96))
        surf.blit(sub, (box.centerx - sub.get_width()//2, box.y+52))
        lbl = self.font_med.render("Nickini gir:", True, (30,30,34))
        surf.blit(lbl, (box.x+30, box.y+86))
        # input alanı — glass + glow focus
        inp = pygame.Rect(box.x+30, box.y+118, box.width-60, 46)
        gfx.draw_soft_shadow(surf, inp, radius=10, alpha=18)
        pygame.draw.rect(surf, (255,255,255), inp, border_radius=10)
        pygame.draw.rect(surf, (255,215,0) if len(self.profile_nick_input)>=2 else (0,0,0), inp, width=2, border_radius=10)
        pygame.draw.line(surf, (255,255,255,90), (inp.x+10, inp.y+5), (inp.right-10, inp.y+5), 1)
        # cursor blink
        txt = self.profile_nick_input
        show = txt + ("|" if (pygame.time.get_ticks()//520)%2==0 else "")
        t_surf = self.font_big.render(show if show else "", True, (0,0,0))
        surf.blit(t_surf, (inp.x+16, inp.centery - t_surf.get_height()//2 if t_surf.get_height()>0 else inp.centery-14))
        if not txt:
            ph = self.font_small.render("örn: Merve", True, (150,150,150))
            surf.blit(ph, (inp.x+16, inp.centery - ph.get_height()//2))
        # hata
        if self.profile_error:
            err = self.font_small.render(self.profile_error, True, (200,30,30))
            surf.blit(err, (box.centerx - err.get_width()//2, inp.bottom+10))
        # OLUSTUR butonu
        btn = pygame.Rect(box.centerx-110, box.y+210, 220, 44)
        hover = btn.collidepoint(pygame.mouse.get_pos())
        gfx.draw_soft_shadow(surf, btn, radius=10, alpha=22 if hover else 14)
        col = (255,215,0) if hover else (30,30,36)
        top = (255,228,110) if hover else (58,58,64)
        btn_s = pygame.Surface((btn.width, btn.height), pygame.SRCALPHA)
        for y in range(btn.height):
            ts=y/btn.height
            rr=int(top[0]*(1-ts)+col[0]*ts); gg=int(top[1]*(1-ts)+col[1]*ts); bb=int(top[2]*(1-ts)+col[2]*ts)
            pygame.draw.line(btn_s,(rr,gg,bb),(0,y),(btn.width,y))
        mask = pygame.Surface((btn.width,btn.height), pygame.SRCALPHA)
        pygame.draw.rect(mask,(255,255,255),(0,0,btn.width,btn.height), border_radius=10)
        btn_s.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(btn_s, btn.topleft)
        pygame.draw.rect(surf, (255,215,0) if hover else (0,0,0), btn, width=2, border_radius=10)
        txt2 = self.font_med.render("OLUŞTUR", True, (0,0,0) if hover else (255,255,255))
        surf.blit(txt2, (btn.centerx - txt2.get_width()//2, btn.centery - txt2.get_height()//2))
        hint = self.font_tiny.render("ENTER ile onayla  •  ID kalıcı ve 5 rakamdan oluşur", True, theme["hud"])
        surf.blit(hint, (box.centerx - hint.get_width()//2, box.bottom+16))

    def draw_play_select(self, surf, theme):
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        gfx.draw_vignette(surf, intensity=0.16)
        title = self.font_big.render("OYNA", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 24))
        hint = self.font_small.render("Nasıl oynamak istersin?", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 56))
        # nick / id kartı
        nick = self.save.get("nickname") or "?"
        pid = self.save.get("player_id") or "?????"
        card = pygame.Rect(config.SCREEN_WIDTH//2-180, 78, 360, 34)
        pygame.draw.rect(surf, (0,0,0,48), card, border_radius=9)
        pygame.draw.rect(surf, (255,215,0,110), card, width=1, border_radius=9)
        txt = self.font_med.render(f"{nick}  •  ID: {pid}", True, (255,255,255) if "siyah" in theme["id"] else (30,30,34))
        surf.blit(txt, (card.centerx - txt.get_width()//2, card.centery - txt.get_height()//2))
        opts = [("ONLINE", "5 haneli ID ile oyuncu bul"), ("BİLGİSAYARA KARŞI", "Çevrimdışı BOT ile yarış"), ("GERİ", "")]
        mx,my = pygame.mouse.get_pos()
        for i,(label,desc) in enumerate(opts):
            y = 132 + i*86
            r = pygame.Rect(config.SCREEN_WIDTH//2-200, y, 400, 68)
            sel = i==self.play_select_index
            hover = r.collidepoint(mx,my)
            gfx.draw_soft_shadow(surf, r, radius=12, alpha=22 if sel or hover else 14)
            base = theme["button"]
            top = (255,228,110) if sel else tuple(min(255,c+14) for c in base)
            bot = (255,185,0) if sel else tuple(max(0,c-10) for c in base)
            btn_s = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            for yy in range(r.height):
                ts=yy/r.height
                rr=int(top[0]*(1-ts)+bot[0]*ts); gg=int(top[1]*(1-ts)+bot[1]*ts); bb=int(top[2]*(1-ts)+bot[2]*ts)
                pygame.draw.line(btn_s,(rr,gg,bb),(0,yy),(r.width,yy))
            mask = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            pygame.draw.rect(mask,(255,255,255),(0,0,r.width,r.height), border_radius=12)
            btn_s.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(btn_s, r.topleft)
            pygame.draw.rect(surf, (255,215,0) if sel else (0,0,0), r, width=3 if sel else 2, border_radius=12)
            pygame.draw.line(surf,(255,255,255,80),(r.x+10,r.y+5),(r.right-10,r.y+5),1)
            t1 = self.font_big.render(label, True, (28,18,4) if sel else (0,0,0) if theme["id"]=="beyaz" else (255,255,255))
            surf.blit(t1, (r.centerx - t1.get_width()//2, r.y+14))
            if desc:
                t2 = self.font_tiny.render(desc, True, (60,60,64) if sel else (90,90,90))
                surf.blit(t2, (r.centerx - t2.get_width()//2, r.y+40))
        info = self.font_small.render("BÖLÜMLER = tek oyunculu ilerleme (ayrı)", True, theme["hud"])
        surf.blit(info, (config.SCREEN_WIDTH//2 - info.get_width()//2, 420))
        sub = self.font_tiny.render("↑↓ Seç  •  ENTER Onayla  •  ESC Geri", True, theme["hud"])
        surf.blit(sub, (config.SCREEN_WIDTH//2 - sub.get_width()//2, config.SCREEN_HEIGHT-22))

    def draw_online(self, surf, theme):
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        gfx.draw_vignette(surf, intensity=0.16)
        title = self.font_big.render("ONLINE", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 24))
        hint = self.font_small.render("Rakibin 5 haneli ID'sini gir ve oyuncuyu bul", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 56))
        # kendi nick/id + bağlantı durumu
        my_nick = self.save.get("nickname") or "?"
        my_id = self.save.get("player_id") or "?????"
        me_txt = self.font_small.render(f"{my_nick}  •  ID: {my_id}", True, theme["hud"])
        surf.blit(me_txt, (config.SCREEN_WIDTH//2 - me_txt.get_width()//2, 74))
        is_on = False
        try:
            is_on = self.online_mgr.is_online() if self.online_mgr else False
        except: pass
        dot_col = (40,200,80) if is_on else (200,40,40)
        dot_txt = "● Sunucuya bağlı" if is_on else "● Sunucu bağlantısı yok"
        st = self.font_tiny.render(dot_txt, True, dot_col)
        surf.blit(st, (config.SCREEN_WIDTH//2 - st.get_width()//2, 88))
        box = pygame.Rect(config.SCREEN_WIDTH//2-260, 106, 520, 306)
        gfx.draw_soft_shadow(surf, box, radius=16, alpha=42)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=14)
        lbl = self.font_med.render("OYUNCU ID GİR (5 rakam):", True, (30,30,34))
        surf.blit(lbl, (box.x+24, box.y+22))
        # input
        inp = pygame.Rect(box.x+24, box.y+54, box.width-48, 48)
        pygame.draw.rect(surf, (255,255,255), inp, border_radius=10)
        pygame.draw.rect(surf, (255,215,0) if len(self.online_input)==5 else (0,0,0), inp, width=2, border_radius=10)
        # digits
        show = self.online_input + ("|" if (pygame.time.get_ticks()//480)%2==0 and len(self.online_input)<5 else "")
        txt = self.font_huge.render(show, True, (0,0,0))
        surf.blit(txt, (inp.centerx - txt.get_width()//2, inp.centery - txt.get_height()//2))
        if not self.online_input:
            ph = self.font_small.render("örn: 48217", True, (160,160,160))
            surf.blit(ph, (inp.centerx - ph.get_width()//2, inp.centery - ph.get_height()//2 + 14))
        # BUL butonu
        btn = pygame.Rect(box.x+24, box.y+118, box.width-48, 42)
        mx,my = pygame.mouse.get_pos()
        hover = btn.collidepoint(mx,my)
        gfx.draw_soft_shadow(surf, btn, radius=10, alpha=18 if hover else 12)
        col = (255,215,0) if hover else (48,48,54)
        top = (255,228,110) if hover else (72,72,78)
        btn_s = pygame.Surface((btn.width,btn.height), pygame.SRCALPHA)
        for y in range(btn.height):
            ts=y/btn.height
            rr=int(top[0]*(1-ts)+col[0]*ts); gg=int(top[1]*(1-ts)+col[1]*ts); bb=int(top[2]*(1-ts)+col[2]*ts)
            pygame.draw.line(btn_s,(rr,gg,bb),(0,y),(btn.width,y))
        mask = pygame.Surface((btn.width,btn.height), pygame.SRCALPHA)
        pygame.draw.rect(mask,(255,255,255),(0,0,btn.width,btn.height), border_radius=10)
        btn_s.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(btn_s, btn.topleft)
        pygame.draw.rect(surf, (255,215,0) if hover else (0,0,0), btn, width=2, border_radius=10)
        t2 = self.font_med.render("OYUNCUYU BUL", True, (0,0,0) if hover else (255,255,255))
        surf.blit(t2, (btn.centerx - t2.get_width()//2, btn.centery - t2.get_height()//2))
        # sonuç alanı
        res_y = btn.bottom+18
        if self.online_error:
            col_err = (200,30,30) if "bulunamadı" in self.online_error or "Bağlantı" in self.online_error else (30,120,30) if "Aranıyor" in self.online_error else (160,80,20)
            err = self.font_small.render(self.online_error, True, col_err)
            surf.blit(err, (box.centerx - err.get_width()//2, res_y))
            res_y+=22
        if self.online_info:
            nick = self.online_info.get("nick","?")
            pid = self.online_info.get("id","?????")
            card = pygame.Rect(box.x+20, res_y+8, box.width-40, 56)
            pygame.draw.rect(surf, (48,38,14), card, border_radius=9)
            pygame.draw.rect(surf, (255,215,0), card, width=2, border_radius=9)
            gfx.draw_glow(surf, (card.x+30, card.centery), 12, (255,215,0), 18)
            pygame.draw.circle(surf, (255,215,0), (card.x+30, card.centery), 10)
            t3 = self.font_med.render(f"{nick}", True, (255,255,255))
            surf.blit(t3, (card.x+54, card.y+10))
            t4 = self.font_small.render(f"ID: {pid}", True, (255,238,130))
            surf.blit(t4, (card.x+54, card.y+30))
            # MAÇ BAŞLAT
            mbtn = pygame.Rect(box.x+24, box.bottom-48, box.width-48, 36)
            hover2 = mbtn.collidepoint(mx,my)
            pygame.draw.rect(surf, (0,160,80) if hover2 else (0,136,68), mbtn, border_radius=9)
            pygame.draw.rect(surf, (0,0,0), mbtn, width=2, border_radius=9)
            if hover2: pygame.draw.rect(surf, (255,215,0), mbtn, width=2, border_radius=9)
            t5 = self.font_med.render("MAÇ BAŞLAT", True, (255,255,255))
            surf.blit(t5, (mbtn.centerx - t5.get_width()//2, mbtn.centery - t5.get_height()//2))
        hint2 = self.font_tiny.render("ESC Geri  •  Sadece rakam gir (5 hane)", True, theme["hud"])
        surf.blit(hint2, (config.SCREEN_WIDTH//2 - hint2.get_width()//2, box.bottom+14))

    def draw_vs_hud(self, surf, theme):
        # VS üst bar: sen vs rakip mesafe
        hud_y = 56
        # yarı şeffaf vs bar
        bar = pygame.Rect(0, hud_y, config.SCREEN_WIDTH, 28)
        bg = pygame.Surface((bar.width, bar.height), pygame.SRCALPHA)
        bg.fill((0,0,0,110))
        surf.blit(bg, bar.topleft)
        # oyuncu mesafe
        my_m = self.player.distance_px/config.PIXELS_PER_METER
        opp_m = 0
        opp_nick = self.vs_opponent_nick or "Rakip"
        if self.state=="vs_bot" and self.vs_bot:
            opp_m = self.vs_bot.distance_px/config.PIXELS_PER_METER
        elif self.state=="vs_online" and self.vs_remote:
            opp_m = self.vs_remote.get("y",0)/config.PIXELS_PER_METER if isinstance(self.vs_remote, dict) else 0
        left = self.font_small.render(f"SEN: {my_m:.1f} m", True, (120,255,120))
        right = self.font_small.render(f"{opp_nick}: {opp_m:.1f} m", True, (255,120,120) if opp_m>my_m else (180,180,255))
        surf.blit(left, (16, hud_y+7))
        surf.blit(right, (config.SCREEN_WIDTH - right.get_width() -16, hud_y+7))
        # orta VS
        vs = self.font_med.render("VS", True, (255,215,0))
        surf.blit(vs, (config.SCREEN_WIDTH//2 - vs.get_width()//2, hud_y+5))
        # lider
        leader = "ÖNDESİN!" if my_m >= opp_m else "GERİDESİN!"
        col = (120,255,120) if my_m>=opp_m else (255,80,80)
        ltxt = self.font_tiny.render(leader, True, col)
        surf.blit(ltxt, (config.SCREEN_WIDTH//2 - ltxt.get_width()//2, hud_y+22))
        # bağlantı uyarısı online
        if self.state=="vs_online" and not self.vs_remote:
            warn = self.font_small.render("Bağlantı bekleniyor...", True, (255,220,100))
            surf.blit(warn, (config.SCREEN_WIDTH//2 - warn.get_width()//2, hud_y+34))

