import pygame
import config
from player import Player
from camera import Camera
from world import World
import save_system
import local_accounts
from particles import ParticleSystem
from audio import audio
import graphics as gfx
import math
from monster import Monster
import random as _rnd
import item_icons
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
        # Misafir saflığı: hesap sahibi değilse eski save'den kalan ID/token asla
        # kullanılmaz — yoksa bg thread "misafir" olarak server'a bağlanır (§24).
        if self.save.get("account_mode") != "account":
            self.save["player_id"] = None
            self.save["account_token"] = None
            self.save["account_mode"] = "guest"
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
        self.vs_finish_y = None  # vs_bot bitiş çizgisi world Y
        self.vs_finish_timer = 0.0
        # Lobby / Invite
        self.lobby_id = None
        self.lobby_players = []
        self.lobby_ready = {}
        self.pending_invite = None
        self.invite_sent = None  # to_id
        self._poll_timer = 0.0
        self._vs_sync_timer = 0.0
        self._lobby_gone_count = 0

        # Hesap kapısı (master §14): oyun her açılışta ana menüye doğrudan girilmez.
        # Önce HESAP OLUŞTUR / GİRİŞ YAP / HESAPSIZ DEVAM ET seçilir.
        # NOT: burada server bağlantısı YOKTUR — sadece OYNA->ONLINE'da bağlanılır.
        self.state = "account_gate"

        # Hesap kapısı durumu
        self.account_gate_index = 0
        self.account_gate_options = ["HESAP OLUŞTUR", "GİRİŞ YAP", "HESAPSIZ DEVAM ET"]
        self.account_error = ""
        self.account_busy = False
        self.play_select_msg = ""
        # HESAP OLUŞTUR / GİRİŞ YAP form alanları
        self.reg_nick = ""
        self.reg_pass = ""
        self.reg_field = 0  # 0 nickname, 1 şifre
        self.login_ident = ""
        self.login_pass = ""
        self.login_field = 0
        # oyun verisi sync (throttled + pending retry)
        self._sync_timer = 5.0
        self._game_data_dirty = False

        self.menu_index = 0
        self.menu_options = ["OYNA", "BÖLÜMLER", "KARAKTERLER", "MAGAZA", "ENVANTER", "TEMALAR", "AYARLAR", "NASIL OYNANIR?", "CIKIS"]
        self.shop_tab = 0
        self.shop_index = 0
        self.shop_scroll = 0  # mağaza liste kaydırma (piksel)
        self.char_index = 0
        self.inv_tab = 0
        self.inv_index = 0
        self.inv_scroll = 0  # envanter liste kaydırma (piksel)
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

        # NASIL OYNANIR? modal
        self.help_open = False
        self.help_pause_prev = None

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
        self.vs_mode = None
        self.vs_bot = None
        self.vs_finish_y = None
        self.vs_result = None
        self.vs_finish_timer = 0.0
        # ONLINE modunu kapat — menüde server'a otomatik bağlantı yok
        try:
            if self.online_mgr:
                self.online_mgr.set_online_mode(False)
        except Exception:
            pass
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

    def _open_help(self):
        """NASIL OYNANIR? modalını açar. Oyundayken otomatik duraklat."""
        if self.state == "playing":
            self.help_pause_prev = self.paused
            self.paused = True
        self.help_open = True
        try: audio.play("click")
        except: pass

    def _close_help(self):
        """Modalı kapatır; oyundan açıldıysa önceki duraklatma durumuna döner."""
        self.help_open = False
        if self.state == "playing" and self.help_pause_prev is not None:
            self.paused = self.help_pause_prev
            self.help_pause_prev = None
        try: audio.play("click")
        except: pass

    def _help_close_rect(self):
        return pygame.Rect(config.SCREEN_WIDTH//2 - 100, config.SCREEN_HEIGHT - 148, 200, 42)

    # ---- Hesap Kapısı (master §14-21) ----
    def is_guest(self):
        """Misafir mi? Misafir asla server bağlantısı başlatmaz (§17)."""
        mode = self.save.get("account_mode", "guest")
        if mode == "account":
            return False
        return True

    def _enter_main_menu(self, first_entry=False):
        """Hesap kapısından ana menüye geç. İlk girişte NASIL OYNANIR? otomatik (§31)."""
        self.state = "menu"
        self.menu_index = 0
        self.play_select_msg = ""
        if first_entry and self.save.get("show_how_to_play", True):
            # tek seferlik: açıldığında flag kapatılır, aynı oturumda tekrar açılmaz
            self.save["show_how_to_play"] = False
            try: save_system.save_game(self.save)
            except: pass
            self._open_help()

    def _gate_select(self):
        idx = self.account_gate_index
        self.account_error = ""
        self.reg_nick = str(self.save.get("nickname") or "")
        self.reg_pass = ""
        self.reg_field = 0
        self.login_ident = str(self.save.get("nickname") or "")
        self.login_pass = ""
        self.login_field = 0
        if idx == 0:
            self.state = "account_register"
            audio.play("click")
        elif idx == 1:
            self.state = "account_login"
            audio.play("click")
        else:
            self._enter_as_guest()

    def _enter_as_guest(self):
        """HESAPSIZ DEVAM ET — tam çevrimdışı, ONLINE kilitli, hiçbir server bağlantısı yok."""
        self.save["account_mode"] = "guest"
        self.save["account_token"] = None
        self.save["player_id"] = None  # bg polling'in server'a hiç dokunmaması için
        if not save_system.is_valid_nick(self.save.get("nickname") or ""):
            self.save["nickname"] = "MİSAFİR"
        try: save_system.save_game(self.save)
        except: pass
        audio.play("levelup")
        self._enter_main_menu(first_entry=True)

    def handle_account_gate_keys(self, event):
        if self.account_busy:
            return
        if event.key == pygame.K_UP:
            self.account_gate_index = (self.account_gate_index - 1) % 3
            audio.play("hover", 0.5)
        elif event.key == pygame.K_DOWN:
            self.account_gate_index = (self.account_gate_index + 1) % 3
            audio.play("hover", 0.5)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._gate_select()
        elif event.key == pygame.K_ESCAPE:
            # kapıdan server'a yönlenme yok — ESC işlevsiz kalır (güvenli)
            pass

    def handle_account_register_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "account_gate"
            self.account_error = ""
            audio.play("click")
            return
        if self.account_busy:
            return
        if event.key == pygame.K_TAB:
            self.reg_field = 1 - self.reg_field
            audio.play("hover", 0.4)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit_register()
        elif event.key == pygame.K_BACKSPACE:
            if self.reg_field == 0:
                self.reg_nick = self.reg_nick[:-1]
            else:
                self.reg_pass = self.reg_pass[:-1]
        else:
            ch = getattr(event, "unicode", "")
            if ch and ch.isprintable() and ch not in ("\n", "\r", "\t"):
                if self.reg_field == 0:
                    if len(self.reg_nick) < 16:
                        self.reg_nick += ch
                elif len(self.reg_pass) < 32:
                    self.reg_pass += ch

    def handle_account_login_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "account_gate"
            self.account_error = ""
            audio.play("click")
            return
        if self.account_busy:
            return
        if event.key == pygame.K_TAB:
            self.login_field = 1 - self.login_field
            audio.play("hover", 0.4)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit_login()
        elif event.key == pygame.K_BACKSPACE:
            if self.login_field == 0:
                self.login_ident = self.login_ident[:-1]
            else:
                self.login_pass = self.login_pass[:-1]
        else:
            ch = getattr(event, "unicode", "")
            if ch and ch.isprintable() and ch not in ("\n", "\r", "\t"):
                if self.login_field == 0:
                    if len(self.login_ident) < 32:
                        self.login_ident += ch
                elif len(self.login_pass) < 32:
                    self.login_pass += ch

    def _submit_register(self):
        nick = self.reg_nick.strip()
        pw = self.reg_pass
        if not save_system.is_valid_nick(nick):
            self.account_error = "Nickname 2-16 karakter olmalı"
            audio.play("death", 0.4)
            return
        if len(pw) < 4:
            self.account_error = "Şifre en az 4 karakter olmalı"
            audio.play("death", 0.4)
            return
        self.account_busy = True
        self.account_error = "Kayıt yapılıyor..."
        try:
            ok, err = local_accounts.register(nick, pw)
        except Exception as e:
            ok, err = False, f"Hata: {e}"
        self.account_busy = False
        if ok:
            # Yerel hesap — server bağlantısı YOK. ID, ilk OYNA->ONLINE'da
            # server tarafından üretilir; token'ı temizle (sync asla çalışmaz).
            self.save["nickname"] = nick
            self.save["account_mode"] = "account"
            self.save["account_token"] = None
            self.save["account_username"] = nick
            try: save_system.save_game(self.save)
            except: pass
            self.account_error = ""
            audio.play("levelup")
            self._enter_main_menu(first_entry=True)
        else:
            self.account_error = err or "Kayıt hatası"
            audio.play("death", 0.4)

    def _submit_login(self):
        ident = self.login_ident.strip()
        pw = self.login_pass
        if not ident:
            self.account_error = "Nickname veya Player ID girin"
            audio.play("death", 0.4)
            return
        if not pw:
            self.account_error = "Şifre girin"
            audio.play("death", 0.4)
            return
        self.account_busy = True
        self.account_error = "Giriş yapılıyor..."
        try:
            ok, err = local_accounts.login(ident, pw)
            if not ok and save_system.is_valid_player_id(ident):
                # Player ID ile giriş: mevcut save'in nick'ine düş (yerel hesap)
                saved_nick = str(self.save.get("nickname") or "").strip()
                if (str(self.save.get("player_id") or "") == ident
                        and saved_nick and saved_nick != ident):
                    ok, err = local_accounts.login(saved_nick, pw)
        except Exception as e:
            ok, err = False, f"Hata: {e}"
        self.account_busy = False
        if ok:
            # Yerel giriş — server bağlantısı YOK, sahip olunan oyun verisi
            # aynen korunur. Token'ı temizle (sync asla çalışmaz).
            self.save["account_mode"] = "account"
            self.save["account_token"] = None
            self.save["account_username"] = ident
            if not save_system.is_valid_nick(self.save.get("nickname") or ""):
                self.save["nickname"] = ident
            try: save_system.save_game(self.save)
            except: pass
            self.account_error = ""
            audio.play("levelup")
            self._enter_main_menu(first_entry=True)
        else:
            self.account_error = err or "Giriş hatası"
            audio.play("death", 0.4)

    def _apply_server_game_data(self, gd):
        """Sunucudan gelen hesap oyun verisini save'e uygula (server yetkili §23)."""
        if not isinstance(gd, dict):
            return
        for k in ("total_coins", "best_distance", "level", "current_level",
                  "selected_character", "selected_hat", "selected_bag",
                  "selected_glasses", "selected_cane", "theme", "final_completed"):
            if gd.get(k) is not None:
                self.save[k] = gd[k]
        for k in ("owned_items", "unlocked_characters", "unlocked_levels", "completed_levels"):
            if isinstance(gd.get(k), list):
                self.save[k] = list(gd[k])
        if isinstance(gd.get("level_stars"), dict):
            try:
                self.save["level_stars"] = {str(k): int(v) for k, v in gd["level_stars"].items()}
            except Exception:
                pass
        if not self.save.get("owned_items"):
            self.save["owned_items"] = []
        if "cop_adam" not in self.save.get("unlocked_characters", []):
            self.save["unlocked_characters"].insert(0, "cop_adam")

    # ---- Oyun verisi sync (throttled + pending retry) ----
    def _build_server_game_data(self):
        s = self.save
        lst = {}
        try:
            lst = {str(k): int(v) for k, v in (s.get("level_stars") or {}).items()}
        except Exception:
            lst = {}
        return {
            "total_coins": s.get("total_coins", 0),
            "best_distance": s.get("best_distance", 0.0),
            "level": s.get("level", 1),
            "current_level": s.get("current_level", 1),
            "selected_character": s.get("selected_character", "cop_adam"),
            "selected_hat": s.get("selected_hat"),
            "selected_bag": s.get("selected_bag"),
            "selected_glasses": s.get("selected_glasses"),
            "selected_cane": s.get("selected_cane"),
            "owned_items": list(s.get("owned_items", [])),
            "theme": s.get("theme", "beyaz"),
            "unlocked_characters": list(s.get("unlocked_characters", ["cop_adam"])),
            "unlocked_levels": list(s.get("unlocked_levels", [1])),
            "completed_levels": list(s.get("completed_levels", [])),
            "level_stars": lst,
            "final_completed": s.get("final_completed", False),
        }

    def _game_mutated(self):
        """Oyun verisi değişti — hesaplı kullanıcılarda throttled sync işaretle."""
        self._game_data_dirty = True

    def _flush_game_data(self):
        """Bekleyen veriyi server'a yaz. Hata olursa dirty kalır → sonraki pencerede yeniden dene."""
        if self.is_guest() or not self.save.get("account_token"):
            self._game_data_dirty = False
            return
        if not self.online_mgr:
            self._game_data_dirty = False
            return
        try:
            ok = self.online_mgr.sync_game_data(self._build_server_game_data())
            if ok:
                self._game_data_dirty = False
        except Exception:
            pass

    def _try_enter_online(self):
        """OYNA->ONLINE — misafir kilitli, server'a asla bağlanmaz."""
        if self.is_guest():
            self.play_select_msg = "ONLINE oynamak için hesapla giriş yapmalısın."
            audio.play("death", 0.4)
            return
        self.play_select_msg = ""
        self.state = "online_menu"
        audio.play("click")
        self._enter_online()

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
        self._game_mutated()
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
        self.vs_finish_y = None
        self.vs_result = None
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
        self.vs_finish_y = None
        self.vs_result = None
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
        if new_level != old_level:
            self._game_mutated()
        return new_level

    def get_equipped(self):
        # Runtime sanitizasyon — bozuk ID veya owned olmayan item render edilmez (çökme yok)
        try:
            _valid = set()
            for _cat in config.SHOP_ITEMS.values():
                for _it in _cat:
                    _valid.add(str(_it.get("id")))
            _owned = set(str(x) for x in self.save.get("owned_items", []))
            def _san(v):
                if v is None:
                    return None
                sv = str(v)
                if sv not in _valid or sv not in _owned:
                    return None
                return sv
            return {
                "hat": _san(self.save.get("selected_hat")),
                "bag": _san(self.save.get("selected_bag")),
                "glasses": _san(self.save.get("selected_glasses")),
                "cane": _san(self.save.get("selected_cane")),
            }
        except Exception:
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

        # Oyun verisi sync — throttled (5sn) + pending retry (sadece hesaplı)
        self._sync_timer += dt
        if self._game_data_dirty and self._sync_timer >= 5.0:
            self._sync_timer = 0.0
            self._flush_game_data()

        # Online invite/lobby polling — throttled (0.2s) non-blocking (bg thread)
        self._poll_timer += dt
        if self._poll_timer >= 0.20:
            self._poll_timer = 0.0
            if self.online_mgr:
                try:
                    # non-blocking cache reads (bg thread handles network)
                    if hasattr(self.online_mgr, "get_cached_invite"):
                        inv = self.online_mgr.get_cached_invite()
                    else:
                        inv = self.online_mgr.poll_invite()
                    if inv and not self.pending_invite:
                        self.pending_invite = inv
                        audio.play("levelup")
                    if hasattr(self.online_mgr, "get_cached_lobby"):
                        lob = self.online_mgr.get_cached_lobby()
                    else:
                        lob = self.online_mgr.poll_lobby()
                    if lob:
                        self.lobby_id = lob.get("lobby_id")
                        self.lobby_players = lob.get("players", [])
                        self.lobby_ready = lob.get("ready", {})
                        if self.state not in ("lobby", "vs_online"):
                            if self.lobby_id:
                                self.state = "lobby"
                        self._lobby_gone_count = 0
                    else:
                        if self.state in ("lobby", "vs_online") and self.lobby_id:
                            cnt = getattr(self, "_lobby_gone_count", 0) + 1
                            self._lobby_gone_count = cnt
                            if cnt >= 2:
                                self.lobby_id = None
                                self.lobby_players = []
                                self.lobby_ready = {}
                                if self.state == "vs_online":
                                    self.vs_remote = None
                                self.state = "online_menu"
                                self.online_error = "Oyuncu lobiden ayrıldı."
                                self._lobby_gone_count = 0
                        else:
                            self._lobby_gone_count = 0
                    if self.lobby_id:
                        if hasattr(self.online_mgr, "get_cached_game_start"):
                            gid = self.online_mgr.get_cached_game_start(self.lobby_id)
                            if not gid:
                                # fallback to bg cached without param
                                gid = self.online_mgr.get_cached_game_start()
                        else:
                            gid = self.online_mgr.poll_game_start(self.lobby_id)
                        if gid:
                            self.lobby_id = gid
                            self.start_multiplayer_game(gid)
                except:
                    pass

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
                self._game_mutated()
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
                self._game_mutated()

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
        # Lobby — sadece bekleme, ready durumu polling ile güncelleniyor
        if self.state == "lobby":
            # bağlantı kopması kontrolü
            if self.online_mgr and not self.online_mgr.is_online():
                # kısa süreli kopma tolere et, ama uzun süre offline ise hata göster
                pass
            # eğer lobby kapandıysa (diğer oyuncu ayrıldı)
            if self.lobby_id and not self.lobby_players:
                # polling'de lobby None oldu
                self.state = "online_menu"
                self.lobby_id = None
                self.online_error = "Oyuncu lobiden ayrıldı."
            return

        # vs_result — KAZANDIN/KAYBETTİN ekranı bekleme
        if self.state == "vs_result":
            self.vs_finish_timer += dt
            self.particles.update(dt, self.camera.y, self.level_info["name"])
            if self.level_up_anim > 0:
                self.level_up_anim -= dt
            return

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
            # world — VS_BOT'ta hem oyuncu hem bot için generate, culling botu silmesin
            if self.state == "vs_bot" and self.vs_bot is not None:
                bot_cam = self.vs_bot.y - config.SCREEN_HEIGHT * config.CAMERA_FOLLOW_Y_RATIO
                gen_cam = max(self.camera.y, bot_cam)
                keep_cam = min(self.camera.y, bot_cam)
                self.world.ensure_generated(gen_cam, keep_cam)
            else:
                self.world.ensure_generated(self.camera.y)
            self.world.update_coins(dt)
            evt = self.player.update_physics(dt, self.world.obstacles)
            if evt=="land":
                self.particles.emit_land(self.player.x+self.player.w//2, self.player.y+self.player.h)
                audio.play("jump",0.5)
            elif evt=="death":
                audio.play("death")
                self.particles.emit_death(self.player.x+self.player.w//2, self.player.y+self.player.h//2)
            # bot physics
            bot_evt=None
            if self.state=="vs_bot" and self.vs_bot:
                bot_evt=self.vs_bot.update_physics(dt, self.world.obstacles)
                # bot coin toplama (görsel)
                for c in self.world.coins:
                    if not c.collected and self.vs_bot.rect.colliderect(c.rect()):
                        c.collected=True
                        self.vs_bot.coins+=c.value
            # online multiplayer sync — throttled (0.08s) non-blocking
            if self.state=="vs_online" and self.online_mgr and self.lobby_id:
                self._vs_sync_timer += dt
                if self._vs_sync_timer >= 0.08:
                    self._vs_sync_timer = 0.0
                    try:
                        my_state = {"x": self.player.x, "y": self.player.y, "vx": self.player.vx, "vy": self.player.vy, "state": self.player.state, "alive": self.player.alive, "coins": self.player.coins, "char": self.save.get("selected_character")}
                        self.online_mgr.send_player_state(self.lobby_id, my_state)
                    except: pass
                    try:
                        if hasattr(self.online_mgr, "get_cached_remotes"):
                            remotes = self.online_mgr.get_cached_remotes(self.lobby_id)
                        else:
                            remotes = self.online_mgr.poll_remote_states(self.lobby_id)
                        for pid, st in remotes.items():
                            if pid != str(self.save.get("player_id")):
                                self.vs_remote = st
                                self.vs_opponent_id = pid
                                break
                    except:
                        self.vs_remote = None
            gained=self.world.check_coin_collection(self.player.rect)
            if gained:
                self.save["total_coins"]+=gained
                self.player.coins+=gained
                self._game_mutated()
                self.particles.emit_coin(self.player.x+self.player.w//2, self.player.y+self.player.h//2, gained)
                audio.play("coin5" if gained>=5 else "coin")
            self.camera.update(dt, self.player.y, self.player.alive)
            # monster — VS_BOT'ta gerçek rekabet: canavar en gerideki hedefi kovalar
            if self.state == "vs_bot":
                try:
                    # deterministik hedef: canavara en yakın (gap küçük) olan
                    target = self.player
                    if self.vs_bot and self.vs_bot.alive:
                        gap_player = self.player.y - self.monster.y
                        gap_bot = self.vs_bot.y - self.monster.y
                        if gap_bot < gap_player:
                            target = self.vs_bot
                    self.monster.update(dt, target, self.camera.y)
                    # her iki yarışmacı için ayrı catch (global flag kirletmeden)
                    if self.vs_bot and self.vs_bot.alive and self.monster.check_catch_vs(self.vs_bot):
                        self.vs_bot.alive=False
                        self.vs_bot.state="death"
                        self.particles.emit_death(self.vs_bot.x+self.vs_bot.w//2, self.vs_bot.y+self.vs_bot.h//2)
                    if self.player.alive and self.monster.check_catch_vs(self.player):
                        self.player.alive=False; self.player.state="death"
                        audio.play("death")
                        self.particles.emit_death(self.player.x+self.player.w//2, self.player.y+self.player.h//2)
                        self.monster.caught=True
                except: pass
            else:
                try:
                    self.monster.update(dt, self.player, self.camera.y)
                    # bot'u da kontrol et — bot ölürse player kazanır (sadece online/monster modda)
                    if self.state=="vs_bot" and self.vs_bot and self.vs_bot.alive:
                        if self.monster.check_catch(self.vs_bot):
                            self.vs_bot.alive=False
                            self.vs_bot.state="death"
                    if self.monster.check_catch(self.player) and self.player.alive:
                        self.player.alive=False; self.player.state="death"
                        audio.play("death")
                        self.particles.emit_death(self.player.x+self.player.w//2, self.player.y+self.player.h//2)
                except: pass
            # --- BİTİŞ ÇİZGİSİ — vs_bot ---
            if self.state == "vs_bot" and self.vs_finish_y is not None and self.vs_result is None:
                player_finished = self.player.alive and self.player.y >= self.vs_finish_y
                bot_finished = self.vs_bot and self.vs_bot.alive and self.vs_bot.y >= self.vs_finish_y
                if player_finished or bot_finished:
                    if player_finished and bot_finished:
                        # beraber çizgiyi geçti — daha ileride olan kazanır
                        self.vs_result = "win" if self.player.y >= self.vs_bot.y else "lose"
                    elif player_finished:
                        self.vs_result = "win"
                    else:
                        self.vs_result = "lose"
                    self.state = "vs_result"
                    self.vs_finish_timer = 0.0
                    self.paused = False
                    try:
                        if self.vs_result == "win":
                            audio.play("levelup")
                            self.particles.emit_levelup(self.player.x + self.player.w//2, self.player.y)
                        else:
                            audio.play("death", 0.6)
                    except: pass
                    save_system.save_game(self.save)
                    # döngüyü durdur — vs_result ekranı update'de bekleyecek
                    return
            if not self.player.alive and self.state=="vs_bot" and self.vs_bot and not self.vs_bot.alive:
                # ikisi aynı anda elendi → deterministik: oyuncu kaybetti
                self.death_timer+=dt
                if self.death_timer>1.2:
                    self.vs_result="lose"
                    self.state="gameover"
                    save_system.save_game(self.save)
            elif not self.player.alive:
                self.death_timer+=dt
                if self.death_timer>1.2:
                    self.vs_result="lose"
                    self.state="gameover"
                    save_system.save_game(self.save)
            elif self.state=="vs_bot" and self.vs_bot and not self.vs_bot.alive:
                # bot elendi → oyuncu kazandı (vs_result ekranı)
                if self.vs_result is None:
                    self.vs_result="win"
                    self.state="vs_result"
                    self.vs_finish_timer=0.0
                    self.paused=False
                    try:
                        audio.play("levelup")
                        self.particles.emit_levelup(self.player.x+self.player.w//2, self.player.y)
                    except: pass
                    save_system.save_game(self.save)
                    return
            self.particles.update(dt, self.camera.y, self.level_info["name"])
            # VS'de mesafe rekoru
            dist_m=self.player.distance_px/config.PIXELS_PER_METER
            if dist_m>self.save.get("best_distance",0):
                self.save["best_distance"]=dist_m
                self._game_mutated()

    # ---------- event handling ----------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            # NASIL OYNANIR? modal — açıkken her tuşu yakala (ESC/H/ENTER/SPACE kapatır)
            if self.help_open:
                if event.key in (pygame.K_h, pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self._close_help()
                return
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
            # NASIL OYNANIR? — H tuşu ile her yerden aç
            if event.key == pygame.K_h:
                if self.state in ("menu","playing","shop","characters","inventory","themes","settings","levels","gameover","play_select","online_menu"):
                    self._open_help()
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
                    # ONLINE modunu kapat — menüde otomatik bağlantı yok
                    try:
                        if self.online_mgr:
                            self.online_mgr.set_online_mode(False)
                    except Exception:
                        pass
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
            elif self.state == "account_gate":
                self.handle_account_gate_keys(event)
            elif self.state == "account_register":
                self.handle_account_register_keys(event)
            elif self.state == "account_login":
                self.handle_account_login_keys(event)
            elif self.state == "play_select":
                self.handle_play_select_keys(event)
            elif self.state == "online_menu":
                self.handle_online_keys(event)
            elif self.state == "lobby":
                self.handle_lobby_keys(event)
            elif self.state in ("vs_bot", "vs_online"):
                self.handle_vs_keys(event)
            elif self.state == "vs_result":
                self.handle_vs_result_keys(event)

            # davet popup her durumda (online_menu/lobby/menu) çalışır
            if self.pending_invite and event.key in (pygame.K_y, pygame.K_RETURN):
                # Y ile kabul, ESC ile reddet zaten handle edilecek
                pass

        elif event.type == pygame.MOUSEBUTTONDOWN and event.pos:
            self.handle_mouse(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.handle_mouse_hover(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            # shop/inventory scroll — yalnızca item alanı üzerindeyken kaydır
            if self.state in ("shop", "inventory"):
                which = "shop" if self.state == "shop" else "inventory"
                if self._item_area(which).collidepoint(pygame.mouse.get_pos()):
                    steps = max(1, abs(event.y))
                    inc = -steps * event.y  # tekerlek aşağı(-y) => index +, yukarı(+y) => index -
                    lay = self._list_layout(which)
                    n = len(lay["lst"])
                    cur = self.shop_index if which == "shop" else self.inv_index
                    new = max(0, min(n - 1, cur + inc)) if n else 0
                    if which == "shop":
                        self.shop_index = new
                    else:
                        self.inv_index = new
                    self._ensure_selection_visible(which)
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
            self.play_select_msg = ""
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
            self.inv_tab = 0
            self._reset_list("inventory")
        elif opt == "MAGAZA":
            self.state = "shop"
            self.shop_tab = 0
            self._reset_list("shop")
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
        elif opt == "NASIL OYNANIR?":
            self._open_help()
        elif opt == "CIKIS":
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ---- shop / inventory scroll helpers ----
    def _list_layout(self, which):
        """which: "shop" veya "inventory" — liste geometrisi + scroll limitini döndürür."""
        if which == "shop":
            lst, _ = self.current_shop_list()
            step, row_h = 86, 76
            scroll = self.shop_scroll
        else:
            key = ["hat","bag","glasses","cane"][self.inv_tab]
            lst = [it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
            step, row_h = 84, 74
            scroll = self.inv_scroll
        list_y = 108
        viewport_bottom = config.SCREEN_HEIGHT - 14
        n = len(lst)
        content_bottom = (list_y + (n - 1) * step + row_h) if n else list_y
        max_scroll = max(0, content_bottom - viewport_bottom)
        return {
            "lst": lst, "step": step, "row_h": row_h, "list_y": list_y,
            "viewport_bottom": viewport_bottom, "max_scroll": max_scroll, "scroll": scroll,
        }

    def _clamp_list_scroll(self, which):
        lay = self._list_layout(which)
        v = max(0, min(lay["scroll"], lay["max_scroll"]))
        if which == "shop":
            self.shop_scroll = v
        else:
            self.inv_scroll = v

    def _item_area(self, which):
        lay = self._list_layout(which)
        return pygame.Rect(60, lay["list_y"], config.SCREEN_WIDTH - 120,
                           lay["viewport_bottom"] - lay["list_y"])

    def _ensure_selection_visible(self, which):
        lay = self._list_layout(which)
        idx = self.shop_index if which == "shop" else self.inv_index
        if idx >= len(lay["lst"]):
            idx = max(0, len(lay["lst"]) - 1)
            if which == "shop":
                self.shop_index = idx
            else:
                self.inv_index = idx
        row_top = lay["list_y"] + idx * lay["step"]
        row_bot = row_top + lay["row_h"]
        new = lay["scroll"]
        if row_top - new < lay["list_y"]:
            new = row_top - lay["list_y"]
        if row_bot - new > lay["viewport_bottom"]:
            new = row_bot - lay["viewport_bottom"]
        new = max(0, min(new, lay["max_scroll"]))
        if which == "shop":
            self.shop_scroll = new
        else:
            self.inv_scroll = new

    def _reset_list(self, which):
        if which == "shop":
            self.shop_index = 0
            self.shop_scroll = 0
        else:
            self.inv_index = 0
            self.inv_scroll = 0

    # ---- shop ----
    def current_shop_list(self):
        tabs = ["hat","bag","glasses","cane"]
        key = tabs[self.shop_tab]
        return config.SHOP_ITEMS[key], key

    def handle_shop_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"; save_system.save_game(self.save); return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self._reset_list("shop")
            self.shop_tab = (self.shop_tab -1) % 4; audio.play("hover",0.6)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._reset_list("shop")
            self.shop_tab = (self.shop_tab +1) %4; audio.play("hover",0.6)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.shop_index = max(0, self.shop_index-1)
            self._ensure_selection_visible("shop")
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            lst,_ = self.current_shop_list()
            self.shop_index = min(len(lst)-1, self.shop_index+1)
            self._ensure_selection_visible("shop")
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
                    self._game_mutated()
                else:
                    if self.save["total_coins"] >= item["price"]:
                        self.save["total_coins"] -= item["price"]
                        if item["id"] not in self.save["owned_items"]:
                            self.save["owned_items"].append(item["id"])
                        sel_key = {"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                        self.save[sel_key] = item["id"]
                        save_system.save_game(self.save)
                        self._game_mutated()
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
                self._game_mutated()
                audio.play("click")

    def handle_inv_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state="menu"; return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self._reset_list("inventory")
            self.inv_tab = (self.inv_tab -1) %4; audio.play("hover",0.6)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._reset_list("inventory")
            self.inv_tab = (self.inv_tab+1)%4; audio.play("hover",0.6)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.inv_index = max(0, self.inv_index-1)
            self._ensure_selection_visible("inventory")
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            tabs=["hat","bag","glasses","cane"]
            key=tabs[self.inv_tab]
            owned = [it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
            self.inv_index = min(max(0,len(owned)-1), self.inv_index+1)
            self._ensure_selection_visible("inventory")
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
                self._game_mutated()
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
            self._game_mutated()
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
        """OYNA->ONLINE'da bağlan: ONLINE modunu aç + server'a bağlan, gerekirse ilk ID'yi server'dan al."""
        self.online_input = ""
        self.online_error = ""
        self.online_info = None
        self.online_searching = False
        # Bağlantı dene
        if not self.online_mgr:
            self.online_error = "Sunucuya bağlanılamadı."
            return
        # ONLINE modu AÇ — bg polling/persistent artık server'a dokunabilir
        self.online_mgr.set_online_mode(True)
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
                # ONLINE — misafir kilitli; sadece hesap kullanıcıları server'a bağlanır
                self._try_enter_online()
            elif self.play_select_index == 1:
                # BİLGİSAYARA KARŞI
                self.start_vs_bot()
                audio.play("click")
            else:
                self.state = "menu"

    def handle_online_keys(self, event):
        # davet popup varsa önce onu işle
        if self.pending_invite:
            if event.key == pygame.K_ESCAPE:
                self.reject_invite()
                return
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_y):
                self.accept_invite()
                return
            elif event.key == pygame.K_n:
                self.reject_invite()
                return
        if event.key == pygame.K_ESCAPE:
            # ONLINE'dan çık — server bağlantısı da kapanır (menüde otomatik yok)
            if self.online_mgr:
                self.online_mgr.set_online_mode(False)
            self.state = "play_select"; self.online_error=""; return
        if event.key == pygame.K_BACKSPACE:
            self.online_input = self.online_input[:-1]
            self.online_error=""
        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
            # ara — eğer oyuncu bulunduysa davet et, yoksa ara
            if self.online_info and self.online_input.strip() == str(self.online_info.get("id") or self.online_info.get("player_id","")):
                self.send_invite()
            else:
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

    def handle_lobby_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.leave_lobby()
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.toggle_ready()
        elif event.key == pygame.K_q:
            self.leave_lobby()

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
        self.vs_finish_y = self.player.y + config.VS_BOT_FINISH_DISTANCE
        self.vs_finish_timer = 0.0
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

    # Yeni: davet/lobby akışı
    def send_invite(self):
        if not self.online_info:
            self.online_error = "Önce oyuncu bulun"
            return
        to_id = str(self.online_info.get("id") or self.online_info.get("player_id","")).strip()
        if not to_id:
            self.online_error = "Geçersiz ID"
            return
        if self.online_mgr:
            ok, msg = self.online_mgr.send_invite(to_id)
            if ok:
                self.invite_sent = to_id
                self.online_error = f"Davet gönderildi: {to_id}"
                audio.play("click")
            else:
                self.online_error = msg
                audio.play("death",0.4)

    def accept_invite(self):
        if not self.pending_invite:
            return
        from_id = self.pending_invite.get("from_id")
        if self.online_mgr:
            ok, msg = self.online_mgr.accept_invite(from_id)
            if ok:
                self.pending_invite = None
                audio.play("levelup")
            else:
                self.online_error = msg

    def reject_invite(self):
        if not self.pending_invite:
            return
        from_id = self.pending_invite.get("from_id")
        if self.online_mgr:
            self.online_mgr.reject_invite(from_id)
        self.pending_invite = None
        audio.play("click")

    def toggle_ready(self):
        if not self.lobby_id or not self.online_mgr:
            return
        # kendi ready durumunu toggle
        cur = self.lobby_ready.get(str(self.save.get("player_id")), False)
        new = not cur
        self.online_mgr.send_ready(self.lobby_id, new)
        # local optimistic
        self.lobby_ready[str(self.save.get("player_id"))] = new
        audio.play("click")

    def leave_lobby(self):
        if self.lobby_id and self.online_mgr:
            self.online_mgr.leave_lobby(self.lobby_id)
        self.lobby_id = None
        self.lobby_players = []
        self.lobby_ready = {}
        self.state = "online_menu"
        audio.play("click")

    def start_multiplayer_game(self, lobby_id):
        # Gerçek multiplayer oyun — lobby hazır
        self.lobby_id = lobby_id
        self.state = "vs_online"
        self.vs_mode = "online"
        self.vs_race_timer = 0.0
        self.vs_result = None
        self.death_timer = 0.0
        self.paused = False
        # rakip bilgisi
        other = None
        for pid in self.lobby_players:
            if pid != str(self.save.get("player_id")):
                other = pid
                break
        if other:
            self.vs_opponent_id = other
            # nick bul
            if self.online_info and str(self.online_info.get("id")) == other:
                self.vs_opponent_nick = self.online_info.get("nick") or self.online_info.get("nickname")
            else:
                self.vs_opponent_nick = other
        else:
            self.vs_opponent_id = self.online_info.get("id") if self.online_info else "Rakip"
            self.vs_opponent_nick = self.online_info.get("nick") if self.online_info else "Rakip"
        self.player.reset(config.SCREEN_WIDTH//2 - config.PLAYER_W//2, 80)
        self.camera.reset(self.player.y)
        self.world.reset()
        self.particles = ParticleSystem()
        self.level = 1
        self.level_info = config.LEVELS[0]
        self.monster = Monster()
        self.monster.reset(self.player.y, 1, "HAVA")
        self.vs_remote = None
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
            self.vs_finish_y=None
            audio.play("click")
        elif event.key==pygame.K_SPACE:
            self.paused= not self.paused
        elif event.key in (pygame.K_UP, pygame.K_w):
            if self.state in ("vs_bot","vs_online"):
                jumped = self.player.try_jump()
                if jumped:
                    self.particles.emit_jump(self.player.x + self.player.w//2, self.player.y + self.player.h)
                    audio.play("jump")

    def handle_vs_result_keys(self, event):
        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
            # tekrar — aynı BOT yarışı
            self.start_vs_bot()
            audio.play("click")
        elif event.key in (pygame.K_ESCAPE, pygame.K_m, pygame.K_q):
            self.state = "play_select"
            self.vs_mode = None
            self.vs_bot = None
            self.vs_finish_y = None
            self.vs_result = None
            audio.play("click")

    def handle_mouse(self, pos):
        mx,my = pos
        if self.help_open:
            if self._help_close_rect().collidepoint(mx,my):
                self._close_help()
            return
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
        elif self.state=="playing" and self.paused:
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
                    self._reset_list("shop"); self.shop_tab=i; audio.play("click"); return
            # liste item hit
            lay = self._list_layout("shop")
            lst = lay["lst"]
            for idx in range(len(lst)):
                y = lay["list_y"] + idx*lay["step"] - lay["scroll"]
                r=pygame.Rect(60,y,config.SCREEN_WIDTH-120,lay["row_h"])
                if r.collidepoint(mx,my):
                    self.shop_index=idx
                    # çift tık gibi: satın al/kuşan
                    key=self.current_shop_list()[1]
                    item=lst[idx]
                    owned=item["id"] in self.save["owned_items"]
                    sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                    if owned:
                        if self.save.get(sel_key)==item["id"]: self.save[sel_key]=None
                        else: self.save[sel_key]=item["id"]
                        save_system.save_game(self.save); self._game_mutated(); audio.play("click")
                    else:
                        if self.save["total_coins"]>=item["price"]:
                            self.save["total_coins"]-=item["price"]; self.save["owned_items"].append(item["id"])
                            self.save[sel_key]=item["id"]; save_system.save_game(self.save); self._game_mutated(); audio.play("coin")
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
                        self.save["selected_character"]=ch["id"]; save_system.save_game(self.save); self._game_mutated(); audio.play("click")
                    else: audio.play("death",0.4)
                    break
        elif self.state=="inventory":
            tabs=["SAPKA","CANTA","GOZLUK","BASTON"]
            tab_w=110; gap=12; total_w=len(tabs)*tab_w+(len(tabs)-1)*gap; start_x=config.SCREEN_WIDTH//2-total_w//2
            for i in range(len(tabs)):
                r=pygame.Rect(start_x+i*(tab_w+gap),68,tab_w,28)
                if r.collidepoint(mx,my):
                    self._reset_list("inventory"); self.inv_tab=i; audio.play("click"); return
            lay = self._list_layout("inventory")
            key=["hat","bag","glasses","cane"][self.inv_tab]
            owned=lay["lst"]
            for idx,item in enumerate(owned):
                y = lay["list_y"] + idx*lay["step"] - lay["scroll"]
                r=pygame.Rect(60,y,config.SCREEN_WIDTH-120,lay["row_h"])
                if r.collidepoint(mx,my):
                    self.inv_index=idx
                    sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                    if self.save.get(sel_key)==item["id"]: self.save[sel_key]=None
                    else: self.save[sel_key]=item["id"]
                    save_system.save_game(self.save); self._game_mutated(); audio.play("click")
                    break
        elif self.state=="themes":
            cols=4; card_w,card_h=190,108; gap_x,gap_y=18,16
            start_x=config.SCREEN_WIDTH//2 - (cols*card_w+(cols-1)*gap_x)//2; start_y=88
            for idx,t in enumerate(config.THEMES):
                row=idx//cols; col=idx%cols
                x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y)
                r=pygame.Rect(x,y,card_w,card_h)
                if r.collidepoint(mx,my):
                    self.theme_index=idx; self.save["theme"]=t["id"]; save_system.save_game(self.save); self._game_mutated(); audio.play("click"); break
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
        elif self.state=="account_gate":
            # draw_account_gate ile aynı geometri: 400x66, start_y 168, gap 80
            for i in range(3):
                y = 168 + i*80
                r = pygame.Rect(config.SCREEN_WIDTH//2-200, y, 400, 66)
                if r.collidepoint(mx,my):
                    self.account_gate_index = i
                    audio.play("hover",0.4)
                    self._gate_select()
                    break
        elif self.state in ("account_register","account_login"):
            box = pygame.Rect(config.SCREEN_WIDTH//2-270, config.SCREEN_HEIGHT//2-170, 540, 360)
            inp0 = pygame.Rect(box.x+40, box.y+74, box.width-80, 44)
            inp1 = pygame.Rect(box.x+40, box.y+138, box.width-80, 44)
            btn = pygame.Rect(box.centerx-110, box.y+214, 220, 44)
            if inp0.collidepoint(mx,my):
                if self.state == "account_register": self.reg_field = 0
                else: self.login_field = 0
                audio.play("hover",0.3)
            elif inp1.collidepoint(mx,my):
                if self.state == "account_register": self.reg_field = 1
                else: self.login_field = 1
                audio.play("hover",0.3)
            elif btn.collidepoint(mx,my):
                if self.state == "account_register": self._submit_register()
                else: self._submit_login()
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
                        self._try_enter_online()
                    elif i==1:
                        self.start_vs_bot()
                        audio.play("click")
                    else:
                        self.state="menu"
                        audio.play("click")
                    break
        elif self.state=="online_menu":
            # davet popup öncelikli
            if self.pending_invite:
                box = pygame.Rect(config.SCREEN_WIDTH//2-180, config.SCREEN_HEIGHT//2-60, 360, 120)
                b_yes = pygame.Rect(box.x+20, box.y+70, 150, 36)
                b_no = pygame.Rect(box.x+190, box.y+70, 150, 36)
                if b_yes.collidepoint(mx,my):
                    self.accept_invite()
                elif b_no.collidepoint(mx,my):
                    self.reject_invite()
                return
            box = pygame.Rect(config.SCREEN_WIDTH//2-260, 106, 520, 306)
            btn = pygame.Rect(box.x+24, box.y+118, box.width-48, 42)
            if btn.collidepoint(mx,my):
                self._online_search()
            if self.online_info:
                mbtn = pygame.Rect(box.x+24, box.bottom-48, box.width-48, 36)
                if mbtn.collidepoint(mx,my):
                    self.send_invite()
        elif self.state=="lobby":
            # HAZIR ve AYRIL butonları
            box = pygame.Rect(config.SCREEN_WIDTH//2-240, config.SCREEN_HEIGHT//2-110, 480, 260)
            b_ready = pygame.Rect(box.x+30, box.y+180, 190, 42)
            b_leave = pygame.Rect(box.x+260, box.y+180, 190, 42)
            if b_ready.collidepoint(mx,my):
                self.toggle_ready()
            elif b_leave.collidepoint(mx,my):
                self.leave_lobby()
            # davet popup da burada
            if self.pending_invite:
                box2 = pygame.Rect(config.SCREEN_WIDTH//2-180, config.SCREEN_HEIGHT//2-60, 360, 120)
                b_yes = pygame.Rect(box2.x+20, box2.y+70, 150, 36)
                b_no = pygame.Rect(box2.x+190, box2.y+70, 150, 36)
                if b_yes.collidepoint(mx,my):
                    self.accept_invite()
                elif b_no.collidepoint(mx,my):
                    self.reject_invite()
        elif self.state in ("vs_bot","vs_online"):
            # ESC ile menü — click boş
            pass
        elif self.state == "vs_result":
            # draw_vs_result: box 440x260, b1 x+30 y+190 190x44, b2 x+230 y+190 190x44
            box = pygame.Rect(config.SCREEN_WIDTH//2-220, config.SCREEN_HEIGHT//2-110, 440, 220)
            b1 = pygame.Rect(box.x+30, box.y+150, 190, 44)
            b2 = pygame.Rect(box.x+220, box.y+150, 190, 44)
            if b1.collidepoint(mx,my):
                self.start_vs_bot()
                audio.play("click")
            elif b2.collidepoint(mx,my):
                self.state = "play_select"
                self.vs_mode = None
                self.vs_bot = None
                self.vs_finish_y = None
                self.vs_result = None
                audio.play("click")

    def handle_mouse_hover(self, pos):
        mx,my = pos
        if self.help_open:
            if self._help_close_rect().collidepoint(mx,my):
                if self.hover_index != -2:
                    self.hover_index = -2
                    audio.play("hover",0.3)
            else:
                self.hover_index = -1
            return
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
        elif self.state=="account_gate":
            for i in range(3):
                y = 168 + i*80
                r = pygame.Rect(config.SCREEN_WIDTH//2-200, y, 400, 66)
                if r.collidepoint(mx,my):
                    if self.hover_index != i:
                        self.hover_index = i
                        audio.play("hover",0.3)
                    return
            self.hover_index = -1

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
            elif self.state=="account_gate":
                self.draw_account_gate(surf, theme)
            elif self.state=="account_register":
                self.draw_account_form(surf, theme, "register")
            elif self.state=="account_login":
                self.draw_account_form(surf, theme, "login")
            elif self.state=="play_select":
                self.draw_play_select(surf, theme)
            elif self.state=="online_menu":
                self.draw_online(surf, theme)
            elif self.state in ("vs_bot","vs_online"):
                # VS yarış — aynı dünya + rakip + bitiş çizgisi
                self.world.draw(surf, self.camera.y, self.level_info)
                # bitiş çizgisi — vs_bot için görünür
                if self.state == "vs_bot" and getattr(self, "vs_finish_y", None) is not None:
                    try:
                        self.draw_vs_finish_line(surf, theme)
                    except: pass
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
                        rx = int(self.vs_remote.get("x", self.player.x+30))
                        ry = int(self.vs_remote.get("y", self.player.y) - self.camera.y)
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
            elif self.state == "vs_result":
                # vs_result arka plan: donmuş yarış + sonuç overlay
                self.world.draw(surf, self.camera.y, self.level_info)
                if self.state == "vs_result" and getattr(self, "vs_finish_y", None) is not None:
                    try:
                        self.draw_vs_finish_line(surf, theme)
                    except: pass
                if hasattr(self, 'monster'):
                    try: self.monster.draw(surf, self.camera.y)
                    except: pass
                self.particles.draw(surf, self.camera.y)
                if self.vs_bot:
                    try:
                        bot_char = getattr(self, 'vs_bot_char', self.get_char_data())
                        self.vs_bot.draw(surf, self.camera.y, bot_char, self.get_equipped(), theme)
                    except: pass
                self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
                self.draw_hud(surf, theme)
                self.draw_vs_hud(surf, theme)
                self.draw_vs_result(surf, theme)
            elif self.state == "lobby":
                self.draw_lobby(surf, theme)
            # davet popup her durumda (lobby hariç üstte)
            if self.pending_invite and self.state != "lobby":
                self.draw_invite_popup(surf, theme)
        except Exception as e:
            print(f"[Draw error] {e}")
            surf.fill((20,20,20))
            err = self.font_small.render(f"Cizim hatasi: {e}", True, (255,80,80))
            surf.blit(err, (20,20))

        # NASIL OYNANIR? modal — her durumun üstüne çizilir
        if self.help_open:
            try:
                self.draw_help_modal(surf, theme)
            except Exception as e:
                print(f"[Draw help error] {e}")

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
        pause_hint = self.font_tiny.render("SPACE Pause  •  ↑ Jump  •  ↓ Roll  •  H Yardım", True, (196,196,202))
        surf.blit(pause_hint, (config.SCREEN_WIDTH//2 - pause_hint.get_width()//2, 33))

    def draw_tutorial(self, surf):
        box = pygame.Rect(18, 62, 286, 96)
        gfx.draw_soft_shadow(surf, box, radius=12, alpha=32)
        gfx.glass_panel(surf, box, fill=(255,255,242,230), border=(0,0,0,160), radius=11)
        title = self.font_small.render("NASIL OYNANIR?  (H ile aç)", True, (22,22,22))
        surf.blit(title, (box.x+12, box.y+10))
        pygame.draw.line(surf,(0,0,0,18),(box.x+10, box.y+26),(box.right-10, box.y+26),1)
        lines = ["← → : Hareket  — akıcı, ivmeli", "↑ : Zıpla (engel üstünde)", "↓ : Hızlı düş / Yuvarlan", "Boşluklardan süzül — sıkışma!"]
        y = box.y+30
        for l in lines:
            dot = self.font_tiny.render("• "+l, True, (48,48,48))
            surf.blit(dot, (box.x+12, y)); y+=14

    def draw_help_modal(self, surf, theme):
        """NASIL OYNANIR? — tam ekran modal. Menüden ve oyundan (H) açılır."""
        W, H = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        dark = "siyah" in theme["id"]
        # arka plan karartma
        over = pygame.Surface((W, H), pygame.SRCALPHA)
        over.fill((0,0,0, 168))
        surf.blit(over, (0,0))
        gfx.draw_vignette(surf, intensity=0.26)
        # ana panel
        box = pygame.Rect(70, 44, W-140, H-118)
        gfx.draw_soft_shadow(surf, box, radius=26, alpha=70)
        gfx.glass_panel(surf, box, fill=(255,255,252,244) if not dark else (30,30,36,244), border=(0,0,0,140), radius=18)
        # üst altın şerit
        pygame.draw.rect(surf, (255,215,0), pygame.Rect(box.x, box.y, box.width, 7), border_radius=4)
        # başlık — 3D
        title = self.font_huge.render("NASIL OYNANIR?", True, (16,16,20) if not dark else (255,255,255))
        sh = self.font_huge.render("NASIL OYNANIR?", True, (0,0,0,60))
        surf.blit(sh, (box.centerx - title.get_width()//2 + 2, box.y + 12 + 2))
        surf.blit(title, (box.centerx - title.get_width()//2, box.y + 12))
        sub = self.font_small.render("Dikey düşüş — aşağı in, engellerden süzül, coin topla, hayatta kal!", True, (88,88,94) if not dark else (176,176,184))
        surf.blit(sub, (box.centerx - sub.get_width()//2, box.y + 58))

        def keycap(x, y, w, h, label, hot=False):
            r = pygame.Rect(x, y, w, h)
            base = (96,150,255) if hot else (228,228,236)
            top = tuple(min(255, c+22) for c in base) if not hot else (150,196,255)
            k = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            for yy in range(r.height):
                ts = yy/r.height
                rr=int(top[0]*(1-ts)+base[0]*ts); gg=int(top[1]*(1-ts)+base[1]*ts); bb=int(top[2]*(1-ts)+base[2]*ts)
                pygame.draw.line(k,(rr,gg,bb),(0,yy),(r.width,yy))
            mask = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            pygame.draw.rect(mask,(255,255,255),(0,0,r.width,r.height), border_radius=int(r.height*0.32))
            k.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(k, r.topleft)
            # alt gölge kenarı
            edge = pygame.Rect(r.x, r.bottom-3, r.width, 3)
            pygame.draw.rect(surf, (0,0,0,70), edge, border_radius=2)
            pygame.draw.rect(surf, (0,0,0,150), r, width=2, border_radius=int(r.height*0.32))
            if hot:
                gfx.draw_glow(surf, r.center, 14, (90,150,255), 18)
                pygame.draw.rect(surf, (120,170,255), r, width=2, border_radius=int(r.height*0.32))
            t = self.font_med.render(label, True, (16,16,22))
            surf.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))
            return r

        col_w = (box.width - 60) // 2
        # --- SOL: KONTROLLER ---
        ctrl_card = pygame.Rect(box.x+20, box.y+92, col_w, 292)
        gfx.draw_soft_shadow(surf, ctrl_card, radius=14, alpha=26)
        pygame.draw.rect(surf, (250,250,253) if not dark else (44,44,52), ctrl_card, border_radius=13)
        pygame.draw.rect(surf, (0,0,0,90), ctrl_card, width=2, border_radius=13)
        ch = self.font_big.render("KONTROLLER", True, (16,16,20) if not dark else (255,255,255))
        surf.blit(ch, (ctrl_card.centerx - ch.get_width()//2, ctrl_card.y+14))
        gfx.draw_glow(surf, (ctrl_card.centerx, ctrl_card.y+30), 16, (90,150,255), 14)
        keys = [("← → / AD", "Hareket — ivmeli, akıcı"),
                ("↑ / W", "Zıpla  (engel üstünde)"),
                ("↓ / S", "Hızlı düş / Yuvarlan"),
                ("SPACE", "Oyunu duraklat"),
                ("H", "Bu yardımı aç"),
                ("M", "İzmir Marşı ♫")]
        y = ctrl_card.y + 56
        for label, desc in keys:
            kc = keycap(ctrl_card.x+18, y, 118, 30, label, hot=(label in ("↑ / W","H")))
            dt = self.font_small.render(desc, True, (70,70,78) if not dark else (196,196,204))
            surf.blit(dt, (kc.right+14, y + (30 - dt.get_height())//2))
            y += 38
        # --- SAĞ: OYUN KURALLARI ---
        rule_card = pygame.Rect(box.x+20+col_w+20, box.y+92, col_w, 292)
        gfx.draw_soft_shadow(surf, rule_card, radius=14, alpha=26)
        pygame.draw.rect(surf, (250,250,253) if not dark else (44,44,52), rule_card, border_radius=13)
        pygame.draw.rect(surf, (0,0,0,90), rule_card, width=2, border_radius=13)
        rh = self.font_big.render("OYUN REHBERİ", True, (16,16,20) if not dark else (255,255,255))
        surf.blit(rh, (rule_card.centerx - rh.get_width()//2, rule_card.y+14))
        rules = [
            ("TEK CAN", "Engine sıkışırsan oyun biter — dikkatli süzül!"),
            ("COİN", "Altınları topla; Mağazada eşya ve karakter aç."),
            ("SONSUZ MOD", "Mesafe attıkça seviye yükselir, yeni katmanlar açılır."),
            ("BÖLÜMLER", "Canavardan kaç, bitiş portalına ulaş, yıldız kazan."),
            ("VS YARIŞ", "BOT veya Online rakibi geç — bitiş çizgisine ilk varan kazanır."),
        ]
        y = rule_card.y + 50
        for hd, tx in rules:
            dot = self.font_med.render("●", True, (255,215,0))
            surf.blit(dot, (rule_card.x+16, y+1))
            ht = self.font_small.render(hd, True, (20,78,28) if not dark else (120,220,130))
            surf.blit(ht, (rule_card.x+36, y))
            # sığdırmak için kelime kaydırması
            words = tx.split(" ")
            lines2 = []
            curline = ""
            for wd in words:
                test = (curline+" "+wd).strip()
                if self.font_tiny.size(test)[0] <= rule_card.width-52:
                    curline = test
                else:
                    if curline: lines2.append(curline)
                    curline = wd
            if curline: lines2.append(curline)
            dy = y + 16
            for ln in lines2:
                ls = self.font_tiny.render(ln, True, (96,96,104) if not dark else (200,200,208))
                surf.blit(ls, (rule_card.x+36, dy))
                dy += 13
            y = dy + 10
        # --- ALT BİLGİ ŞERİDİ ---
        stat_card = pygame.Rect(box.x+20, box.y+92+292+18, box.width-40, 60)
        pygame.draw.rect(surf, (255,246,220) if not dark else (52,52,42), stat_card, border_radius=12)
        pygame.draw.rect(surf, (255,215,0,120), stat_card, width=2, border_radius=12)
        best = self.save.get("best_distance",0)
        lvl = self.save.get("level",1)
        coins = self.save.get("total_coins",0)
        char = self.get_char_data()["name"]
        st = f"COIN: {coins}   •   SEVİYE: {lvl} ({self.level_info['name']})   •   EN İYİ: {best:.1f} m   •   KARAKTER: {char}"
        sts = self.font_med.render(st, True, (60,48,10) if not dark else (255,238,160))
        surf.blit(sts, (stat_card.centerx - sts.get_width()//2, stat_card.centery - sts.get_height()//2 + 1))
        if self.level_mode is not None:
            note = self.font_tiny.render(f"Şu anda bölüm {self.level}: amacın bitişe ulaşıp canavardan kaçmak.", True, (70,60,20) if not dark else (230,220,150))
            surf.blit(note, (stat_card.centerx - note.get_width()//2, stat_card.bottom - 16))
        # --- KAPAT ---
        cbtn = self._help_close_rect()
        hover = cbtn.collidepoint(pygame.mouse.get_pos())
        gfx.draw_soft_shadow(surf, cbtn, radius=12, alpha=26 if hover else 16)
        col = (255,215,0) if hover else (48,48,54)
        top = (255,228,110) if hover else (80,80,88)
        b = pygame.Surface((cbtn.width, cbtn.height), pygame.SRCALPHA)
        for yy in range(cbtn.height):
            ts = yy/cbtn.height
            rr=int(top[0]*(1-ts)+col[0]*ts); gg=int(top[1]*(1-ts)+col[1]*ts); bb=int(top[2]*(1-ts)+col[2]*ts)
            pygame.draw.line(b,(rr,gg,bb),(0,yy),(cbtn.width,yy))
        mask = pygame.Surface((cbtn.width, cbtn.height), pygame.SRCALPHA)
        pygame.draw.rect(mask,(255,255,255),(0,0,cbtn.width,cbtn.height), border_radius=11)
        b.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(b, cbtn.topleft)
        pygame.draw.rect(surf, (255,215,0) if hover else (0,0,0,170), cbtn, width=2 if not hover else 3, border_radius=11)
        if hover:
            gfx.draw_glow(surf, cbtn.center, 20, (255,215,0), 24)
        ct = self.font_med.render("KAPAT", True, (0,0,0))
        surf.blit(ct, (cbtn.centerx - ct.get_width()//2, cbtn.centery - ct.get_height()//2))
        tip = self.font_tiny.render("ESC / H / ENTER / SPACE ile kapat", True, (112,112,120) if not dark else (168,168,176))
        surf.blit(tip, (config.SCREEN_WIDTH//2 - tip.get_width()//2, cbtn.y - 20))

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
        hint = self.font_small.render("←→ Kategori  |  ↑↓/W-S Kaydır  |  ENTER Satın Al/Kuşan  |  ESC Menu", True, theme["hud"])
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
        lay = self._list_layout("shop")
        lst = lay["lst"]
        self.shop_scroll = max(0, min(self.shop_scroll, lay["max_scroll"]))
        list_y = lay["list_y"]
        step = lay["step"]
        row_h = lay["row_h"]
        vb = lay["viewport_bottom"]
        # liste alanını kırp: sekmeler/title bozulmasın
        old_clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, list_y, config.SCREEN_WIDTH, vb - list_y))
        for idx,item in enumerate(lst):
            y = list_y + idx*step - self.shop_scroll
            if y + row_h < list_y or y > vb:
                continue
            r=pygame.Rect(60, y, config.SCREEN_WIDTH-120, row_h)
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
            try:
                iconic = item_icons.get_item_icon(item)
                surf.blit(iconic, (icon_r.centerx - iconic.get_width()//2, icon_r.centery - iconic.get_height()//2))
            except Exception:
                ic=self.font_big.render(item["icon"], True, (28,28,30))
                surf.blit(ic, (icon_r.centerx-ic.get_width()//2, icon_r.centery-ic.get_height()//2))
            name=self.font_med.render(item["name"], True, (18,18,22) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (238,238,242))
            surf.blit(name, (r.x+80, r.y+14))
            owned=item["id"] in self.save["owned_items"]
            if owned:
                using=False
                for k,sk in (("hat","selected_hat"),("bag","selected_bag"),("glasses","selected_glasses"),("cane","selected_cane")):
                    if item["id"] in config.SHOP_ITEMS[k] and self.save.get(sk)==item["id"]:
                        using=True; break
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
        surf.set_clip(old_clip)
        # scrollbar
        if lay["max_scroll"] > 0:
            track_h = vb - list_y
            sb_x = config.SCREEN_WIDTH - 34
            pygame.draw.rect(surf, (0,0,0,70), pygame.Rect(sb_x, list_y, 6, track_h), border_radius=3)
            thumb_h = max(28, int(track_h * track_h / (lay["max_scroll"] + track_h)))
            thumb_y = list_y + int((track_h - thumb_h) * (self.shop_scroll / lay["max_scroll"]))
            pygame.draw.rect(surf, (255,215,0) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else tuple(min(255,c+40) for c in theme["button_hover"]), pygame.Rect(sb_x, thumb_y, 6, thumb_h), border_radius=3)

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
        hint=self.font_small.render("←→ Kategori  |  ↑↓/W-S Kaydır  |  ENTER Kuşan/Çıkar  |  ESC Menu", True, theme["hud"])
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
        lay = self._list_layout("inventory")
        key=["hat","bag","glasses","cane"][self.inv_tab]
        owned=lay["lst"]
        if not owned:
            msg=self.font_med.render("Bu kategoride eşyan yok — Mağazaya git!", True, theme["hud"])
            surf.blit(msg, (config.SCREEN_WIDTH//2 - msg.get_width()//2, 220))
            tip=self.font_small.render("Coin topla ve Mağazadan satın al", True, theme["hud"])
            surf.blit(tip, (config.SCREEN_WIDTH//2 - tip.get_width()//2, 250))
        else:
            self.inv_scroll = max(0, min(self.inv_scroll, lay["max_scroll"]))
            list_y = lay["list_y"]
            step = lay["step"]
            row_h = lay["row_h"]
            vb = lay["viewport_bottom"]
            sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
            old_clip = surf.get_clip()
            surf.set_clip(pygame.Rect(0, list_y, config.SCREEN_WIDTH, vb - list_y))
            for idx,item in enumerate(owned):
                y = list_y + idx*step - self.inv_scroll
                if y + row_h < list_y or y > vb:
                    continue
                r=pygame.Rect(60,y,config.SCREEN_WIDTH-120,row_h)
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
                try:
                    iconic = item_icons.get_item_icon(item)
                    surf.blit(iconic, (icon_r.centerx-iconic.get_width()//2, icon_r.centery-iconic.get_height()//2))
                except Exception:
                    ic=self.font_big.render(item["icon"], True, (0,0,0))
                    surf.blit(ic, (icon_r.centerx-ic.get_width()//2, icon_r.centery-ic.get_height()//2))
                name=self.font_med.render(item["name"], True, (0,0,0) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (255,255,255))
                surf.blit(name, (r.x+80,r.y+14))
                using=self.save.get(sel_key)==item["id"]
                st=self.font_small.render("● KULLANILIYOR" if using else "ENTER ile Kuşan", True, (0,150,0) if using else (90,90,90))
                surf.blit(st, (r.x+80,r.y+40))
            surf.set_clip(old_clip)
            if lay["max_scroll"] > 0:
                track_h = vb - list_y
                sb_x = config.SCREEN_WIDTH - 34
                pygame.draw.rect(surf, (0,0,0,70), pygame.Rect(sb_x, list_y, 6, track_h), border_radius=3)
                thumb_h = max(28, int(track_h * track_h / (lay["max_scroll"] + track_h)))
                thumb_y = list_y + int((track_h - thumb_h) * (self.inv_scroll / lay["max_scroll"]))
                pygame.draw.rect(surf, (255,215,0) if theme["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else tuple(min(255,c+40) for c in theme["button_hover"]), pygame.Rect(sb_x, thumb_y, 6, thumb_h), border_radius=3)

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

    def draw_account_gate(self, surf, theme):
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        gfx.draw_vignette(surf, intensity=0.2)
        title = self.font_huge.render("FREEFALL", True, theme["hud"])
        for off in (3,2):
            sh = self.font_huge.render("FREEFALL", True, (0,0,0))
            sh.set_alpha(90 if off==2 else 60)
            surf.blit(sh, (config.SCREEN_WIDTH//2 - title.get_width()//2 + off, 60+off))
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 58))
        gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, 80), 52, (255,215,0), 16)
        sub = self.font_med.render("HESAP KAPISI — oyun başlamadan hesabını seç", True, theme["hud"])
        surf.blit(sub, (config.SCREEN_WIDTH//2 - sub.get_width()//2, 116))
        opts = self.account_gate_options
        mx,my = pygame.mouse.get_pos()
        for i, opt in enumerate(opts):
            y = 168 + i*80
            r = pygame.Rect(config.SCREEN_WIDTH//2-200, y, 400, 66)
            sel = i==self.account_gate_index
            hover = r.collidepoint(mx,my)
            gfx.draw_soft_shadow(surf, r, radius=12, alpha=24 if sel or hover else 12)
            base = theme["button"]
            top = (255,228,110) if sel else tuple(min(255,c+14) for c in base)
            bot = (255,185,0) if sel else tuple(max(0,c-10) for c in base)
            btn_s = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            for yy in range(r.height):
                ts = yy/r.height
                btn_s.fill((int(top[0]*(1-ts)+bot[0]*ts), int(top[1]*(1-ts)+bot[1]*ts), int(top[2]*(1-ts)+bot[2]*ts)), (0,yy,r.width,1))
            mask = pygame.Surface((r.width,r.height), pygame.SRCALPHA)
            pygame.draw.rect(mask,(255,255,255),(0,0,r.width,r.height), border_radius=12)
            btn_s.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(btn_s, r.topleft)
            pygame.draw.rect(surf, (255,215,0) if sel else (0,0,0), r, width=3 if sel else 2, border_radius=12)
            pygame.draw.line(surf,(255,255,255,80),(r.x+10,r.y+5),(r.right-10,r.y+5),1)
            t = self.font_big.render(opt, True, (28,18,4) if sel or hover else (0,0,0) if theme["id"]=="beyaz" else (255,255,255))
            surf.blit(t, (r.centerx - t.get_width()//2, r.centery - t.get_height()//2))
            d = self.font_tiny.render(["Kayıt ol, 5 haneli ID server'dan gelir","Nickname veya Player ID + şifre ile giriş","Çevrimdışı — ONLINE kilitli, server'a bağlanmaz"][i], True, (60,60,64) if sel else (110,110,112))
            surf.blit(d, (r.centerx - d.get_width()//2, r.y + 46))
        if self.account_error:
            err = self.font_small.render(self.account_error, True, (200,30,30))
            surf.blit(err, (config.SCREEN_WIDTH//2 - err.get_width()//2, 168 + 3*80 + 12))
        hint_col = tuple(max(0,min(255,c)) for c in theme["hud"])
        h = self.font_small.render("↑↓ Seç  •  ENTER Onayla  •  Mouse Tıkla", True, hint_col)
        h.set_alpha(190)
        surf.blit(h, (config.SCREEN_WIDTH//2 - h.get_width()//2, config.SCREEN_HEIGHT-26))

    def _account_form_rects(self):
        box = pygame.Rect(config.SCREEN_WIDTH//2-270, config.SCREEN_HEIGHT//2-170, 540, 360)
        inp0 = pygame.Rect(box.x+40, box.y+74, box.width-80, 44)
        inp1 = pygame.Rect(box.x+40, box.y+138, box.width-80, 44)
        btn = pygame.Rect(box.centerx-110, box.y+214, 220, 44)
        return box, inp0, inp1, btn

    def draw_account_form(self, surf, theme, mode):
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        gfx.draw_vignette(surf, intensity=0.18)
        is_reg = mode == "register"
        title_txt = "HESAP OLUŞTUR" if is_reg else "GİRİŞ YAP"
        sub_txt = "Server 5 haneli ID üretir ve şifreni hash'ler" if is_reg else "Nickname veya Player ID + şifre ile giriş"
        box, inp0, inp1, btn = self._account_form_rects()
        gfx.draw_soft_shadow(surf, box, radius=18, alpha=48)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=16)
        pygame.draw.rect(surf, (255,215,0), pygame.Rect(box.x, box.y, box.width, 6), border_radius=4)
        title = self.font_big.render(title_txt, True, (18,18,20))
        surf.blit(title, (box.centerx - title.get_width()//2, box.y+14))
        sub = self.font_small.render(sub_txt, True, (90,90,96))
        surf.blit(sub, (box.centerx - sub.get_width()//2, box.y+42))
        field = self.reg_field if is_reg else self.login_field
        nick_val = self.reg_nick if is_reg else self.login_ident
        pass_val = self.reg_pass if is_reg else self.login_pass
        lbl0 = "NICKNAME" if is_reg else "NICKNAME VEYA OYUNCU ID"
        # input 0
        gfx.draw_soft_shadow(surf, inp0, radius=10, alpha=18)
        pygame.draw.rect(surf, (255,255,255), inp0, border_radius=10)
        l0 = self.font_tiny.render(lbl0, True, (120,120,126))
        surf.blit(l0, (inp0.x+12, inp0.y-15))
        pygame.draw.rect(surf, (255,215,0) if field==0 else (0,0,0), inp0, width=2, border_radius=10)
        pygame.draw.line(surf, (255,255,255,90), (inp0.x+10, inp0.y+5), (inp0.right-10, inp0.y+5), 1)
        blink = (pygame.time.get_ticks()//520)%2==0
        show0 = nick_val + ("|" if (field==0 and blink) else "")
        t0 = self.font_big.render(show0, True, (0,0,0))
        surf.blit(t0, (inp0.x+16, inp0.centery - t0.get_height()//2))
        if not nick_val:
            ph = self.font_small.render("örn: Merve", True, (150,150,150))
            surf.blit(ph, (inp0.x+16, inp0.centery - ph.get_height()//2))
        # input 1 (şifre — maskeli)
        l1 = self.font_tiny.render("ŞİFRE", True, (120,120,126))
        surf.blit(l1, (inp1.x+12, inp1.y-15))
        gfx.draw_soft_shadow(surf, inp1, radius=10, alpha=18)
        pygame.draw.rect(surf, (255,255,255), inp1, border_radius=10)
        pygame.draw.rect(surf, (255,215,0) if field==1 else (0,0,0), inp1, width=2, border_radius=10)
        pygame.draw.line(surf, (255,255,255,90), (inp1.x+10, inp1.y+5), (inp1.right-10, inp1.y+5), 1)
        masked = "•" * len(pass_val)
        show1 = masked + ("|" if (field==1 and blink) else "")
        t1 = self.font_big.render(show1, True, (0,0,0))
        surf.blit(t1, (inp1.x+16, inp1.centery - t1.get_height()//2))
        if not pass_val:
            ph1 = self.font_small.render("en az 4 karakter", True, (150,150,150))
            surf.blit(ph1, (inp1.x+16, inp1.centery - ph1.get_height()//2))
        # gönder butonu
        mx,my = pygame.mouse.get_pos()
        hover_btn = btn.collidepoint(mx,my)
        gfx.draw_soft_shadow(surf, btn, radius=10, alpha=22 if hover_btn else 14)
        col = (255,215,0) if hover_btn else (30,30,36)
        top = (255,228,110) if hover_btn else (58,58,64)
        b_s = pygame.Surface((btn.width, btn.height), pygame.SRCALPHA)
        for y in range(btn.height):
            ts = y/btn.height
            b_s.fill((int(top[0]*(1-ts)+col[0]*ts), int(top[1]*(1-ts)+col[1]*ts), int(top[2]*(1-ts)+col[2]*ts)), (0,y,btn.width,1))
        mask = pygame.Surface((btn.width,btn.height), pygame.SRCALPHA)
        pygame.draw.rect(mask,(255,255,255),(0,0,btn.width,btn.height), border_radius=10)
        b_s.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(b_s, btn.topleft)
        pygame.draw.rect(surf, (255,215,0) if hover_btn else (0,0,0), btn, width=2, border_radius=10)
        btn_txt = "HESAP OLUŞTUR" if is_reg else "GİRİŞ"
        t2 = self.font_med.render(btn_txt, True, (0,0,0) if hover_btn else (255,255,255))
        surf.blit(t2, (btn.centerx - t2.get_width()//2, btn.centery - t2.get_height()//2))
        # durum / hata
        if self.account_busy:
            busy = self.font_small.render(self.account_error, True, (120,90,20))
            surf.blit(busy, (box.centerx - busy.get_width()//2, btn.bottom+10))
        elif self.account_error:
            err = self.font_small.render(self.account_error, True, (200,30,30))
            surf.blit(err, (box.centerx - err.get_width()//2, btn.bottom+10))
        hint = self.font_tiny.render("TAB alan değiştir  •  ENTER onayla  •  ESC Geri (kapıya)", True, tuple(max(0,min(255,c)) for c in theme["hud"]))
        surf.blit(hint, (box.centerx - hint.get_width()//2, box.bottom+14))

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
        guest = self.is_guest()
        card = pygame.Rect(config.SCREEN_WIDTH//2-180, 78, 360, 34)
        pygame.draw.rect(surf, (0,0,0,48), card, border_radius=9)
        pygame.draw.rect(surf, (255,215,0,110), card, width=1, border_radius=9)
        if guest:
            txt = self.font_med.render(f"{nick}  •  MİSAFİR (ONLINE kilitli)", True, (180,140,60))
        else:
            txt = self.font_med.render(f"{nick}  •  ID: {pid}", True, (255,255,255) if "siyah" in theme["id"] else (30,30,34))
        surf.blit(txt, (card.centerx - txt.get_width()//2, card.centery - txt.get_height()//2))
        if guest:
            opts = [("ONLINE 🔒", "Hesap ile giriş yap — misafir kilitli"), ("BİLGİSAYARA KARŞI", "Çevrimdışı BOT ile yarış"), ("GERİ", "")]
        else:
            opts = [("ONLINE", "5 haneli ID ile oyuncu bul"), ("BİLGİSAYARA KARŞI", "Çevrimdışı BOT ile yarış"), ("GERİ", "")]
        mx,my = pygame.mouse.get_pos()
        for i,(label,desc) in enumerate(opts):
            y = 132 + i*86
            r = pygame.Rect(config.SCREEN_WIDTH//2-200, y, 400, 68)
            sel = i==self.play_select_index
            hover = r.collidepoint(mx,my)
            locked = guest and i==0
            gfx.draw_soft_shadow(surf, r, radius=12, alpha=22 if sel or hover else 14)
            base = theme["button"]
            top = (255,228,110) if sel else tuple(min(255,c+14) for c in base)
            bot = (255,185,0) if sel else tuple(max(0,c-10) for c in base)
            if locked and not sel:
                top = tuple(int(c*0.55) for c in top)
                bot = tuple(int(c*0.55) for c in bot)
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
            if locked and sel:
                t1 = self.font_big.render(label, True, (90,60,20))
            surf.blit(t1, (r.centerx - t1.get_width()//2, r.y+14))
            if desc:
                t2 = self.font_tiny.render(desc, True, (60,60,64) if sel else (90,90,90))
                surf.blit(t2, (r.centerx - t2.get_width()//2, r.y+40))
        if self.play_select_msg:
            msg = self.font_small.render(self.play_select_msg, True, (200,120,40))
            surf.blit(msg, (config.SCREEN_WIDTH//2 - msg.get_width()//2, 132 + 3*86))
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
            # DAVET ET
            mbtn = pygame.Rect(box.x+24, box.bottom-48, box.width-48, 36)
            hover2 = mbtn.collidepoint(mx,my)
            # davet gönderildiyse farklı renk
            is_sent = self.invite_sent == pid
            col_inv = (80,160,255) if is_sent else (0,160,80) if hover2 else (0,136,68)
            pygame.draw.rect(surf, col_inv, mbtn, border_radius=9)
            pygame.draw.rect(surf, (0,0,0), mbtn, width=2, border_radius=9)
            if hover2: pygame.draw.rect(surf, (255,215,0), mbtn, width=2, border_radius=9)
            txt_inv = "DAVET GÖNDERİLDİ" if is_sent else "DAVET ET"
            t5 = self.font_med.render(txt_inv, True, (255,255,255))
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
        # ilerleme % — sadece vs_bot için net 0-100
        if self.state == "vs_bot" and getattr(self, "vs_finish_y", None) is not None:
            total = max(1, self.vs_finish_y - self.level_start_y)
            done = max(0, self.player.y - self.level_start_y)
            prog = max(0.0, min(1.0, done / total))
            percent = int(prog * 100)
            if prog >= 1.0:
                percent = 100
            prog_txt = self.font_small.render(f"İLERLEME: {percent}%", True, (255,215,0))
            surf.blit(prog_txt, (config.SCREEN_WIDTH//2 - prog_txt.get_width()//2, hud_y+34))
            bar = pygame.Rect(config.SCREEN_WIDTH//2-60, hud_y+50, 120, 6)
            pygame.draw.rect(surf, (40,40,46), bar, border_radius=3)
            fill = pygame.Rect(bar.x+1, bar.y+1, int((bar.width-2)*prog), bar.height-2)
            if fill.width>0:
                pygame.draw.rect(surf, (255,215,0), fill, border_radius=3)
            pygame.draw.rect(surf, (0,0,0), bar, width=1, border_radius=3)
        # bağlantı uyarısı online
        if self.state=="vs_online" and not self.vs_remote:
            warn = self.font_small.render("Bağlantı bekleniyor...", True, (255,220,100))
            surf.blit(warn, (config.SCREEN_WIDTH//2 - warn.get_width()//2, hud_y+34))

    def draw_vs_finish_line(self, surf, theme):
        if self.vs_finish_y is None:
            return
        fy = int(self.vs_finish_y - self.camera.y)
        if fy < -40 or fy > config.SCREEN_HEIGHT + 40:
            return
        # görünür bitiş çizgisi — duvardan duvara dama + ışık
        rect = pygame.Rect(config.WALL_THICKNESS, fy - 8, config.SCREEN_WIDTH - 2*config.WALL_THICKNESS, 16)
        gfx.draw_glow(surf, rect.center, 28, (255,215,0), 24)
        # dama deseni
        cell = 22
        for x in range(rect.x, rect.right, cell):
            col = (255,255,255) if ((x - rect.x)//cell) % 2 == 0 else (0,0,0)
            sub = pygame.Rect(x, rect.y, min(cell, rect.right - x), rect.height)
            pygame.draw.rect(surf, col, sub)
        pygame.draw.rect(surf, (255,215,0), rect, width=3)
        pygame.draw.rect(surf, (0,0,0), rect, width=1)
        # BITIS etiketi
        label = self.font_med.render("BİTİŞ", True, (0,0,0))
        bg = pygame.Rect(rect.centerx - label.get_width()//2 - 10, rect.y - 20, label.get_width()+20, 18)
        pygame.draw.rect(surf, (255,215,0), bg, border_radius=6)
        pygame.draw.rect(surf, (0,0,0), bg, width=2, border_radius=6)
        surf.blit(label, (bg.centerx - label.get_width()//2, bg.centery - label.get_height()//2))
        # mesafe kalan göstergesi üstte
        if self.state in ("vs_bot","vs_online"):
            remain = max(0, (self.vs_finish_y - self.player.y) / config.PIXELS_PER_METER)
            txt = self.font_tiny.render(f"Bitişe {remain:.0f} m", True, (255,255,200))
            surf.blit(txt, (rect.centerx - txt.get_width()//2, rect.bottom + 4))

    def draw_vs_result(self, surf, theme):
        # yarı saydam overlay
        over = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        over.fill((0,0,0,118))
        surf.blit(over, (0,0))
        box = pygame.Rect(config.SCREEN_WIDTH//2-220, config.SCREEN_HEIGHT//2-110, 440, 220)
        gfx.draw_soft_shadow(surf, box, radius=16, alpha=48)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=14)
        is_win = self.vs_result == "win"
        title = "KAZANDIN!" if is_win else "KAYBETTİN!"
        col = (40,160,60) if is_win else (200,40,40)
        tcol = (255,215,0) if is_win else (255,220,220)
        title_surf = self.font_huge.render(title, True, tcol)
        # glow
        gfx.draw_glow(surf, box.center, 46, col, 26)
        surf.blit(title_surf, (box.centerx - title_surf.get_width()//2, box.y+22))
        # süre ve mesafe
        time_txt = self.font_small.render(f"Süre: {self.vs_race_timer:.1f} sn", True, (60,60,60))
        surf.blit(time_txt, (box.centerx - time_txt.get_width()//2, box.y+78))
        my_m = self.player.distance_px / config.PIXELS_PER_METER
        dist_txt = self.font_small.render(f"Mesafe: {my_m:.1f} m", True, (60,60,60))
        surf.blit(dist_txt, (box.centerx - dist_txt.get_width()//2, box.y+100))
        # butonlar
        mx,my = pygame.mouse.get_pos()
        b1 = pygame.Rect(box.x+30, box.y+150, 190, 44)
        b2 = pygame.Rect(box.x+220, box.y+150, 190, 44)
        for b, label in [(b1, "TEKRAR OYNA"), (b2, "MENÜ")]:
            hover = b.collidepoint(mx,my)
            c = (0,160,80) if b==b1 else (60,60,70)
            top = (80,220,120) if b==b1 else (90,90,96)
            if hover:
                c = tuple(min(255, x+18) for x in c)
                top = tuple(min(255, x+18) for x in top)
            btn_s = pygame.Surface((b.width, b.height), pygame.SRCALPHA)
            for yy in range(b.height):
                ts=yy/b.height
                rr=int(top[0]*(1-ts)+c[0]*ts); gg=int(top[1]*(1-ts)+c[1]*ts); bb=int(top[2]*(1-ts)+c[2]*ts)
                pygame.draw.line(btn_s,(rr,gg,bb),(0,yy),(b.width,yy))
            mask = pygame.Surface((b.width,b.height), pygame.SRCALPHA)
            pygame.draw.rect(mask,(255,255,255),(0,0,b.width,b.height), border_radius=10)
            btn_s.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(btn_s, b.topleft)
            pygame.draw.rect(surf, (255,215,0) if hover else (0,0,0), b, width=2, border_radius=10)
            txt = self.font_med.render(label, True, (255,255,255))
            surf.blit(txt, (b.centerx - txt.get_width()//2, b.centery - txt.get_height()//2))
        hint = self.font_tiny.render("ENTER Tekrar  •  ESC Menü", True, (90,90,96))
        surf.blit(hint, (box.centerx - hint.get_width()//2, box.bottom+14))

    def draw_lobby(self, surf, theme):
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        gfx.draw_vignette(surf, intensity=0.16)
        title = self.font_big.render("LOBİ", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 24))
        hint = self.font_small.render("Hazır olunca oyun başlayacak", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 56))
        box = pygame.Rect(config.SCREEN_WIDTH//2-240, 92, 480, 260)
        gfx.draw_soft_shadow(surf, box, radius=16, alpha=42)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=14)
        # oyuncular
        y = box.y + 20
        for idx, pid in enumerate(self.lobby_players or []):
            is_me = pid == str(self.save.get("player_id"))
            nick = self.save.get("nickname") if is_me else (self.vs_opponent_nick or self.online_info.get("nick") if self.online_info else pid)
            # nick resolve
            if not is_me and self.online_info and str(self.online_info.get("id"))==pid:
                nick = self.online_info.get("nick")
            elif not is_me and self.pending_invite and self.pending_invite.get("from_id")==pid:
                nick = self.pending_invite.get("from_nick")
            ready = self.lobby_ready.get(pid, False)
            card = pygame.Rect(box.x+20, y + idx*70, box.width-40, 56)
            col = (60,160,80) if ready else (220,220,220)
            pygame.draw.rect(surf, col, card, border_radius=10)
            pygame.draw.rect(surf, (0,0,0), card, width=2, border_radius=10)
            if ready:
                pygame.draw.rect(surf, (255,215,0), card, width=3, border_radius=10)
            name = self.font_med.render(f"{nick} {'(SEN)' if is_me else ''}", True, (0,0,0))
            surf.blit(name, (card.x+16, card.y+10))
            idt = self.font_small.render(f"ID: {pid}", True, (60,60,60))
            surf.blit(idt, (card.x+16, card.y+30))
            status = self.font_small.render("HAZIR" if ready else "HAZIR DEĞİL", True, (0,120,40) if ready else (160,40,40))
            surf.blit(status, (card.right - status.get_width() -16, card.centery - status.get_height()//2))
        # hazır butonu
        mx,my = pygame.mouse.get_pos()
        b_ready = pygame.Rect(box.x+30, box.y+180, 190, 42)
        hover = b_ready.collidepoint(mx,my)
        my_ready = self.lobby_ready.get(str(self.save.get("player_id")), False)
        col = (0,160,80) if not my_ready else (200,60,60)
        top = (80,220,120) if not my_ready else (255,120,120)
        btn_s = pygame.Surface((b_ready.width, b_ready.height), pygame.SRCALPHA)
        for yy in range(b_ready.height):
            ts=yy/b_ready.height
            rr=int(top[0]*(1-ts)+col[0]*ts); gg=int(top[1]*(1-ts)+col[1]*ts); bb=int(top[2]*(1-ts)+col[2]*ts)
            pygame.draw.line(btn_s,(rr,gg,bb),(0,yy),(b_ready.width,yy))
        mask = pygame.Surface((b_ready.width,b_ready.height), pygame.SRCALPHA)
        pygame.draw.rect(mask,(255,255,255),(0,0,b_ready.width,b_ready.height), border_radius=10)
        btn_s.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(btn_s, b_ready.topleft)
        pygame.draw.rect(surf, (0,0,0), b_ready, width=2, border_radius=10)
        if hover: pygame.draw.rect(surf, (255,215,0), b_ready, width=2, border_radius=10)
        txt = self.font_med.render("HAZIR DEĞİL" if not my_ready else "HAZIR", True, (255,255,255))
        surf.blit(txt, (b_ready.centerx - txt.get_width()//2, b_ready.centery - txt.get_height()//2))
        # ayrıl
        b_leave = pygame.Rect(box.x+260, box.y+180, 190, 42)
        hover2 = b_leave.collidepoint(mx,my)
        pygame.draw.rect(surf, (200,40,40) if hover2 else (120,30,30), b_leave, border_radius=10)
        pygame.draw.rect(surf, (0,0,0), b_leave, width=2, border_radius=10)
        t2 = self.font_med.render("LOBİDEN AYRIL", True, (255,255,255))
        surf.blit(t2, (b_leave.centerx - t2.get_width()//2, b_leave.centery - t2.get_height()//2))
        # bilgi
        info = self.font_tiny.render("İki oyuncu hazır olunca oyun başlar", True, theme["hud"])
        surf.blit(info, (box.centerx - info.get_width()//2, box.bottom+14))

    def draw_invite_popup(self, surf, theme):
        # yarı saydam overlay
        over = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        over.fill((0,0,0,120))
        surf.blit(over, (0,0))
        box = pygame.Rect(config.SCREEN_WIDTH//2-180, config.SCREEN_HEIGHT//2-60, 360, 120)
        gfx.draw_soft_shadow(surf, box, radius=16, alpha=48)
        gfx.glass_panel(surf, box, fill=(255,255,255,242), border=(0,0,0,110), radius=12)
        from_nick = self.pending_invite.get("from_nick","?")
        from_id = self.pending_invite.get("from_id","?????")
        txt1 = self.font_med.render(f"{from_nick} ({from_id})", True, (0,0,0))
        surf.blit(txt1, (box.centerx - txt1.get_width()//2, box.y+18))
        txt2 = self.font_small.render("seni oyuna davet ediyor.", True, (60,60,60))
        surf.blit(txt2, (box.centerx - txt2.get_width()//2, box.y+44))
        mx,my = pygame.mouse.get_pos()
        b_yes = pygame.Rect(box.x+20, box.y+70, 150, 36)
        b_no = pygame.Rect(box.x+190, box.y+70, 150, 36)
        for b, label, col in [(b_yes,"KABUL ET",(0,160,80)), (b_no,"REDDET",(200,40,40))]:
            hover = b.collidepoint(mx,my)
            pygame.draw.rect(surf, col if not hover else tuple(min(255,c+20) for c in col), b, border_radius=8)
            pygame.draw.rect(surf, (0,0,0), b, width=2, border_radius=8)
            if hover: pygame.draw.rect(surf, (255,215,0), b, width=2, border_radius=8)
            t = self.font_med.render(label, True, (255,255,255))
            surf.blit(t, (b.centerx - t.get_width()//2, b.centery - t.get_height()//2))

