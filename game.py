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
        # FAZ6: set weapon from save
        try: self.player.attack_weapon = self.save.get("equipped_weapon","fist")
        except: pass
        self.camera = Camera()
        self.camera.reset(self.player.y)
        self.world = World()
        self.world.reset()
        self.particles = ParticleSystem()

        self.state = "menu"
        self.prev_state = "menu"
        self.paused = False
        self.death_timer = 0.0
        # (FAZ14) legacy march kaldirildi — M artik genel music toggle

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
        # FAZ12: final cinematic
        self.final_cinematic_timer = 0.0
        self.final_cinematic_stage = 0
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
        self.menu_options = ["OYNA", "BÖLÜMLER", "KARAKTERLER", "MAGAZA", "ENVANTER", "TEMALAR", "AYARLAR", "NASIL OYNANIR?", "İSTATİSTİKLER", "BAŞARIMLAR", "HİKAYE", "CIKIS"]
        self.shop_tab = 0
        self.shop_index = 0
        self.shop_scroll = 0  # mağaza liste kaydırma (piksel)
        self.char_index = 0
        self.inv_tab = 0
        self.inv_index = 0
        self.inv_scroll = 0  # envanter liste kaydırma (piksel)
        self.theme_index = 0

        # settings slider index - FAZ13: 3 audio + 1 tutorial + 3 PC (fullscreen/fps/res) + controls info + geri = 9
        self.settings_index = 0  # 0 master,1 music,2 sfx,3 tutorial,4 fullscreen,5 fps,6 resolution,7 controls,8 geri
        self.settings_items = ["MASTER", "MUSIC", "SFX", "TUTORIAL", "FULLSCREEN", "FPS", "RESOLUTION", "CONTROLS", "GERI"]
        self._display_changed = False  # FAZ13: main loop icin display yenileme bayragi

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

        # Polish — combo / coin / notifications / menu bg / intro / lore
        self.combo = 0
        self.combo_timer = 0.0
        self.combo_max = 0
        self.shake = 0.0  # FAZ3: hafif screen shake (dikey, cap'li)
        self._sfx_cd = {}  # FAZ3: ses spam engelleme (name -> kalan süre)
        self._near_cd = 0.0  # FAZ3: near-miss global cooldown
        self._near_seen = set()  # FAZ3: aynı engelde spam engelle (id set, cap'li)
        self._warn_cd = 0.0  # FAZ3: monster uyarı sesi cooldown
        self.floating_texts = []  # [{x,y,txt,life,alpha}]
        self.notifications = []  # [{txt,life}]
        # FAZ5: economy/run tracking (transient, not saved)
        self.level_run_base = 0
        self.level_run_combo_bonus = 0
        self.level_run_risk_bonus = 0
        self.level_run_near = 0
        self.level_run_start_total = 0
        self._shop_flash = {}  # FAZ5: shop purchase flash (item_id -> timer)
        self._hud_coin_flash = 0.0  # FAZ5: HUD coin pop
        self._monster_close = 0.0  # FAZ9: monster proximity 0..1 for vignette/shake
        self.menu_bg_time = 0.0
        self.menu_particles = []  # low-cost menu bg (max 15)
        self._logo_cache = {}  # theme_id -> title surf (font render cache)
        self._btn_press_idx = -1
        self._btn_press_t = 0.0
        self._menu_enter_t = 1.0  # logo giriş efekti (0->1)
        self.level_intro_timer = 0.0
        self.level_intro_data = None
        self.death_flash = 0.0
        self.finish_flash = 0.0
        self.vs_bot_name = "BOT"
        self.intro_done = self.save.get("intro_shown", False)
        self.intro_timer = 0.0
        self.intro_state = "logo" if not self.intro_done else "skip"
        # FAZ11: opening story (2-4s, ESC skip, FREEFALL logo ile çakışmaz)
        self.opening_shown = self.save.get("opening_shown", False)
        self.opening_timer = 0.0
        self.opening_state = "opening" if not self.opening_shown else "skip"
        self.easter_egg_timer = 0.0
        # Lore kısa metinler (23 bölüm için)
        self.lore_texts = {
            1: "Yukarıda gökyüzü vardı. Şimdi sadece düşüş var.",
            4: "Buradan sonrası daha sıcak. Kaya eriyor.",
            5: "Soğuk kemiklerine işliyor. Nefesin buhar oluyor.",
            6: "Işık yok. Sadece derinliğin sesi var.",
            9: "Bir zamanlar burada kahve kokusu vardı.",
            11: "Sarı ışık hiç sönmüyor. Zaman yok gibi.",
            15: "Metal gıcırdıyor. Fabrika hâlâ çalışıyor.",
            23: "En alttasın. Monster sustu. Bitti mi?",
        }

        # apply saved audio settings (FAZ14: music_enabled dahil)
        try:
            s = self.save.get("settings", {})
            audio.set_master(s.get("master", 0.7))
            audio.set_music(s.get("music", 0.5))
            audio.set_sfx(s.get("sfx", 0.8))
            # FAZ14: M toggle persistent
            audio.music_enabled = bool(s.get("music_enabled", True))
        except:
            pass
        audio.load_or_generate()
        # FAZ14: ana menu rock'i hazirla (lazy — ilk menu'de calacak)
        try:
            if audio.music_enabled and self.state == "account_gate":
                # account gate'de sessiz baslar, menu'ye gecince calacak
                pass
        except: pass

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
        try: self._menu_enter_t = 0.0
        except: pass
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
        # FAZ4: menuye donuste muzik fade out (bolum muzigi) — FAZ14: menu rock'a gecis
        try:
            audio.stop_music(fade_out=0.35)
            audio.set_tension(0.0)
            # kisa gecikme sonra menu rock baslar (update'de de tetiklenir, ama burada da dene)
            if audio.music_enabled:
                # fade out bitmeden menu rock'i baslatma — 0.35s sonra update'de baslayacak
                pass
        except: pass
        # FAZ6: combat reset
        try:
            self.player.attack_timer=0; self.player.attack_cooldown=0; self.player.attack_phase="idle"; self.player._attack_hit_done=set()
            self.shake=0
        except: pass
        # FAZ14: tehdit muzigi sustur
        try:
            audio.set_tension(0.0)
            audio.stop_threat(fade_out=0.35)
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

    def _get_online_nick(self):
        """ONLINE için doğru nick: yerel hesap varsa account_username, yoksa nickname. ID'yi nick sanma."""
        if self.save.get("account_mode") == "account":
            uname = str(self.save.get("account_username") or "").strip()
            if save_system.is_valid_nick(uname) and not save_system.is_valid_player_id(uname):
                return uname
        nick = str(self.save.get("nickname") or "").strip()
        if save_system.is_valid_nick(nick) and not save_system.is_valid_player_id(nick):
            return nick
        return nick or "Oyuncu"

    def _get_display_id(self):
        """UI için ID: geçerli ise 5 haneli, yoksa ????? değil Yükleniyor/—"""
        pid = str(self.save.get("player_id") or "").strip()
        if save_system.is_valid_player_id(pid):
            return pid
        # hesaplı ama ID henüz yok -> Yükleniyor, misafir -> —
        if self.save.get("account_mode") == "account":
            # ONLINE bağlanıyorsa Yükleniyor
            if self.online_mgr and getattr(self.online_mgr, '_online_mode', False):
                return "Yükleniyor..."
            return "—"
        return "—"

    def _get_display_nick(self):
        """UI için nick: hesaplı ise account_username öncelikli, ID'yi nick sanma"""
        if self.save.get("account_mode") == "account":
            uname = str(self.save.get("account_username") or "").strip()
            if save_system.is_valid_nick(uname) and not save_system.is_valid_player_id(uname):
                return uname
        nick = str(self.save.get("nickname") or "").strip()
        if save_system.is_valid_nick(nick) and not save_system.is_valid_player_id(nick):
            return nick
        # fallback: account_username if nickname is ID/invalid
        au = str(self.save.get("account_username") or "").strip()
        if save_system.is_valid_nick(au) and not save_system.is_valid_player_id(au):
            return au
        return "Oyuncu"

    def _enter_main_menu(self, first_entry=False):
        """Hesap kapısından ana menüye geç. İlk girişte NASIL OYNANIR? otomatik (§31)."""
        self.state = "menu"
        try: self._menu_enter_t = 0.0
        except: pass
        self.menu_index = 0
        self.play_select_msg = ""
        # FAZ14: menu rock baslat (master/music + music_enabled ile)
        try:
            if audio.music_enabled:
                self._ensure_menu_music()
            audio.set_tension(0.0)
        except: pass
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
            # FAZ6-BUGFIX: ident player_id ise account_username nickname olmalı, ID değil
            actual_nick = ident
            if save_system.is_valid_player_id(ident):
                saved_nick2 = str(self.save.get("nickname") or "").strip()
                if save_system.is_valid_nick(saved_nick2) and not save_system.is_valid_player_id(saved_nick2):
                    actual_nick = saved_nick2
                else:
                    # fallback: try to find nickname for this ID from save's account_username if valid
                    au = str(self.save.get("account_username") or "").strip()
                    if save_system.is_valid_nick(au) and not save_system.is_valid_player_id(au):
                        actual_nick = au
            # ensure actual_nick is not a player_id
            if save_system.is_valid_player_id(actual_nick):
                actual_nick = str(self.save.get("nickname") or "").strip()
            self.save["account_username"] = actual_nick
            if not save_system.is_valid_nick(self.save.get("nickname") or "") or save_system.is_valid_player_id(self.save.get("nickname") or ""):
                if save_system.is_valid_nick(actual_nick) and not save_system.is_valid_player_id(actual_nick):
                    self.save["nickname"] = actual_nick
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
        # FAZ5: detect newly unlocked characters for notification
        _prev_chars = set(self.save.get("unlocked_characters", []))
        try:
            save_system.unlock_next_level(self.save, lvl)
        except:
            nxt = lvl+1
            if nxt <= len(config.LEVELS) and nxt not in self.save["unlocked_levels"]:
                self.save["unlocked_levels"].append(nxt)
        save_system.save_game(self.save)
        self._game_mutated()
        try:
            _new_chars = [c for c in self.save.get("unlocked_characters", []) if c not in _prev_chars]
            for cid in _new_chars:
                cname = next((cc["name"] for cc in config.CHARACTERS if cc["id"]==cid), cid)
                self._add_notification(f"YENI KARAKTER: {cname}!", (255,215,0))
                self._play_sfx_cd("unlock", cd=0.3, volume=0.8)
                # small levelup particle
                try: self.particles.emit_levelup(self.player.x+self.player.w//2, self.player.y)
                except: pass
            if _new_chars:
                # also check theme unlock if any (future)
                pass
        except: pass
        # FAZ5: reward breakdown (base/combo/risk/near) - gercek degerler
        try:
            _base = int(getattr(self, 'level_run_base', coins))
            _combo_b = int(getattr(self, 'level_run_combo_bonus', 0))
            _risk_b = int(getattr(self, 'level_run_risk_bonus', 0))
            _near = int(getattr(self, 'level_run_near', 0))
            # fallback if run tracking not used (e.g., old save)
            if _base == 0 and coins > 0:
                _base = int(coins - _combo_b - _risk_b)
                if _base < 0: _base = int(coins)
        except:
            _base = int(coins); _combo_b = 0; _risk_b = 0; _near = 0
        # level_complete verisi (FAZ5 breakdown)
        self.level_complete_data = {
            "level": lvl,
            "name": self.level_info["name"],
            "coins": coins,
            "base": _base,
            "combo_bonus": _combo_b,
            "risk_bonus": _risk_b,
            "near_count": _near,
            "earned": int(_base + _combo_b + _risk_b),
            "total_coins": self.save.get("total_coins",0),
            "distance": self.player.distance_px / config.PIXELS_PER_METER,
            "stars": stars,
            "is_final": lvl >= len(config.LEVELS),
        }
        # istatistik & başarım
        try:
            stats = self.save.setdefault("statistics", {})
            stats["levels_completed"] = int(stats.get("levels_completed",0)) + 1
            stats["total_sections"] = int(stats.get("total_sections",0)) + 1
            if stars >= 3:
                stats["total_coins_collected"] = int(self.save.get("total_coins",0))
            # vs değil, normal bölüm
            self._check_achievements()
        except: pass
        self._add_notification(f"BÖLÜM {lvl} TAMAMLANDI!", (80,220,120))
        if lvl < len(config.LEVELS):
            self._add_notification(f"BÖLÜM {lvl+1} AÇILDI!", (255,215,0))
        # canavar durdur
        try:
            audio.play("levelup")
            self.particles.emit_levelup(self.player.x + self.player.w//2, self.player.y)
        except: pass
        if lvl >= len(config.LEVELS):
            # FAZ12: FINAL cinematic - reward korunur, cinematic_seen kontrolü
            if not self.save.get("final_cinematic_seen", False):
                self.state = "final_cinematic"
                self.final_cinematic_timer = 0.0
                self.final_cinematic_stage = 0
            else:
                # zaten görüldü, direkt level_complete
                self.state = "level_complete"
                self.level_complete_timer = 0.90
            self.ending_anim = 0.0
            self.ending_timer = 0.0
            self.camera.y -= 12
            # reward zaten kaydedildi, final_completed True
        else:
            self.state = "level_complete"
            self.level_complete_timer = 0.0
            self.level_up_anim = 0.0
            # FAZ7: finish bounce + flash
            try:
                self.player.squash = 0.16
                self.finish_flash = 0.7
                self.particles.emit_levelup(self.player.x+self.player.w//2, self.player.y)
            except: pass
            # FAZ6: clear attack on finish
            try: self.player.attack_timer=0; self.player.attack_phase="idle"
            except: pass

    def _add_notification(self, txt, col=(255,215,0)):
        try:
            self.notifications.append({"txt": txt, "life": 2.2, "col": col})
            if len(self.notifications) > 4:
                self.notifications = self.notifications[-4:]
        except: pass

    def _check_achievements(self):
        try:
            ach = self.save.setdefault("achievements", {})
            stats = self.save.get("statistics", {})
            # İlk düşüş
            if 1 in self.save.get("completed_levels",[]) and not ach.get("first_fall"):
                ach["first_fall"]=True
                self._add_notification("🏆 BAŞARIM: İLK ADIM!", (255,215,0))
                self._play_sfx_cd("unlock", cd=0.3, volume=0.8)
            # 5 bölüm
            if len(self.save.get("completed_levels",[])) >= 5 and not ach.get("deep10b"):
                ach["deep10b"]=True
                self._add_notification("🏆 YÜKSELİŞ: 5 BÖLÜM!", (120,220,255))
                self._play_sfx_cd("unlock", cd=0.3, volume=0.8)
            # 10 bölüm
            if len(self.save.get("completed_levels",[])) >= 10 and not ach.get("deep10"):
                ach["deep10"]=True
                self._add_notification("🏆 KAÇIŞ: 10 BÖLÜM!", (120,200,255))
                self._play_sfx_cd("unlock", cd=0.3, volume=0.8)
            # Final
            if self.save.get("final_completed") and not ach.get("final"):
                ach["final"]=True
                self._add_notification("🏆 ZİRVE: 23 BÖLÜM!", (255,100,100))
                self._play_sfx_cd("levelup", cd=0.3, volume=0.8)
            # Combo 6
            if self.combo_max >= 6 and not ach.get("combo6"):
                ach["combo6"]=True
                self._add_notification("🏆 KOMBO USTASI!", (180,255,180))
                self._play_sfx_cd("combo", cd=0.3, volume=0.8)
            # 100 coin
            if self.save.get("total_coins",0) >= 100 and not ach.get("coin100"):
                ach["coin100"]=True
                self._add_notification("🏆 HAZİNE AVCISI: 100 COIN!", (255,215,0))
                self._play_sfx_cd("bonus", cd=0.3, volume=0.8)
            # 10 eşya
            if len(self.save.get("owned_items",[])) >= 10 and not ach.get("collector"):
                ach["collector"]=True
                self._add_notification("🏆 KOLEKSİYONCU: 10 EŞYA!", (200,180,120))
                self._play_sfx_cd("unlock", cd=0.3, volume=0.8)
            # 20 eşya
            if len(self.save.get("owned_items",[])) >= 20 and not ach.get("full_gear"):
                ach["full_gear"]=True
                self._add_notification("🏆 TAM DONANIM: 20 EŞYA!", (180,220,255))
                self._play_sfx_cd("unlock", cd=0.3, volume=0.8)
            save_system.save_game(self.save)
        except: pass

    # ---------- FAZ5 helpers ----------
    def _play_sfx_cd(self, name, cd=0.14, volume=1.0):
        try:
            if self._sfx_cd.get(name, 0) > 0:
                return False
            audio.play(name, volume)
            self._sfx_cd[name] = cd
            return True
        except:
            return False

    def _reset_run_stats(self):
        try:
            self.level_run_base = 0
            self.level_run_combo_bonus = 0
            self.level_run_risk_bonus = 0
            self.level_run_near = 0
            self.level_run_start_total = int(self.save.get("total_coins",0))
            self._near_seen = set()
            self._near_cd = 0.0
            self.combo = 0
            self.combo_timer = 0.0
        except: pass

    def _check_near_miss(self):
        if getattr(self, '_near_cd', 0) > 0:
            return
        if getattr(self.player, 'on_ground', False) or not getattr(self.player, 'alive', True):
            return
        if self.state not in ("playing", "vs_bot", "vs_online"):
            return
        try:
            px = self.player.x; py = self.player.y; pw = self.player.w; ph = self.player.h
            for o in self.world.obstacles:
                key = (int(o.x), int(o.y), int(o.width))
                if key in self._near_seen:
                    continue
                if py + ph <= o.top or py >= o.bottom:
                    continue
                gap_left = o.left - (px + pw)
                gap_right = px - o.right
                is_near = False
                if 0 < gap_left < 11:
                    is_near = True
                elif 0 < gap_right < 11:
                    is_near = True
                if is_near:
                    self._near_cd = 0.38
                    self._near_seen.add(key)
                    if len(self._near_seen) > 64:
                        try: self._near_seen.pop()
                        except: pass
                    self.combo = getattr(self, 'combo', 0) + 1
                    self.combo_timer = 1.6
                    self.combo_max = max(getattr(self, 'combo_max',0), self.combo)
                    self.level_run_near = getattr(self, 'level_run_near', 0) + 1
                    try:
                        self.floating_texts.append({"x": self.player.x+self.player.w//2, "y": self.player.y-12, "txt": "NEAR MISS! + COMBO", "life": 0.7, "alpha": 255})
                        self._add_notification("NEAR MISS!", (120,200,255))
                        self._play_sfx_cd("near_miss", cd=0.2, volume=0.7)
                        self.particles.emit_coin(self.player.x+self.player.w//2, self.player.y+self.player.h//2, 1)
                        self.shake = min(2.0, getattr(self, 'shake',0)+0.35)
                    except: pass
                    break
        except: pass

    def start_game(self):
        # Sonsuz mod — canavar yok
        self.player.reset(config.SCREEN_WIDTH//2 - config.PLAYER_W//2, 80)
        try: self.player.attack_weapon = self.save.get("equipped_weapon","fist")
        except: pass
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
        # FAZ4: sonsuz mod muzik (level_info guncel sonra)
        try:
            self._update_level_music(self.level_info.get("name", "HAVA"), force=True)
        except: pass

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
        try: self.player.attack_weapon = self.save.get("equipped_weapon","fist")
        except: pass
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
        # FAZ5: run stats reset
        try: self._reset_run_stats()
        except: pass
        # FAZ11: level intro (first time only)
        try:
            seen = self.save.get("seen_lore", [])
            if lvl not in seen:
                self.level_intro_active = True
                self.level_intro_timer = 0.0
            else:
                self.level_intro_active = False
                self.level_intro_timer = 0.0
        except:
            self.level_intro_active = False
            self.level_intro_timer = 0.0
        # FAZ4: bolum muzik secimi (same-key restart yok)
        try:
            self._update_level_music(self.level_info.get("name", "HAVA"))
        except: pass

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
                # FAZ4: endless seviye muzik degisimi (music_key farkliysa crossfade)
                try:
                    self._update_level_music(self.level_info.get("name", "HAVA"))
                except: pass
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

    def _get_theme(self):
        try:
            tid = self.save.get("theme", "beyaz")
            for t in config.THEMES:
                if t["id"] == tid:
                    return t
            return config.THEMES[0]
        except:
            return config.THEMES[0]

    def _update_level_music(self, level_name=None, force=False):
        try:
            ln = level_name or getattr(self.level_info, "get", lambda k,d=None: None)("name") if isinstance(self.level_info, dict) else getattr(self.level_info, "name", None)
            if not ln:
                ln = self.level_info.get("name", "HAVA") if isinstance(self.level_info, dict) else "HAVA"
            # audio handles same-key no-restart
            audio.play_music_for_level(ln, fade_in=0.8 if not force else 0.6)
        except: pass

    def _ensure_menu_music(self, force=False):
        """FAZ14: ana menu dark rock — telifsiz procedural, MUSIC volumu ile, restart yok."""
        try:
            if not audio.music_enabled or not audio.enabled:
                return False
            # zaten menu rock caliyorsa tekrar baslatma
            if not force and audio.get_current_music_key() == "menu_rock":
                return False
            audio.play_music_key("menu_rock", fade_in=0.9)
            # tension'i sifirla — menu'de threat yok
            audio.set_tension(0.0)
            return True
        except:
            return False

    def update(self, dt, keys_held):
        # transition alpha
        if self.transition_target is not None:
            self.transition += dt*6
            if self.transition >= 1:
                self.transition = 0
                self.transition_target = None
        # FAZ4: audio fade/tension update (her frame, ucuz)
        try:
            audio.update(dt)
            # monster tension -> audio
            if getattr(self, 'monster', None) and getattr(self, 'level_mode', None) is not None and getattr(self.player, 'alive', True):
                try:
                    gap = self.player.y - self.monster.y
                    # 220 ideal, <180 gerilim baslar, <90 yuksek
                    if gap < 180:
                        tens = (180 - gap) / 180.0
                        tens = max(0, min(1, tens))
                    else:
                        tens = 0.0
                    audio.set_tension(tens)
                except:
                    audio.set_tension(0.0)
            else:
                audio.set_tension(0.0)
                # FAZ14: menu'de dark rock (telifsiz) — intro/cinematic degilse baslat
                if self.state == "menu" and getattr(self, 'intro_state','skip')=='skip' and getattr(self, 'opening_state','skip')=='skip' and not self.help_open:
                    if audio.music_enabled and audio.get_current_music_key() not in ("menu_rock",):
                        # sadece bir kez, fade ile
                        try: self._ensure_menu_music()
                        except: pass
        except: pass
        # Intro — ilk açılışta kısa, atlanabilir
        if getattr(self, 'intro_state', 'skip') == "logo":
            self.intro_timer += dt
            if self.intro_timer > 2.2:
                self.intro_state = "skip"
                self.save["intro_shown"] = True
                try: save_system.save_game(self.save)
                except: pass
            return
        # FAZ12: opening cinematic 7.2s (6-9s, ESC skip)
        if getattr(self, 'opening_state', 'skip') == "opening":
            self.opening_timer += dt
            if self.opening_timer > 7.2:
                self.opening_state = "skip"
                self.save["opening_shown"] = True
                try: save_system.save_game(self.save)
                except: pass
            return
        # Combo timer + floating texts + notifications + menu bg + stats play time
        if getattr(self, 'combo_timer', 0) > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0
        # FAZ5: near-miss / sfx cd / shake decay
        if getattr(self, '_near_cd', 0) > 0:
            self._near_cd = max(0, self._near_cd - dt)
        if getattr(self, '_warn_cd', 0) > 0:
            self._warn_cd = max(0, self._warn_cd - dt)
        if getattr(self, 'shake', 0) > 0:
            self.shake = max(0, self.shake - dt*3.5)
        if getattr(self, '_hud_coin_flash', 0) > 0:
            self._hud_coin_flash = max(0, self._hud_coin_flash - dt*2.5)
        # sfx cd dict
        if hasattr(self, '_sfx_cd') and self._sfx_cd:
            for k in list(self._sfx_cd.keys()):
                self._sfx_cd[k] = max(0, self._sfx_cd[k] - dt)
                if self._sfx_cd[k] <= 0:
                    self._sfx_cd.pop(k, None)
        # shop flash
        if hasattr(self, '_shop_flash') and self._shop_flash:
            for k in list(self._shop_flash.keys()):
                self._shop_flash[k] = max(0, self._shop_flash[k] - dt)
                if self._shop_flash[k] <= 0:
                    self._shop_flash.pop(k, None)
        # floating texts
        if hasattr(self, 'floating_texts'):
            for ft in self.floating_texts:
                ft['y'] -= 28*dt
                ft['life'] -= dt
                ft['alpha'] = int(255 * max(0, ft['life']/0.9))
            self.floating_texts = [f for f in self.floating_texts if f['life'] > 0]
        # notifications
        if hasattr(self, 'notifications'):
            for n in self.notifications:
                n['life'] -= dt
            self.notifications = [n for n in self.notifications if n['life'] > 0]
        # menu bg time + low-cost particles (max 15)
        if hasattr(self, 'menu_bg_time'):
            self.menu_bg_time += dt
            if self.state == "menu" and len(getattr(self, 'menu_particles', [])) < 15 and self.menu_bg_time > 0.12:
                self.menu_bg_time = 0
                try:
                    import random as _rnd
                    self.menu_particles.append({"x": _rnd.randint(20,880), "y": _rnd.randint(-20,700), "vx": _rnd.uniform(-12,12), "vy": _rnd.uniform(8,18), "life": 6.0, "col": (255,215,0) if _rnd.random()<0.3 else (180,220,255)})
                except: pass
            for p in getattr(self, 'menu_particles', []):
                p['x'] += p.get('vx',0)*dt
                p['y'] += p.get('vy',0)*dt
                p['life'] -= dt
            self.menu_particles = [p for p in getattr(self,'menu_particles',[]) if p['life']>0 and p['y']<720]
        # stats play time
        try:
            if self.state in ("playing","vs_bot","vs_online") and not self.paused:
                self.save.setdefault("statistics", {})["total_play_time"] = float(self.save["statistics"].get("total_play_time",0) + dt)
        except: pass
        # death/finish flash
        if getattr(self, 'death_flash', 0) > 0:
            self.death_flash -= dt*2.2
        if getattr(self, 'finish_flash', 0) > 0:
            self.finish_flash -= dt*1.8
        # menu giriş + buton basma zamanlayıcıları
        if getattr(self, '_menu_enter_t', 1.0) < 1.0:
            self._menu_enter_t = min(1.0, self._menu_enter_t + dt*3.0)
        if getattr(self, '_btn_press_t', 0.0) > 0:
            self._btn_press_t = max(0.0, self._btn_press_t - dt)
        # (FAZ14) legacy timer kaldirildi

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
            self.particles.update(dt, self.camera.y, self.level_info["name"], self._get_theme())
            if self.level_up_anim > 0:
                self.level_up_anim -= dt
            return
        if self.state == "ending":
            self.ending_timer += dt
            self.ending_anim += dt
            self.particles.update(dt, self.camera.y, self.level_info["name"], self._get_theme())
            # sinematik kamera — yavaşça yukarı kaydır
            self.camera.y -= 42 * dt
            if self.camera.y < 0:
                self.camera.y = 0
            return
        if self.state == "final_cinematic":
            self.final_cinematic_timer += dt
            self.ending_anim += dt
            self.particles.update(dt, self.camera.y, self.level_info["name"], self._get_theme())
            self.camera.y -= 7 * dt
            if self.camera.y < 0:
                self.camera.y = 0
            if self.final_cinematic_timer > 19.5:
                # auto to level_complete with buttons visible
                self.state = "level_complete"
                self.level_complete_timer = 0.90
                self.save["final_cinematic_seen"] = True
                try: save_system.save_game(self.save)
                except: pass
            return
        if self.state == "playing":
            if self.paused:
                # tutorial kapama vs yine de input alabilir
                return
            # FAZ11: level intro timer (first time 1.6s, ESC skip handled in handle_event)
            if getattr(self, 'level_intro_active', False):
                self.level_intro_timer += dt
                if self.level_intro_timer > 1.6:
                    self.level_intro_active = False
                    try:
                        if self.level_mode not in self.save.get("seen_lore", []):
                            self.save["seen_lore"].append(self.level_mode)
                            self.save["seen_lore"] = sorted(set(self.save["seen_lore"]))
                            save_system.save_game(self.save)
                    except: pass
                # still update camera/particles but not blocking input
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
                # FAZ9: death atmosphere
                try: self.death_flash = 1.0; self.shake = 1.2
                except: pass

            # FAZ5: near-miss check (after physics, before coin)
            try: self._check_near_miss()
            except: pass
            gained = self.world.check_coin_collection(self.player.rect)
            if gained:
                # FAZ5: base tracking + combo + risk bonus (cap'li)
                _base = int(gained)
                self.combo = getattr(self, 'combo', 0) + 1
                self.combo_timer = 1.6
                self.combo_max = max(getattr(self, 'combo_max', 0), self.combo)
                try:
                    self.save["statistics"]["max_combo"] = max(self.save["statistics"].get("max_combo",0), self.combo)
                    self.save["statistics"]["total_coins_collected"] = int(self.save["statistics"].get("total_coins_collected",0) + _base)
                except: pass
                bonus = 0
                if self.combo >= 4:
                    bonus = 1 if self.combo < 7 else 2
                    gained += bonus
                # FAZ5: monster yakin risk bonusu (cap 6 per level)
                risk = 0
                if self.level_mode is not None and getattr(self, 'monster', None) and getattr(self.player, 'alive', True):
                    try:
                        gap = self.player.y - self.monster.y
                        if 0 < gap < 155:
                            if getattr(self, 'level_run_risk_bonus', 0) < 6:
                                risk = 1
                                gained += risk
                    except: pass
                # run tracking
                try:
                    self.level_run_base = getattr(self, 'level_run_base', 0) + _base
                    self.level_run_combo_bonus = getattr(self, 'level_run_combo_bonus', 0) + bonus
                    self.level_run_risk_bonus = getattr(self, 'level_run_risk_bonus', 0) + risk
                except: pass
                self.save["total_coins"] += gained
                self.player.coins += gained
                self._game_mutated()
                # FAZ5: HUD coin flash
                try: self._hud_coin_flash = 0.45
                except: pass
                # floating text + combo + risk
                try:
                    _txt = f"+{gained}"
                    if bonus or risk:
                        _parts = []
                        if bonus: _parts.append(f"COMBO+{bonus}")
                        if risk: _parts.append("RISK+1")
                        _txt += "  " + " ".join(_parts)
                    elif self.combo>=2:
                        _txt += f"  COMBO x{self.combo}"
                    self.floating_texts.append({"x": self.player.x+self.player.w//2, "y": self.player.y, "txt": _txt, "life": 0.9, "alpha": 255})
                    if bonus:
                        self._add_notification(f"COMBO x{self.combo} +{bonus} BONUS!", (255,215,0))
                        self._play_sfx_cd("combo", cd=0.12, volume=0.7)
                    if risk:
                        self._add_notification("RISK BONUS +1!", (255,120,80))
                        self._play_sfx_cd("bonus", cd=0.15, volume=0.6)
                except: pass
                # coin sesi ve parçacık — value'ye göre yoğunluk + FAZ5 extra glow for combo
                self.particles.emit_coin(self.player.x + self.player.w//2, self.player.y + self.player.h//2, gained)
                if self.combo >= 6:
                    try: self.particles.emit_coin(self.player.x+self.player.w//2, self.player.y+self.player.h//2, 1)
                    except: pass
                if gained >= 5:
                    self._play_sfx_cd("coin5", cd=0.08, volume=1.0)
                elif gained >= 3:
                    self._play_sfx_cd("coin5", cd=0.08, volume=0.7)
                else:
                    self._play_sfx_cd("coin", cd=0.07, volume=1.0)

            self.camera.update(dt, self.player.y, self.player.alive)
            # Bölümlü kaçış modunda canavar ve bitiş
            if self.level_mode is not None:
                # canavar takip — gerçek tehdit
                try:
                    self.monster.update(dt, self.player, self.camera.y)
                    # FAZ9: monster proximity atmosphere (shake/vignette, no AI change)
                    try:
                        _gap9 = self.player.y - self.monster.y
                        if 0 < _gap9 < 180:
                            if _gap9 < 95:
                                self.shake = min(1.1, getattr(self, 'shake',0) + dt*1.6)
                            elif _gap9 < 145:
                                self.shake = min(0.6, getattr(self, 'shake',0) + dt*0.8)
                            self._monster_close = (180 - _gap9)/180
                        else:
                            self._monster_close = max(0, self._monster_close - dt*1.5)
                    except:
                        self._monster_close = 0
                    # FAZ6: combat hit (gap-based, monster behind)
                    try:
                        hb = self.player.get_attack_hitbox()
                        w = config.get_weapon(self.player.attack_weapon)
                        gap = self.player.y - self.monster.y
                        # hit if monster within weapon range behind + horizontal close
                        if hb is not None and 0 < gap < w["range"] + 90 and abs(self.player.x - self.monster.x) < 72:
                            aid = getattr(self.player, 'attack_id', 0)
                            hit_done = getattr(self.player, '_attack_hit_done', set())
                            key = ("monster", aid)
                            if key not in hit_done:
                                hit_done.add(key)
                                self.player._attack_hit_done = hit_done
                                self.monster.apply_hit(w["damage"], w["knockback"], w["stagger"])
                                hit_x = self.monster.x + self.monster.w//2
                                hit_y = self.monster.y + self.monster.h//2
                                try: self.particles.emit_hit(hit_x, hit_y, w["id"])
                                except: pass
                                self._play_sfx_cd("sword_hit" if w["id"]=="beam_sword" else "punch", cd=0.12, volume=0.8)
                                try: self.floating_texts.append({"x": hit_x, "y": hit_y-16, "txt": f"HIT! -{w['damage']}", "life": 0.6, "alpha": 255})
                                except: pass
                                self.shake = min(2.5, getattr(self, 'shake',0)+ (0.6 if w["id"]=="fist" else 0.9))
                                # FAZ7: hit recoil
                                try: self.player.squash = -0.09 if w["id"]=="fist" else -0.06
                                except: pass
                                self.combo = getattr(self, 'combo',0)+1
                                self.combo_timer = 1.6
                    except: pass
                    if self.monster.check_catch(self.player) and self.player.alive:
                        self.player.alive = False
                        self.player.state = "death"
                        audio.play("death")
                        self.particles.emit_death(self.player.x + self.player.w//2, self.player.y + self.player.h//2)
                        # FAZ9: death atmosphere
                        try: self.death_flash = 1.0; self.shake = 1.4; self.player.squash = 0.18
                        except: pass
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
                # FAZ6: clear attack on death
                try: self.player.attack_timer=0; self.player.attack_phase="idle"
                except: pass
                self.death_timer += dt
                if self.death_timer > 1.0:
                    self.state = "gameover"
                    save_system.save_game(self.save)

            # particles
            self.particles.update(dt, self.camera.y, self.level_info["name"], self._get_theme())
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
            self.particles.update(dt, self.camera.y, self.level_info["name"], self._get_theme())
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
            # FAZ5: near-miss (vs)
            try: self._check_near_miss()
            except: pass
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
                    # FAZ9: vs proximity
                    try:
                        _gapv = self.player.y - self.monster.y
                        if 0 < _gapv < 180:
                            self._monster_close = (180-_gapv)/180
                        else:
                            self._monster_close = max(0, self._monster_close - 0.02)
                    except: pass
                    # FAZ6: vs combat hit (gap-based)
                    try:
                        hb = self.player.get_attack_hitbox()
                        w = config.get_weapon(self.player.attack_weapon)
                        gap = self.player.y - self.monster.y
                        if hb is not None and 0 < gap < w["range"] + 90 and abs(self.player.x - self.monster.x) < 72:
                            aid = getattr(self.player, 'attack_id', 0)
                            hit_done = getattr(self.player, '_attack_hit_done', set())
                            key = ("monster_vs", aid)
                            if key not in hit_done:
                                hit_done.add(key)
                                self.player._attack_hit_done = hit_done
                                self.monster.apply_hit(w["damage"], w["knockback"]*0.7, w["stagger"]*0.7)
                                hit_x = self.monster.x + self.monster.w//2
                                hit_y = self.monster.y + self.monster.h//2
                                try: self.particles.emit_hit(hit_x, hit_y, w["id"])
                                except: pass
                                self._play_sfx_cd("sword_hit" if w["id"]=="beam_sword" else "punch", cd=0.12, volume=0.8)
                                self.shake = min(2.5, getattr(self, 'shake',0)+0.5)
                                try: self.player.squash = -0.07
                                except: pass
                    except: pass
                    # her iki yarışmacı için ayrı catch (global flag kirletmeden)
                    if self.vs_bot and self.vs_bot.alive and self.monster.check_catch_vs(self.vs_bot):
                        self.vs_bot.alive=False
                        self.vs_bot.state="death"
                        self.particles.emit_death(self.vs_bot.x+self.vs_bot.w//2, self.vs_bot.y+self.vs_bot.h//2)
                    if self.player.alive and self.monster.check_catch_vs(self.player):
                        self.player.alive=False; self.player.state="death"
                        audio.play("death")
                        self.particles.emit_death(self.player.x+self.player.w//2, self.player.y+self.player.h//2)
                        try: self.death_flash=1.0; self.shake=1.2
                        except: pass
                        self.monster.caught=True
                except: pass
            else:
                try:
                    self.monster.update(dt, self.player, self.camera.y)
                    # FAZ9: proximity for online
                    try:
                        _gap9o = self.player.y - self.monster.y
                        if 0 < _gap9o < 180:
                            self._monster_close = (180-_gap9o)/180
                        else:
                            self._monster_close = max(0, self._monster_close - 0.02)
                    except: pass
                    # FAZ6: combat hit for online/vs
                    try:
                        hb = self.player.get_attack_hitbox()
                        w = config.get_weapon(self.player.attack_weapon)
                        gap = self.player.y - self.monster.y
                        if hb is not None and 0 < gap < w["range"] + 90 and abs(self.player.x - self.monster.x) < 72:
                            aid = getattr(self.player, 'attack_id', 0)
                            hit_done = getattr(self.player, '_attack_hit_done', set())
                            key = ("monster_online", aid)
                            if key not in hit_done:
                                hit_done.add(key)
                                self.player._attack_hit_done = hit_done
                                self.monster.apply_hit(w["damage"], w["knockback"]*0.7, w["stagger"]*0.7)
                                hit_x = self.monster.x + self.monster.w//2
                                hit_y = self.monster.y + self.monster.h//2
                                try: self.particles.emit_hit(hit_x, hit_y, w["id"])
                                except: pass
                                self._play_sfx_cd("sword_hit" if w["id"]=="beam_sword" else "punch", cd=0.12, volume=0.8)
                                self.shake = min(2.5, getattr(self, 'shake',0)+0.5)
                                try: self.player.squash = -0.07
                                except: pass
                    except: pass
                    # bot'u da kontrol et — bot ölürse player kazanır (sadece online/monster modda)
                    if self.state=="vs_bot" and self.vs_bot and self.vs_bot.alive:
                        if self.monster.check_catch(self.vs_bot):
                            self.vs_bot.alive=False
                            self.vs_bot.state="death"
                    if self.monster.check_catch(self.player) and self.player.alive:
                        self.player.alive=False; self.player.state="death"
                        audio.play("death")
                        self.particles.emit_death(self.player.x+self.player.w//2, self.player.y+self.player.h//2)
                        try: self.death_flash=1.0; self.shake=1.2
                        except: pass
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
                # ikisi aynı anda elendi → deterministik: oyuncu kaybetti (FAZ16: duplicate block kaldirildi, tek increment)
                try: self.player.attack_timer=0; self.player.attack_phase="idle"
                except: pass
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
            self.particles.update(dt, self.camera.y, self.level_info["name"], self._get_theme())
            # VS'de mesafe rekoru
            dist_m=self.player.distance_px/config.PIXELS_PER_METER
            if dist_m>self.save.get("best_distance",0):
                self.save["best_distance"]=dist_m
                self._game_mutated()

    # ---------- event handling ----------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            # intro skip (ilk acilis 2.2s, atlanabilir)
            if getattr(self, 'intro_state', 'skip') == "logo":
                if event.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
                    self.intro_state = "skip"
                    self.save["intro_shown"] = True
                    try: save_system.save_game(self.save)
                    except: pass
                return
            # NASIL OYNANIR? modal — açıkken her tuşu yakala (ESC/H/ENTER/SPACE kapatır)
            if self.help_open:
                if event.key in (pygame.K_h, pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                    self._close_help()
                return
            # FAZ11: opening story skip
            if getattr(self, 'opening_state', 'skip') == "opening":
                if event.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
                    self.opening_state = "skip"
                    self.save["opening_shown"] = True
                    try: save_system.save_game(self.save)
                    except: pass
                return
            # FAZ14: M — genel MUSIC toggle (legacy march kaldirildi, global muzik)
            if event.key == pygame.K_m and self.state in ("menu","playing","shop","characters","inventory","themes","settings","levels","play_select","online_menu","lobby","vs_bot","vs_online"):
                if True:
                    new_enabled = not getattr(audio, "music_enabled", True)
                    audio.music_enabled = new_enabled
                    # persist (backward compat key)
                    try:
                        self.save["settings"]["music_enabled"] = bool(new_enabled)
                        save_system.save_game(self.save)
                    except: pass
                    if new_enabled:
                        # resume appropriate track
                        try:
                            if self.state == "menu":
                                self._ensure_menu_music()
                            elif self.state in ("playing","paused","vs_bot","vs_online"):
                                self._update_level_music(self.level_info.get("name","HAVA"))
                            else:
                                # generic resume: if no track, start menu rock
                                if not audio.get_current_music_key():
                                    self._ensure_menu_music()
                                else:
                                    # force re-apply volume (unmute)
                                    audio._apply_music_volume()
                                    try: audio._apply_threat_volume()
                                    except: pass
                        except: pass
                    else:
                        try:
                            audio.stop_music(fade_out=0.35)
                        except: pass
                        try:
                            audio.stop_threat(fade_out=0.35)
                        except: pass
                    try: audio.play("click")
                    except: pass
                    return
            # NASIL OYNANIR? — H tuşu ile her yerden aç
            if event.key == pygame.K_h:
                if self.state in ("menu","playing","shop","characters","inventory","themes","settings","levels","gameover","play_select","online_menu"):
                    self._open_help()
                    return
            # FAZ13: F11 fullscreen toggle (guvenli, fallback'li)
            if event.key == pygame.K_F11:
                try:
                    cur = bool(self.save["settings"].get("fullscreen", False))
                    self.save["settings"]["fullscreen"] = not cur
                    save_system.save_game(self.save)
                    self._try_apply_display(fullscreen=not cur)
                    audio.play("click")
                except:
                    pass
                return
            # global hover/click sound
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                audio.play("hover", 0.6)
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                # menü onayı sesi
                if self.state in ("menu","characters","shop","inventory","themes","settings","paused","gameover"):
                    audio.play("click")

            if self.state == "playing":
                # FAZ11: level intro skip (ESC/SPACE/ENTER)
                if getattr(self, 'level_intro_active', False):
                    if event.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
                        self.level_intro_active = False
                        try:
                            if self.level_mode not in self.save.get("seen_lore", []):
                                self.save["seen_lore"].append(self.level_mode)
                                self.save["seen_lore"] = sorted(set(self.save["seen_lore"]))
                                save_system.save_game(self.save)
                        except: pass
                        return
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
                elif event.key == pygame.K_f or event.key == pygame.K_j:
                    # FAZ6: attack
                    try:
                        wid = self.save.get("equipped_weapon","fist")
                        if self.player.try_attack(wid):
                            w = config.get_weapon(wid)
                            self._play_sfx_cd("sword_swing" if wid=="beam_sword" else "punch", cd=0.08, volume=0.7)
                    except: pass
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
            elif self.state == "final_cinematic":
                self.handle_final_cinematic_keys(event)
            elif self.state in ("lore",):
                if event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    try: audio.play("click")
                    except: pass
            elif self.state in ("stats", "achievements"):
                if event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    try: audio.play("click")
                    except: pass
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
            # FAZ6: left click attack in gameplay
            if getattr(event, 'button', 1) == 1 and self.state in ("playing","vs_bot","vs_online") and not getattr(self, 'paused', False) and getattr(self.player, 'alive', True):
                try:
                    wid = self.save.get("equipped_weapon","fist")
                    if self.player.try_attack(wid):
                        w = config.get_weapon(wid)
                        self._play_sfx_cd("sword_swing" if wid=="beam_sword" else "punch", cd=0.08, volume=0.7)
                except: pass
                # still allow handle_mouse for UI, but playing has no UI, so return
                if self.state in ("playing","vs_bot","vs_online"):
                    return
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
            elif self.state == "themes":
                # 4 columns, one row per wheel step
                steps = max(1, abs(event.y))
                if event.y > 0:
                    self.theme_index = max(0, self.theme_index - 4*steps)
                else:
                    self.theme_index = min(len(config.THEMES)-1, self.theme_index + 4*steps)
                try: audio.play("hover",0.3)
                except: pass

    def _trigger_transition(self, v=0.35):
        try:
            self.transition = v
            self.transition_target = "fade"
        except: pass

    def _sfx(self, event):
        """Ses altyapısı haritası — yeni dosya yok, mevcut audio.play kullanılır."""
        try:
            if event == "menu_hover":
                audio.play("hover", 0.5)
            elif event == "menu_click":
                audio.play("click")
            elif event == "theme_select":
                audio.play("unlock", 0.8)
            elif event == "locked":
                audio.play("death", 0.4)
            elif event == "purchase":
                audio.play("purchase")
            elif event == "equip":
                audio.play("click")
        except: pass

    def _owned_theme_ids(self):
        """Tema sahipliği — şu an tümü açık; mağaza bağlantısı için yapı hazır."""
        try:
            owned = self.save.get("owned_themes", None)
            if isinstance(owned, list) and owned:
                return set(str(x) for x in owned)
        except: pass
        return set(t["id"] for t in config.THEMES)

    def _theme_atmosphere(self, surf, theme):
        """Tema atmosferi — mevcut glow/particle altyapısı, max 2 glow + birkaç çizgi/nokta."""
        try:
            tid = theme.get("id", "")
            glow_c = theme.get("glow", (255, 215, 0, 60))
            if isinstance(glow_c, (list, tuple)) and len(glow_c) == 4:
                glow_c3 = (glow_c[0], glow_c[1], glow_c[2])
            elif isinstance(glow_c, (list, tuple)):
                glow_c3 = tuple(glow_c[:3])
            else:
                glow_c3 = (255, 215, 0)
            accent = theme.get("accent", glow_c3)
            # hafif ışık bölgeleri (tema glow/accent, sabit konum — per-frame random yok)
            h1 = hash(tid + "_a") % 600
            h2 = hash(tid + "_b") % 600
            gfx.draw_glow(surf, (150 + h1 % 200, 140), 70, glow_c3, 12)
            gfx.draw_glow(surf, (750 - h2 % 200, 560), 80, accent if isinstance(accent, tuple) else glow_c3, 10)
            # çok hafif geometri (sadece bazı temalar)
            if tid == "industrial_gray":
                for yy in (210, 420, 560):
                    pygame.draw.line(surf, (120, 125, 135, 60), (60, yy), (180, yy), 1)
                    pygame.draw.line(surf, (120, 125, 135, 60), (720, yy + 20), (840, yy + 20), 1)
            elif tid == "retro_arcade":
                for ix in range(6):
                    for iy in range(3):
                        px = 80 + ix * 24 + (hash(tid) % 7)
                        py = 600 + iy * 12
                        pygame.draw.rect(surf, accent if isinstance(accent, tuple) else (0, 230, 200), (px, py, 5, 5))
            elif tid == "monochrome":
                pygame.draw.line(surf, (150, 150, 150, 70), (0, 350), (config.SCREEN_WIDTH, 350), 1)
            elif tid in ("neon_cyan", "retro_arcade", "ocean"):
                pygame.draw.line(surf, (*glow_c3, 50) if len(glow_c3) == 3 else glow_c3, (0, 120), (config.SCREEN_WIDTH, 120), 1)
        except: pass

    def activate_menu(self):
        self._trigger_transition(0.35)
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
        elif opt == "İSTATİSTİKLER":
            self.state = "stats"
        elif opt == "BAŞARIMLAR":
            self.state = "achievements"
        elif opt == "HİKAYE":
            self.state = "lore"
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
            key = ["hat","bag","glasses","cane","weapon"][self.inv_tab]
            if key == "weapon":
                lst = [config.WEAPONS[wid] for wid in self.save.get("owned_weapons", ["fist"]) if wid in config.WEAPONS]
                # convert to shop-like dict for rendering (needs id,name,price,icon)
                lst = [{"id": w["id"], "name": w["name"], "price": w["price"], "icon": w.get("icon","W")} for w in lst]
            else:
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
        tabs = ["hat","bag","glasses","cane","weapon"]
        key = tabs[self.shop_tab]
        if key == "weapon":
            # FAZ6: weapons are in config.WEAPONS, not SHOP_ITEMS
            lst = []
            for wid, w in config.WEAPONS.items():
                lst.append({"id": w["id"], "name": w["name"], "price": w["price"], "icon": w.get("icon","W")})
            return lst, key
        return config.SHOP_ITEMS[key], key

    def handle_shop_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"; save_system.save_game(self.save); return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self._reset_list("shop")
            self.shop_tab = (self.shop_tab -1) % 5; audio.play("hover",0.6)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._reset_list("shop")
            self.shop_tab = (self.shop_tab +1) %5; audio.play("hover",0.6)
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
                if key == "weapon":
                    owned = item["id"] in self.save.get("owned_weapons", ["fist"])
                    if owned:
                        if self.save.get("equipped_weapon") == item["id"]:
                            # fist cannot be unequipped fully, fallback to fist
                            if item["id"] != "fist":
                                self.save["equipped_weapon"] = "fist"
                                try: self.player.attack_weapon = "fist"
                                except: pass
                                self._add_notification(f"CIKARILDI: {item['name']} -> YUMRUK", (180,180,180))
                            else:
                                self._add_notification("YUMRUK zaten kusanili", (180,180,180))
                        else:
                            self.save["equipped_weapon"] = item["id"]
                            try: self.player.attack_weapon = item["id"]
                            except: pass
                            self._add_notification(f"KUSANILDI: {item['name']}!", (80,220,255))
                            self._play_sfx_cd("weapon_equip", cd=0.12, volume=0.8)
                        save_system.save_game(self.save)
                        self._game_mutated()
                    else:
                        if self.save["total_coins"] >= item["price"]:
                            self.save["total_coins"] -= item["price"]
                            if "owned_weapons" not in self.save: self.save["owned_weapons"]=[]
                            if item["id"] not in self.save["owned_weapons"]:
                                self.save["owned_weapons"].append(item["id"])
                            self.save["equipped_weapon"] = item["id"]
                            try: self.player.attack_weapon = item["id"]
                            except: pass
                            save_system.save_game(self.save)
                            self._game_mutated()
                            try:
                                self._shop_flash[item["id"]] = 0.6
                                self._add_notification(f"SATIN ALINDI: {item['name']}!", (80,220,120))
                                self._play_sfx_cd("purchase", cd=0.2, volume=0.9)
                                self.particles.emit_coin(450, 200, 3)
                            except: pass
                            audio.play("weapon_equip")
                        else:
                            self._play_sfx_cd("death", cd=0.2, volume=0.4)
                            audio.play("death",0.4)
                else:
                    owned = item["id"] in self.save["owned_items"]
                    if owned:
                        sel_key = {"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                        if self.save.get(sel_key) == item["id"]:
                            self.save[sel_key] = None
                            self._add_notification(f"CIKARILDI: {item['name']}", (180,180,180))
                        else:
                            self.save[sel_key] = item["id"]
                            self._add_notification(f"KUSANILDI: {item['name']}!", (80,200,255))
                            self._play_sfx_cd("click", cd=0.12, volume=0.8)
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
                            # FAZ5: purchase polish
                            try:
                                self._shop_flash[item["id"]] = 0.6
                                self._add_notification(f"SATIN ALINDI: {item['name']}!", (80,220,120))
                                self._play_sfx_cd("purchase", cd=0.2, volume=0.9)
                                self.particles.emit_coin(450, 200, 3)
                            except: pass
                            audio.play("purchase")
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
                try:
                    self._add_notification(f"KARAKTER: {ch['name']}!", (120,220,255))
                    self._play_sfx_cd("click", cd=0.12, volume=0.8)
                except: pass
                audio.play("click")

    def handle_inv_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state="menu"; return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self._reset_list("inventory")
            self.inv_tab = (self.inv_tab -1) %5; audio.play("hover",0.6)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._reset_list("inventory")
            self.inv_tab = (self.inv_tab+1)%5; audio.play("hover",0.6)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.inv_index = max(0, self.inv_index-1)
            self._ensure_selection_visible("inventory")
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            tabs=["hat","bag","glasses","cane","weapon"]
            key=tabs[self.inv_tab]
            if key == "weapon":
                owned = [config.WEAPONS[wid] for wid in self.save.get("owned_weapons", ["fist"]) if wid in config.WEAPONS]
                owned = [{"id": w["id"], "name": w["name"], "price": w["price"], "icon": w.get("icon","W")} for w in owned]
            else:
                owned = [it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
            self.inv_index = min(max(0,len(owned)-1), self.inv_index+1)
            self._ensure_selection_visible("inventory")
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            tabs=["hat","bag","glasses","cane","weapon"]
            key=tabs[self.inv_tab]
            if key == "weapon":
                owned_raw = [config.WEAPONS[wid] for wid in self.save.get("owned_weapons", ["fist"]) if wid in config.WEAPONS]
                owned = [{"id": w["id"], "name": w["name"], "price": w["price"], "icon": w.get("icon","W")} for w in owned_raw]
            else:
                owned = [it for it in config.SHOP_ITEMS[key] if it["id"] in self.save["owned_items"]]
            if owned and 0 <= self.inv_index < len(owned):
                item = owned[self.inv_index]
                if key == "weapon":
                    if self.save.get("equipped_weapon")==item["id"]:
                        if item["id"] != "fist":
                            self.save["equipped_weapon"]="fist"
                            self._add_notification(f"CIKARILDI: {item['name']} -> YUMRUK", (180,180,180))
                        else:
                            self._add_notification("YUMRUK zaten kusanili", (180,180,180))
                    else:
                        self.save["equipped_weapon"]=item["id"]
                        self._add_notification(f"KUSANILDI: {item['name']}!", (80,220,255))
                        self._play_sfx_cd("weapon_equip", cd=0.12, volume=0.8)
                else:
                    sel_key = {"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                    if self.save.get(sel_key)==item["id"]:
                        self.save[sel_key]=None
                        self._add_notification(f"CIKARILDI: {item['name']}", (180,180,180))
                    else:
                        self.save[sel_key]=item["id"]
                        self._add_notification(f"KUSANILDI: {item['name']}!", (80,200,255))
                        self._play_sfx_cd("click", cd=0.12, volume=0.8)
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
            self._trigger_transition(0.25)
            self._sfx("theme_select")
            # FAZ5: theme equip feedback
            try:
                tn = config.THEMES[self.theme_index]["name"]
                self._add_notification(f"TEMA: {tn}!", (180,220,255))
                self._play_sfx_cd("unlock", cd=0.2, volume=0.7)
            except: pass

    def handle_settings_keys(self, event):
        if event.key == pygame.K_ESCAPE:
            # geri - paused ise playing+paused bayrağı ile dön
            if self.prev_state == "paused":
                self.state = "playing"
                self.paused = True
            else:
                self.state = self.prev_state if self.prev_state in ("menu",) else "menu"
            save_system.save_game(self.save)
            audio.play("click")
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
            elif self.settings_index == 4:  # fullscreen toggle (ENTER)
                cur = bool(self.save["settings"].get("fullscreen", False))
                self.save["settings"]["fullscreen"] = not cur
                save_system.save_game(self.save)
                self._try_apply_display(fullscreen=not cur)
                audio.play("click")
            elif self.settings_index == 5:  # fps cycle (ENTER)
                cur = int(self.save["settings"].get("fps_limit", 60))
                opts = [30,60,90,120,0]
                idx = opts.index(cur) if cur in opts else 1
                nxt = opts[(idx+1)%len(opts)]
                self.save["settings"]["fps_limit"] = nxt
                save_system.save_game(self.save)
                audio.play("click")
            elif self.settings_index == 6:  # resolution cycle (ENTER)
                cur = str(self.save["settings"].get("resolution","900x700"))
                opts = ["900x700","1280x720","1600x900","1920x1080"]
                idx = opts.index(cur) if cur in opts else 0
                nxt = opts[(idx+1)%len(opts)]
                self.save["settings"]["resolution"] = nxt
                save_system.save_game(self.save)
                if not self.save["settings"].get("fullscreen", False):
                    self._try_apply_display(resolution=nxt)
                audio.play("click")
            elif self.settings_index == 7:  # controls info - show help
                self._open_help()
            elif self.settings_index == 8:  # geri
                if self.prev_state == "paused":
                    self.state = "playing"; self.paused = True
                else:
                    self.state = self.prev_state if self.prev_state in ("menu",) else "menu"
                save_system.save_game(self.save)
                audio.play("click")

    def adjust_setting(self, delta):
        s = self.save["settings"]
        if self.settings_index == 0:
            s["master"] = round(max(0, min(1, s.get("master",0.7)+delta)), 2)
            audio.set_master(s["master"])
        elif self.settings_index == 1:
            s["music"] = round(max(0, min(1, s.get("music",0.5)+delta)), 2)
            audio.set_music(s["music"])
        elif self.settings_index == 2:
            s["sfx"] = round(max(0, min(1, s.get("sfx",0.8)+delta)), 2)
            audio.set_sfx(s["sfx"])
        elif self.settings_index == 3:  # tutorial toggle via left/right
            if delta != 0:
                cur = bool(s.get("show_tutorial", True))
                s["show_tutorial"] = not cur
        elif self.settings_index == 4:  # fullscreen via left/right
            if delta != 0:
                cur = bool(s.get("fullscreen", False))
                s["fullscreen"] = not cur
                self._try_apply_display(fullscreen=not cur)
        elif self.settings_index == 5:  # fps cycle via left/right
            cur = int(s.get("fps_limit", 60))
            opts = [30,60,90,120,0]
            idx = opts.index(cur) if cur in opts else 1
            step = 1 if delta>0 else -1
            nxt = opts[(idx+step)%len(opts)]
            s["fps_limit"] = nxt
        elif self.settings_index == 6:  # resolution cycle via left/right
            cur = str(s.get("resolution","900x700"))
            opts = ["900x700","1280x720","1600x900","1920x1080"]
            idx = opts.index(cur) if cur in opts else 0
            step = 1 if delta>0 else -1
            nxt = opts[(idx+step)%len(opts)]
            s["resolution"] = nxt
            if not s.get("fullscreen", False):
                self._try_apply_display(resolution=nxt)
        elif self.settings_index == 7:
            # controls info - no ajuste, just feedback
            audio.play("hover",0.3)
            return
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
        # FAZ10: block early input until buttons appear (0.88s)
        if getattr(self, 'level_complete_timer', 0) < 0.88:
            if event.key == pygame.K_ESCAPE:
                self.state = "levels"
                return
            return
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

    def handle_final_cinematic_keys(self, event):
        if event.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
            self.state = "level_complete"
            self.level_complete_timer = 0.90
            self.save["final_cinematic_seen"] = True
            try: save_system.save_game(self.save)
            except: pass
            audio.play("click")
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
        # Eğer henüz ID yoksa server'dan iste — yerel hesap varsa account_username kullan
        pid = str(self.save.get("player_id") or "").strip()
        nick = self._get_online_nick()
        import save_system as _ss
        if not _ss.is_valid_player_id(pid):
            # İlk ONLINE — server ID üretsin (aynı yerel hesap için tek ID)
            print(f"[ONLINE] İlk giriş {nick} için register_new", flush=True)
            ok, result = self.online_mgr.register_new(nick)
            if not ok:
                if "Sunucuya bağlanılamadı" in str(result):
                    self.online_error = "Sunucuya bağlanılamadı."
                else:
                    self.online_error = result
                return
            # ok -> save zaten güncellendi (register_new içinde) -> aynı hesap için korunur
            print(f"[ONLINE] Yeni ID {result} -> {nick} kaydedildi", flush=True)
            self.online_error = ""
        else:
            # Mevcut geçerli ID ile login — tekrar register_new çalıştırma
            ok, msg = self.online_mgr.login()
            if not ok:
                if "bulunamadı" in str(msg):
                    print(f"[ONLINE] ID {pid} sunucuda bulunamadı ({nick}), kontrollü yeniden kayıt", flush=True)
                    self.online_error = f"Eski ID bulunamadı, yeni ID alınıyor..."
                    ok2, res2 = self.online_mgr.register_new(nick)
                    if not ok2:
                        self.online_error = res2 if "Sunucuya" in str(res2) else "Sunucuya bağlanılamadı."
                        return
                    print(f"[ONLINE] Yeni ID {res2} verildi (eski {pid} yoktu)", flush=True)
                    self.online_error = ""
                elif "Sunucuya bağlanılamadı" in str(msg):
                    self.online_error = "Sunucuya bağlanılamadı."
                    return
                else:
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
        try: self.player.attack_weapon = self.save.get("equipped_weapon","fist")
        except: pass
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
        try: self._update_level_music("HAVA", force=True)
        except: pass
        try: self._update_level_music("HAVA", force=True)
        except: pass

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
        try: self.player.attack_weapon = self.save.get("equipped_weapon","fist")
        except: pass
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
        try: self.player.attack_weapon = self.save.get("equipped_weapon","fist")
        except: pass
        self.camera.reset(self.player.y)
        self.world.reset()
        self.particles = ParticleSystem()
        self.level = 1
        self.level_info = config.LEVELS[0]
        self.monster = Monster()
        self.monster.reset(self.player.y, 1, "HAVA")
        try: self._update_level_music("HAVA", force=True)
        except: pass
        try: self._update_level_music("HAVA", force=True)
        except: pass
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
        elif event.key in (pygame.K_f, pygame.K_j):
            # FAZ6: vs attack
            try:
                wid = self.save.get("equipped_weapon","fist")
                if self.player.try_attack(wid):
                    w = config.get_weapon(wid)
                    self._play_sfx_cd("sword_swing" if wid=="beam_sword" else "punch", cd=0.08, volume=0.7)
            except: pass
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
            # draw_menu ile aynı geometri (FAZ10 adaptive 11 için)
            _n = len(self.menu_options)
            if _n > 10:
                btn_w, btn_h = 320, 38; start_y = 180; gap = 42
            else:
                btn_w, btn_h = 326, 44; start_y = 194; gap = 50
            for i in range(len(self.menu_options)):
                bx = config.SCREEN_WIDTH//2 - btn_w//2; by = start_y + i*gap
                if bx <= mx <= bx+btn_w and by <= my <= by+btn_h:
                    self.menu_index = i
                    self._btn_press_idx = i; self._btn_press_t = 0.12
                    self._sfx("menu_click"); self.activate_menu(); break
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
            lay = self._settings_layout()
            card = lay["card"]
            bars = lay["bars"]
            rows = lay["rows"]
            back = lay["back"]
            # sliders 0..2
            for idx in range(3):
                y, bar = bars[idx]
                hit = bar.inflate(0, 10)
                # also expand to row hit
                row_hit = pygame.Rect(card.x+14, y-4, card.width-28, 36)
                if hit.collidepoint(mx,my) or row_hit.collidepoint(mx,my):
                    # only if bar area: if clicking row but not bar, treat as selection?
                    # but for precise, if click inside bar -> set value
                    if hit.collidepoint(mx,my):
                        rel = round(max(0,min(1,(mx - bar.x)/bar.width)), 2)
                        key = ["master","music","sfx"][idx]
                        self.save["settings"][key]=rel
                        if key=="master": audio.set_master(rel)
                        elif key=="music": audio.set_music(rel)
                        elif key=="sfx": audio.set_sfx(rel)
                        save_system.save_game(self.save)
                        self.settings_index = idx
                        audio.play("hover",0.3)
                        return
                    else:
                        # row click -> select
                        self.settings_index = idx
                        audio.play("hover",0.3)
                        return
            # rows 3..7
            if rows[3].collidepoint(mx,my):
                self.settings_index = 3
                cur = self.save["settings"].get("show_tutorial", True)
                self.save["settings"]["show_tutorial"]=not cur
                save_system.save_game(self.save)
                audio.play("click")
                return
            if rows[4].collidepoint(mx,my):
                self.settings_index = 4
                cur = bool(self.save["settings"].get("fullscreen", False))
                self.save["settings"]["fullscreen"] = not cur
                save_system.save_game(self.save)
                self._try_apply_display(fullscreen=not cur)
                audio.play("click")
                return
            if rows[5].collidepoint(mx,my):
                self.settings_index = 5
                # cycle fps on click
                cur = int(self.save["settings"].get("fps_limit", 60))
                opts = [30,60,90,120,0]
                idx = opts.index(cur) if cur in opts else 1
                nxt = opts[(idx+1)%len(opts)]
                self.save["settings"]["fps_limit"] = nxt
                save_system.save_game(self.save)
                audio.play("click")
                return
            if rows[6].collidepoint(mx,my):
                self.settings_index = 6
                cur = str(self.save["settings"].get("resolution","900x700"))
                opts = ["900x700","1280x720","1600x900","1920x1080"]
                idx = opts.index(cur) if cur in opts else 0
                nxt = opts[(idx+1)%len(opts)]
                self.save["settings"]["resolution"] = nxt
                save_system.save_game(self.save)
                if not self.save["settings"].get("fullscreen", False):
                    self._try_apply_display(resolution=nxt)
                audio.play("click")
                return
            if rows[7].collidepoint(mx,my):
                self.settings_index = 7
                self._open_help()
                return
            if back.collidepoint(mx,my):
                self.settings_index = 8
                if self.prev_state == "paused":
                    self.state = "playing"; self.paused = True
                else:
                    self.state = self.prev_state if self.prev_state in ("menu",) else "menu"
                save_system.save_game(self.save)
                audio.play("click")
                return
            # also bar hover selection without click? handled via motion
            # click on empty card selects nearest? no
        elif self.state=="shop":
            # tab hit
            tabs = ["SAPKA","CANTA","GOZLUK","BASTON","SİLAH"]
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
                    # FAZ6: weapon handling for mouse shop
                    if key == "weapon":
                        owned_w = item["id"] in self.save.get("owned_weapons", ["fist"])
                        if owned_w:
                            if self.save.get("equipped_weapon")==item["id"]:
                                if item["id"] != "fist":
                                    self.save["equipped_weapon"]="fist"
                                    self._add_notification(f"CIKARILDI: {item['name']} -> YUMRUK", (180,180,180))
                                else:
                                    self._add_notification("YUMRUK zaten kusanili", (180,180,180))
                            else:
                                self.save["equipped_weapon"]=item["id"]
                                self._add_notification(f"KUSANILDI: {item['name']}!", (80,220,255))
                                self._play_sfx_cd("weapon_equip", cd=0.12, volume=0.8)
                            save_system.save_game(self.save); self._game_mutated(); audio.play("click")
                        else:
                            if self.save["total_coins"]>=item["price"]:
                                self.save["total_coins"]-=item["price"]
                                if "owned_weapons" not in self.save: self.save["owned_weapons"]=[]
                                if item["id"] not in self.save["owned_weapons"]:
                                    self.save["owned_weapons"].append(item["id"])
                                self.save["equipped_weapon"]=item["id"]
                                try: self.player.attack_weapon=item["id"]
                                except: pass
                                save_system.save_game(self.save); self._game_mutated()
                                try:
                                    self._shop_flash[item["id"]] = 0.6
                                    self._add_notification(f"SATIN ALINDI: {item['name']}!", (80,220,120))
                                    self._play_sfx_cd("purchase", cd=0.2, volume=0.9)
                                except: pass
                                audio.play("weapon_equip")
                            else:
                                audio.play("death",0.4)
                    else:
                        owned=item["id"] in self.save["owned_items"]
                        if owned:
                            sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                            if self.save.get(sel_key)==item["id"]: self.save[sel_key]=None
                            else: self.save[sel_key]=item["id"]
                            save_system.save_game(self.save); self._game_mutated(); audio.play("click")
                        else:
                            sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                            if self.save["total_coins"]>=item["price"]:
                                self.save["total_coins"]-=item["price"]; self.save["owned_items"].append(item["id"])
                                self.save[sel_key]=item["id"]; save_system.save_game(self.save); self._game_mutated()
                                try:
                                    self._shop_flash[item["id"]] = 0.6
                                    self._add_notification(f"SATIN ALINDI: {item['name']}!", (80,220,120))
                                    self._play_sfx_cd("purchase", cd=0.2, volume=0.9)
                                except: pass
                                audio.play("purchase")
                            else:
                                audio.play("death",0.4)
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
            tabs=["SAPKA","CANTA","GOZLUK","BASTON","SİLAH"]
            tab_w=110; gap=12; total_w=len(tabs)*tab_w+(len(tabs)-1)*gap; start_x=config.SCREEN_WIDTH//2-total_w//2
            for i in range(len(tabs)):
                r=pygame.Rect(start_x+i*(tab_w+gap),68,tab_w,28)
                if r.collidepoint(mx,my):
                    self._reset_list("inventory"); self.inv_tab=i; audio.play("click"); return
            lay = self._list_layout("inventory")
            key=["hat","bag","glasses","cane","weapon"][self.inv_tab]
            owned=lay["lst"]
            for idx,item in enumerate(owned):
                y = lay["list_y"] + idx*lay["step"] - lay["scroll"]
                r=pygame.Rect(60,y,config.SCREEN_WIDTH-120,lay["row_h"])
                if r.collidepoint(mx,my):
                    self.inv_index=idx
                    if key == "weapon":
                        if self.save.get("equipped_weapon")==item["id"]:
                            if item["id"] != "fist":
                                self.save["equipped_weapon"]="fist"
                                self._add_notification(f"CIKARILDI: {item['name']} -> YUMRUK", (180,180,180))
                            else:
                                self._add_notification("YUMRUK zaten kusanili", (180,180,180))
                        else:
                            self.save["equipped_weapon"]=item["id"]
                            self._add_notification(f"KUSANILDI: {item['name']}!", (80,220,255))
                            self._play_sfx_cd("weapon_equip", cd=0.12, volume=0.8)
                    else:
                        sel_key={"hat":"selected_hat","bag":"selected_bag","glasses":"selected_glasses","cane":"selected_cane"}[key]
                        if self.save.get(sel_key)==item["id"]: self.save[sel_key]=None
                        else: self.save[sel_key]=item["id"]
                    save_system.save_game(self.save); self._game_mutated(); audio.play("click")
                    break
        elif self.state=="themes":
            cols=4; card_w,card_h=190,110; gap_x,gap_y=18,16
            start_x=config.SCREEN_WIDTH//2 - (cols*card_w+(cols-1)*gap_x)//2; start_y=88
            cur_row = (self.theme_index // cols)
            total_rows = (len(config.THEMES) + cols - 1)//cols
            first_row = max(0, min(cur_row - 1, max(0, total_rows - 4)))
            y_off = first_row * (card_h + gap_y)
            for idx,t in enumerate(config.THEMES):
                row=idx//cols; col=idx%cols
                x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y) - y_off
                r=pygame.Rect(x,y,card_w,card_h)
                if r.collidepoint(mx,my):
                    self.theme_index=idx; self.save["theme"]=t["id"]; save_system.save_game(self.save); self._game_mutated(); self._trigger_transition(0.25); self._sfx("theme_select"); break
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
        elif self.state in ("stats", "achievements", "lore"):
            back = pygame.Rect(config.SCREEN_WIDTH//2-90, config.SCREEN_HEIGHT-60, 180, 36)
            if back.collidepoint(mx,my):
                self.state="menu"
                audio.play("click")
        elif self.state=="level_complete":
            if getattr(self, 'level_complete_timer',0) < 0.88:
                return
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
        elif self.state=="final_cinematic":
            self.state="level_complete"
            self.level_complete_timer=0.90
            self.save["final_cinematic_seen"]=True
            try: save_system.save_game(self.save)
            except: pass
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
            _n = len(self.menu_options)
            if _n > 10:
                btn_w, btn_h = 320, 38; start_y = 180; gap = 42
            else:
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
                self.world.draw(surf, self.camera.y, self.level_info, theme)
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
                # FAZ11: level intro (first time)
                try:
                    if getattr(self, 'level_intro_active', False):
                        _a_in = 1.0
                        if self.level_intro_timer < 0.3:
                            _a_in = self.level_intro_timer/0.3
                        elif self.level_intro_timer > 1.2:
                            _a_in = (1.6 - self.level_intro_timer)/0.4
                        _a_in = max(0, min(1, _a_in))
                        _lore11 = config.LEVEL_LORE.get(self.level_mode, {"title": self.level_info["name"], "text": ""})
                        _bar = pygame.Rect(config.SCREEN_WIDTH//2-220, config.SCREEN_HEIGHT//2-40, 440, 80)
                        _s = pygame.Surface((_bar.width, _bar.height), pygame.SRCALPHA)
                        _s.fill((0,0,0, int(170*_a_in)))
                        surf.blit(_s, _bar.topleft)
                        pygame.draw.rect(surf, (255,215,0, int(200*_a_in)), _bar, width=2, border_radius=10)
                        _t1 = self.font_big.render(_lore11["title"], True, (255,215,0))
                        _t1.set_alpha(int(255*_a_in))
                        surf.blit(_t1, (_bar.centerx - _t1.get_width()//2, _bar.y+14))
                        _t2 = self.font_small.render(_lore11["text"], True, (255,255,255))
                        _t2.set_alpha(int(255*_a_in))
                        # wrap if too long
                        if _t2.get_width() > _bar.width-20:
                            # simple split
                            _words = _lore11["text"].split(" ")
                            _l1=""; _l2=""
                            for _w in _words:
                                _test = (_l1+" "+_w).strip()
                                if self.font_small.size(_test)[0] < _bar.width-20:
                                    _l1=_test
                                else:
                                    _l2+=_w+" "
                            _t2a=self.font_small.render(_l1.strip(), True, (255,255,255)); _t2a.set_alpha(int(255*_a_in))
                            surf.blit(_t2a, (_bar.centerx - _t2a.get_width()//2, _bar.y+44))
                            if _l2.strip():
                                _t2b=self.font_tiny.render(_l2.strip(), True, (200,200,210)); _t2b.set_alpha(int(200*_a_in))
                                surf.blit(_t2b, (_bar.centerx - _t2b.get_width()//2, _bar.y+62))
                        else:
                            surf.blit(_t2, (_bar.centerx - _t2.get_width()//2, _bar.y+44))
                except: pass
                # FAZ9: death/finish flash (subtle)
                try:
                    if getattr(self, 'death_flash',0)>0:
                        _a = int(90*min(1, self.death_flash))
                        _over = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                        _over.fill((20,0,0, _a//2))
                        surf.blit(_over, (0,0))
                    elif getattr(self, 'finish_flash',0)>0:
                        _a2 = int(70*min(1, self.finish_flash))
                        _over2 = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                        _over2.fill((255,215,0, _a2//4))
                        surf.blit(_over2, (0,0))
                except: pass
                # tutorial overlay
                if self.state=="playing" and not self.paused and self.save.get("settings",{}).get("show_tutorial",True) and not self.save.get("tutorial_done",False):
                    self.draw_tutorial(surf)
                if self.level_up_anim > 0:
                    self.draw_levelup(surf)
                # (FAZ14) legacy marş gostergesi kaldirildi
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
            elif self.state=="stats":
                self.draw_stats(surf, theme)
            elif self.state=="achievements":
                self.draw_achievements(surf, theme)
            elif self.state=="lore":
                self.draw_lore(surf, theme)
            elif self.state=="level_complete":
                # arka planı da çiz (donmuş oyun)
                self.world.draw(surf, self.camera.y, self.level_info, theme)
                self.particles.draw(surf, self.camera.y)
                if hasattr(self, 'monster'):
                    try: self.monster.draw(surf, self.camera.y)
                    except: pass
                self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
                self.draw_hud(surf, theme)
                self.draw_level_complete(surf, theme)
            elif self.state=="ending":
                self.world.draw(surf, self.camera.y, self.level_info, theme)
                self.particles.draw(surf, self.camera.y)
                if hasattr(self, 'monster'):
                    try: self.monster.draw(surf, self.camera.y)
                    except: pass
                self.player.draw(surf, self.camera.y, self.get_char_data(), self.get_equipped(), theme)
                self.draw_ending(surf, theme)
            elif self.state=="final_cinematic":
                self.draw_final_cinematic(surf, theme)
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
                self.world.draw(surf, self.camera.y, self.level_info, theme)
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
                self.world.draw(surf, self.camera.y, self.level_info, theme)
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
        # FAZ5: HUD coin flash (pop scale when just collected)
        try:
            _cf = getattr(self, '_hud_coin_flash', 0)
            if _cf > 0:
                scale = 1.0 + _cf*0.18
                # scale via font size trick: just glow
                gfx.draw_glow(surf, (coin_bg.centerx, coin_bg.centery), 22, (255,215,0), int(30*_cf))
        except: pass
        surf.blit(coin_txt, (coin_bg.x+40, coin_bg.y+6))
        plus = self.font_small.render(f"+{self.player.coins}", True, (255,238,130))
        surf.blit(plus, (coin_bg.x+40+coin_txt.get_width()+8, coin_bg.y+13))
        # FAZ5: combo HUD (center top)
        try:
            if getattr(self, 'combo', 0) >= 2:
                _ct = getattr(self, 'combo_timer', 0)
                _alpha = int(180 * min(1, _ct/1.6)) if _ct>0 else 0
                if _alpha>20:
                    cbg = pygame.Rect(config.SCREEN_WIDTH//2-62, 8, 124, 22)
                    pygame.draw.rect(surf, (0,0,0,90), cbg, border_radius=8)
                    pygame.draw.rect(surf, (255,215,0,120), cbg, width=1, border_radius=8)
                    ctxt = self.font_small.render(f"COMBO x{self.combo}", True, (255,238,130))
                    surf.blit(ctxt, (cbg.centerx - ctxt.get_width()//2, cbg.centery - ctxt.get_height()//2))
                    if self.combo >= 4:
                        gfx.draw_glow(surf, cbg.center, 16, (255,215,0), 16)
        except: pass
        # FAZ6: weapon HUD (bottom left, small)
        try:
            wid = self.save.get("equipped_weapon","fist")
            w = config.get_weapon(wid)
            # cooldown progress
            cd = getattr(self.player, 'attack_cooldown', 0) if hasattr(self, 'player') else 0
            max_cd = w["cooldown"]
            prog = 1 - (cd / max_cd) if max_cd>0 else 1
            prog = max(0,min(1,prog))
            wbg = pygame.Rect(12, config.SCREEN_HEIGHT-28, 140, 18)
            pygame.draw.rect(surf, (0,0,0,90), wbg, border_radius=6)
            pygame.draw.rect(surf, (80,220,255,120) if wid=="beam_sword" else (200,200,180,120), wbg, width=1, border_radius=6)
            # cooldown bar
            if prog < 1:
                bar = pygame.Rect(wbg.x+2, wbg.y+2, int((wbg.width-4)*prog), wbg.height-4)
                pygame.draw.rect(surf, (80,220,255) if wid=="beam_sword" else (255,220,180), bar, border_radius=4)
            wtxt = self.font_tiny.render(f"{w['name']}", True, (255,255,255))
            surf.blit(wtxt, (wbg.centerx - wtxt.get_width()//2, wbg.centery - wtxt.get_height()//2))
            if cd > 0:
                gfx.draw_glow(surf, wbg.center, 10, (255,80,80), 12)
        except: pass
        # FAZ9: monster proximity vignette (subtle)
        try:
            _mc = getattr(self, '_monster_close', 0)
            if _mc > 0.18 and self.state in ("playing","vs_bot","vs_online"):
                _a = int(22*_mc)
                _vig2 = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                _vig2.fill((0,0,0, _a))
                surf.blit(_vig2, (0,0))
                gfx.draw_vignette(surf, intensity=0.10*_mc)
        except: pass
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
                ("M", "Müzik Aç/Kapat")]
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
        # Intro — siyah FREEFALL
        if getattr(self, 'intro_state', 'skip') == "logo":
            surf.fill((8,8,10))
            t = self.intro_timer
            alpha = int(255 * min(1, t*1.8))
            if t > 0.4:
                title = self.font_huge.render("FREEFALL", True, (255,255,255))
                title.set_alpha(alpha)
                surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, config.SCREEN_HEIGHT//2 - 30))
                sub = self.font_small.render("aşağıya düşüş başlıyor...", True, (180,180,190))
                sub.set_alpha(int(alpha*0.7))
                surf.blit(sub, (config.SCREEN_WIDTH//2 - sub.get_width()//2, config.SCREEN_HEIGHT//2 + 18))
                hint = self.font_tiny.render("SPACE/ENTER ile geç", True, (120,120,130))
                if t > 1.2:
                    surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, config.SCREEN_HEIGHT-30))
            return
        # FAZ12: opening cinematic 7.2s (12 adim)
        if getattr(self, 'opening_state', 'skip') == "opening":
            surf.fill((8,8,10))
            t = self.opening_timer
            # fade in/out
            alpha = 255
            if t < 0.4:
                alpha = int(255 * t/0.4)
            elif t > 6.6:
                alpha = int(255 * (7.2 - t)/0.6)
            alpha = max(0, min(255, alpha))
            gfx.draw_vignette(surf, intensity=0.22)
            # step timing
            # 0.5-1.4 Bir adım attın.
            # 1.5-2.4 Zemin kayboldu.
            # 2.5-3.4 Ve düşmeye başladın.
            # 3.5-4.6 silüet
            # 4.7-5.3 symbol edge
            # 5.4-6.6 Bu düşüşün sonu neresi?
            y0 = config.SCREEN_HEIGHT//2 - 40
            def _fade_txt(txt, col, y, appear, hold=0.9):
                if t < appear or t > appear+hold+0.3:
                    return
                a = alpha
                if t < appear+0.22:
                    a = int(alpha * (t-appear)/0.22)
                elif t > appear+hold:
                    a = int(alpha * (appear+hold+0.3 - t)/0.3)
                a = max(0, min(255, a))
                s = self.font_med.render(txt, True, col)
                s.set_alpha(a)
                surf.blit(s, (config.SCREEN_WIDTH//2 - s.get_width()//2, y))
            _fade_txt("Bir adım attın.", (255,255,255), y0, 0.5)
            _fade_txt("Zemin kayboldu.", (255,255,255), y0+32, 1.5)
            _fade_txt("Ve düşmeye başladın.", (255,215,0), y0+64, 2.5)
            # silüet 3.5-4.6
            if 3.5 < t < 4.7:
                a = int(alpha * (1 if t<4.4 else (4.7-t)/0.3))
                a = max(0, min(255, a))
                # simple silhouette: small player at center
                sx = config.SCREEN_WIDTH//2; sy = y0+110
                # glow behind
                gfx.draw_glow(surf, (sx, sy), 18, (200,200,210), int(14*a/255))
                # body
                pygame.draw.rect(surf, (60,60,70, a), pygame.Rect(sx-10, sy-10, 20, 26), border_radius=6)
                pygame.draw.circle(surf, (255,220,180, a), (sx, sy-16), 8)
                # symbol at edge 4.7-5.3
            if 4.7 < t < 5.6:
                a2 = 0
                if t < 5.0:
                    a2 = int(90 * (t-4.7)/0.3)
                elif t < 5.3:
                    a2 = 90
                else:
                    a2 = int(90 * (5.6 - t)/0.3)
                a2 = max(0, min(90, a2))
                sym = self.font_small.render(config.REPEATING_SYMBOL, True, (255,255,255))
                sym.set_alpha(a2)
                surf.blit(sym, (config.SCREEN_WIDTH-40, 24))
            _fade_txt("Bu düşüşün sonu neresi?", (180,220,255), y0+110, 5.4)
            hint = self.font_tiny.render("ESC / SPACE / ENTER ile geç", True, (120,120,130))
            hint.set_alpha(int(alpha*0.5))
            surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, config.SCREEN_HEIGHT-28))
            return
        # zengin gradient bg + tema atmosferi + low-cost menu particles
        gfx.vertical_gradient(surf, tuple(min(255,c+18) for c in theme["bg"]), tuple(max(0,c-14) for c in theme["bg"]))
        self._theme_atmosphere(surf, theme)
        # menu bg particles (max 15, tema particle rengi + tema tipi)
        tid = theme.get("id", "")
        for p in getattr(self, 'menu_particles', []):
            col = theme.get("particle", (200,200,210))
            if not (isinstance(col, (list,tuple)) and len(col)==3):
                continue
            px, py = int(p['x']), int(p['y'])
            if tid in ("ice", "arctic_night"):
                pygame.draw.line(surf, col, (px-3, py), (px+3, py), 1)
                pygame.draw.line(surf, col, (px, py-3), (px, py+3), 1)
                pygame.draw.circle(surf, col, (px, py), 1)
            elif tid in ("forest", "toxic_green"):
                pygame.draw.circle(surf, col, (px, py), 2)
                pygame.draw.line(surf, col, (px, py), (px+3, py-3), 1)
            elif tid in ("ocean",):
                pygame.draw.circle(surf, col, (px, py), 2, 1)
            elif tid in ("neon_cyan", "retro_arcade"):
                pygame.draw.rect(surf, col, (px-2, py-2, 4, 4))
            else:
                pygame.draw.circle(surf, col, (px, py), 2)
                gfx.draw_glow(surf, (px, py), 6, col, 12)
        gfx.draw_vignette(surf, intensity=0.13 if theme["id"]=="beyaz" else 0.22)
        # subtle top glow (cached, per-frame Surface yok)
        if not hasattr(self, '_menu_glow') or self._menu_glow is None:
            try:
                glow = pygame.Surface((config.SCREEN_WIDTH, 180), pygame.SRCALPHA)
                for i in range(90):
                    a=int(16*(1-i/90))
                    pygame.draw.line(glow,(255,255,255,a),(0,i),(config.SCREEN_WIDTH,i))
                self._menu_glow = glow
            except:
                self._menu_glow = None
        if getattr(self, '_menu_glow', None) is not None:
            surf.blit(self._menu_glow,(0,0))
        # başlık — logo cache + tema glow + kısa giriş (k<=1) + FAZ8 idle pulse
        k = min(1.0, getattr(self, '_menu_enter_t', 1.0))
        y_off = int((1.0 - k) * 12)
        # FAZ8: subtle logo pulse (scale 1.015, glow 16±3) - dt tabanlı, cache'i bozmadan
        _pulse = 1.0 + math.sin(self.menu_bg_time*1.9)*0.015 if k>=1 else 1.0
        _glow_a = 16 + int(math.sin(self.menu_bg_time*2.1)*3) if k>=1 else 16
        tkey = (theme.get("id",""), tuple(theme.get("hud",(30,30,30))[:3]))
        cached = self._logo_cache.get(tkey)
        if cached is None:
            try:
                _t = self.font_huge.render("FREEFALL", True, theme["hud"])
                _sh = self.font_huge.render("FREEFALL", True, (0,0,0))
                self._logo_cache[tkey] = (_t, _sh)
                if len(self._logo_cache) > 30:
                    self._logo_cache.pop(next(iter(self._logo_cache)))
            except:
                cached = None
        if cached is not None:
            title, sh = cached
            sh.set_alpha(80)
            # pulse scale via smoothscale (küçük, 1.015 max) - sadece k==1'de
            if _pulse != 1.0:
                try:
                    sw, sh2 = title.get_size()
                    pw, ph = int(sw*_pulse), int(sh2*_pulse)
                    p_title = pygame.transform.smoothscale(title, (pw, ph))
                    p_sh = pygame.transform.smoothscale(sh, (pw, ph))
                    surf.blit(p_sh, (config.SCREEN_WIDTH//2 - pw//2 + 3, 44 + y_off + 3))
                    surf.blit(p_title, (config.SCREEN_WIDTH//2 - pw//2, 42 + y_off))
                except:
                    surf.blit(sh, (config.SCREEN_WIDTH//2 - title.get_width()//2 + 3, 44 + y_off + 3))
                    surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 42 + y_off))
            else:
                surf.blit(sh, (config.SCREEN_WIDTH//2 - title.get_width()//2 + 3, 44 + y_off + 3))
                if k < 1.0:
                    title.set_alpha(int(255*k))
                else:
                    title.set_alpha(255)
                surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 42 + y_off))
        else:
            title = self.font_huge.render("FREEFALL", True, theme["hud"])
            surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 42 + y_off))
        _lg = theme.get("glow", (255,215,0,60))
        _lg3 = (_lg[0], _lg[1], _lg[2]) if isinstance(_lg,(list,tuple)) and len(_lg)>=3 else (255,215,0)
        gfx.draw_glow(surf, (config.SCREEN_WIDTH//2, 62 + y_off), 56, _lg3, _glow_a)
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
        # profil rozeti — nick + 5 haneli ID (ayrı, ????? yok)
        nick = self._get_display_nick()
        pid = self._get_display_id()
        prof_txt = f"Oyuncu: {nick}  •  ID: {pid}"
        prof = self.font_small.render(prof_txt, True, (255,255,255) if "siyah" in theme["id"] else (30,30,34))
        prof_box = pygame.Rect(config.SCREEN_WIDTH- prof.get_width()-28, 8, prof.get_width()+16, 22)
        pygame.draw.rect(surf, (0,0,0,48) if "siyah" in theme["id"] else (255,255,255,200), prof_box, border_radius=8)
        pygame.draw.rect(surf, (255,215,0,90), prof_box, width=1, border_radius=8)
        surf.blit(prof, (prof_box.centerx - prof.get_width()//2, prof_box.centery - prof.get_height()//2))
        # FAZ10: adaptive for 11 options
        _n = len(self.menu_options)
        if _n > 10:
            _pb_y = 142
            btn_w, btn_h = 320, 38; start_y = 182; gap = 42
        else:
            _pb_y = 148
            btn_w, btn_h = 326, 44; start_y = 194; gap = 50
        # mini karakter önizleme — glass card + FAZ7 idle (FAZ8 polish: subtle bob)
        ch = self.get_char_data()
        eq = self.get_equipped()
        preview_box = pygame.Rect(config.SCREEN_WIDTH//2 - 76, _pb_y, 152, 38)
        gfx.draw_soft_shadow(surf, preview_box, radius=10, alpha=22)
        gfx.glass_panel(surf, preview_box, fill=(255,255,255,210) if theme["id"]=="beyaz" else (38,38,44,210), border=(0,0,0,36), radius=9)
        cx = preview_box.centerx; cy = preview_box.centery + int(math.sin(self.menu_bg_time*2.0)*1.8)
        gfx.draw_glow(surf,(cx,cy-4),14,ch["accent"],22)
        pygame.draw.rect(surf, ch["color"], pygame.Rect(cx-13, cy-8, 26, 19), border_radius=5)
        pygame.draw.rect(surf,(0,0,0,160), pygame.Rect(cx-13, cy-8, 26, 19), width=1, border_radius=5)
        pygame.draw.circle(surf, (255,220,180), (cx, cy-12), 9)
        pygame.draw.circle(surf,(0,0,0,160),(cx, cy-12), 9, 1)
        if eq["hat"]:
            pygame.draw.rect(surf, (200,30,30), pygame.Rect(cx-11, cy-21, 22, 6), border_radius=3)
        mx,my = pygame.mouse.get_pos()
        _acc = theme.get("accent", (255,215,0))
        _acc3 = (_acc[0], _acc[1], _acc[2]) if isinstance(_acc,(list,tuple)) and len(_acc)>=3 else (255,215,0)
        for i, opt in enumerate(self.menu_options):
            bx = config.SCREEN_WIDTH//2 - btn_w//2; by = start_y + i*gap
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            hover = rect.collidepoint(mx,my)
            selected = i==self.menu_index
            is_exit = opt=="CIKIS"
            base = theme["button"]
            # FAZ8: basılma 1.5px aşağı + hafif squash, hover 6x3 büyütme
            is_press = (getattr(self,'_btn_press_idx',-1)==i and getattr(self,'_btn_press_t',0)>0)
            press_dy = 2 if is_press else 0
            if is_press:
                draw_rect = rect.inflate(-2, -1).move(0, press_dy)
            elif hover and not selected:
                draw_rect = rect.inflate(6, 3)
            else:
                draw_rect = rect
            # selected → gold gradient (korundu)
            if selected or hover:
                # soft shadow
                gfx.draw_soft_shadow(surf, draw_rect, radius=12, alpha=26)
                # gold bevel for selected
                top = (255,228,110) if selected else tuple(min(255,c+18) for c in base)
                bot = (255,185,0) if selected else tuple(max(0,c-14) for c in base)
                btn_surf = pygame.Surface((draw_rect.width, draw_rect.height), pygame.SRCALPHA)
                for y in range(draw_rect.height):
                    ts=y/draw_rect.height
                    rr=int(top[0]*(1-ts)+bot[0]*ts); gg=int(top[1]*(1-ts)+bot[1]*ts); bb=int(top[2]*(1-ts)+bot[2]*ts)
                    pygame.draw.line(btn_surf,(rr,gg,bb),(0,y),(draw_rect.width,y))
                mask = pygame.Surface((draw_rect.width, draw_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(mask,(255,255,255),(0,0,draw_rect.width,draw_rect.height), border_radius=11)
                btn_surf.blit(mask,(0,0), special_flags=pygame.BLEND_RGBA_MULT)
                surf.blit(btn_surf, draw_rect.topleft)
                pygame.draw.rect(surf,(255,215,0) if selected else _acc3, draw_rect, width=3 if selected else 2, border_radius=11)
                pygame.draw.line(surf,(255,255,255,92),(draw_rect.x+10,draw_rect.y+5),(draw_rect.right-10,draw_rect.y+5),1)
                if hover and not selected:
                    gfx.draw_glow(surf, draw_rect.center, 16, _acc3, 18)
                if selected:
                    gfx.draw_glow(surf, draw_rect.center, 20, (255,215,0), 22)
                    arrow = self.font_med.render("►", True, (255,215,0,220))
                    # glow arrow
                    surf.blit(arrow, (bx-26, draw_rect.centery - arrow.get_height()//2))
            else:
                pygame.draw.rect(surf, base, draw_rect, border_radius=11)
                pygame.draw.rect(surf,(0,0,0,110), draw_rect, width=2, border_radius=11)
                pygame.draw.line(surf,(255,255,255,44),(draw_rect.x+10,draw_rect.y+5),(draw_rect.right-10,draw_rect.y+5),1)
            txt_col = (28,18,4) if (selected or hover) else ((255,255,255) if theme["id"] in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (30,30,34))
            if is_exit and not (selected or hover):
                txt_col=(168,24,24) if "siyah" not in theme["id"] else (255,104,104)
            t = self.font_med.render(opt, True, txt_col)
            surf.blit(t, (draw_rect.centerx - t.get_width()//2, draw_rect.centery - t.get_height()//2))
        hint = self.font_small.render("↑↓ Seç  •  ENTER/SPACE Onayla  •  Mouse & Scroll", True, (theme["hud"][0],theme["hud"][1],theme["hud"][2], 210) if len(theme["hud"])==3 else theme["hud"])
        # ensure tuple
        hint_col = tuple(max(0,min(255,c)) for c in theme["hud"]) if isinstance(theme["hud"],(list,tuple)) else (30,30,30)
        hint_col = (hint_col[0],hint_col[1],hint_col[2])
        hint_surf = self.font_small.render("↑↓ Seç  •  ENTER/SPACE Onayla  •  Mouse & Scroll", True, hint_col)
        hint_surf.set_alpha(180)
        surf.blit(hint_surf, (config.SCREEN_WIDTH//2 - hint_surf.get_width()//2, config.SCREEN_HEIGHT-28))
        try:
            _fps_lab = self._fps_label(self.save.get("settings",{}).get("fps_limit",60))
        except:
            _fps_lab = "60 FPS"
        ver = self.font_tiny.render(f"v1.2  •  Tek Can  •  Sonsuz Dünya  •  {_fps_lab}", True, hint_col)
        ver.set_alpha(140)
        surf.blit(ver, (10, config.SCREEN_HEIGHT-15))
        # FAZ14: M — genel muzik toggle ipucu (legacy kaldirildi)
        is_muted = not getattr(audio, "music_enabled", True)
        mars_hint = self.font_tiny.render("M: ♫ Müzik Kapalı" if is_muted else "M: ♫ Müzik", True, (200,20,30) if is_muted else hint_col)
        mars_hint.set_alpha(170)
        surf.blit(mars_hint, (config.SCREEN_WIDTH - mars_hint.get_width() - 10, config.SCREEN_HEIGHT-15))

    def draw_shop(self, surf, theme):
        surf.fill(theme["bg"])
        gfx.draw_vignette(surf, intensity=0.13 if theme["id"]=="beyaz" else 0.22)
        title = self.font_big.render("MAGAZA", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        coin = self.font_med.render(f"COIN: {self.save['total_coins']}", True, (120,90,0) if theme["id"]=="beyaz" else (255,215,0))
        surf.blit(coin, (config.SCREEN_WIDTH-160, 18))
        hint = self.font_small.render("←→ Kategori  |  ↑↓/W-S Kaydır  |  ENTER Satın Al/Kuşan  |  ESC Menu", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 46))
        tabs = ["SAPKA","CANTA","GOZLUK","BASTON","SİLAH"]
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
        _, key = self.current_shop_list()
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
            # FAZ5: purchase flash
            if item["id"] in getattr(self, '_shop_flash', {}) and self._shop_flash[item["id"]]>0:
                _a = int(120 * min(1, self._shop_flash[item["id"]]/0.6))
                gfx.draw_glow(surf, r.center, 18, (80,220,120), _a)
                pygame.draw.rect(surf, (80,220,120), r, width=4, border_radius=11)
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
            # FAZ6: weapon owned check
            if key == "weapon":
                owned=item["id"] in self.save.get("owned_weapons", ["fist"])
                using=(self.save.get("equipped_weapon","fist")==item["id"])
            else:
                owned=item["id"] in self.save["owned_items"]
                using=False
                for k,sk in (("hat","selected_hat"),("bag","selected_bag"),("glasses","selected_glasses"),("cane","selected_cane")):
                    if item["id"] in config.SHOP_ITEMS[k] and self.save.get(sk)==item["id"]:
                        using=True; break
            if owned:
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
        gfx.draw_vignette(surf, intensity=0.13 if theme["id"]=="beyaz" else 0.22)
        title=self.font_big.render("KARAKTERLER", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint=self.font_small.render("Yön: Seç  |  ENTER: Seç  |  ESC: Menü", True, theme["hud"])
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
            # FAZ7: subtle idle bob for preview
            _bob = int(math.sin(pygame.time.get_ticks()*0.002 + idx*0.7)*1.2) if unlocked else 0
            preview_r=pygame.Rect(r.x+14, r.y+14+_bob, 52, 52)
            pygame.draw.rect(surf, ch["color"], preview_r, border_radius=8)
            pygame.draw.rect(surf, (0,0,0), preview_r, width=2, border_radius=8)
            pygame.draw.circle(surf, ch["accent"], (preview_r.right-10, preview_r.bottom-10), 7)
            # kafa ikonu (with same bob)
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
        # FAZ11: karakter lore paneli (seçili karakter)
        try:
            _ch = config.CHARACTERS[self.char_index] if 0 <= self.char_index < len(config.CHARACTERS) else None
            if _ch:
                _lore = config.CHARACTER_LORE.get(_ch["id"], "")
                if _lore:
                    _lp = pygame.Rect(80, config.SCREEN_HEIGHT-52, config.SCREEN_WIDTH-160, 36)
                    gfx.draw_soft_shadow(surf, _lp, radius=10, alpha=18)
                    gfx.glass_panel(surf, _lp, fill=(255,255,255,200) if theme["id"]=="beyaz" else (30,30,36,200), border=(0,0,0,80), radius=8)
                    _lt = self.font_small.render(_lore, True, (30,30,34) if theme["id"]=="beyaz" else (230,230,240))
                    surf.blit(_lt, (_lp.centerx - _lt.get_width()//2, _lp.centery - _lt.get_height()//2))
        except: pass

    def draw_inventory(self, surf, theme):
        surf.fill(theme["bg"])
        gfx.draw_vignette(surf, intensity=0.13 if theme["id"]=="beyaz" else 0.22)
        title=self.font_big.render("ENVANTER", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint=self.font_small.render("←→ Kategori  |  ↑↓/W-S Kaydır  |  ENTER Kuşan/Çıkar  |  ESC Menü", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 44))
        tabs=["SAPKA","CANTA","GOZLUK","BASTON","SİLAH"]
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
        key=["hat","bag","glasses","cane","weapon"][self.inv_tab]
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
            # FAZ6: weapon sel_key handling
            if key == "weapon":
                sel_key = "equipped_weapon"
            else:
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
                if key == "weapon":
                    using=self.save.get("equipped_weapon","fist")==item["id"]
                else:
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
        gfx.draw_vignette(surf, intensity=0.13 if theme["id"]=="beyaz" else 0.22)
        title=self.font_big.render("TEMALAR", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint=self.font_small.render("Yön: Seç  |  ENTER: Uygula  |  ESC: Menu", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 42))
        cur_txt=self.font_small.render(f"Seçili: {theme['name']}", True, theme["hud"])
        surf.blit(cur_txt, (config.SCREEN_WIDTH//2 - cur_txt.get_width()//2, 62))
        cols=4; card_w,card_h=190,110; gap_x,gap_y=18,16
        start_x=config.SCREEN_WIDTH//2 - (cols*card_w+(cols-1)*gap_x)//2; start_y=88
        # scroll: cursor satırı görünür tut (28 tema için)
        cur_row = (self.theme_index // cols) if getattr(self,'theme_index',0) else 0
        total_rows = (len(config.THEMES) + cols - 1)//cols
        vis_rows = 4
        first_row = max(0, min(cur_row - 1, max(0, total_rows - vis_rows)))
        y_off = first_row * (card_h + gap_y)
        for idx,t in enumerate(config.THEMES):
            row=idx//cols; col=idx%cols
            x=start_x+col*(card_w+gap_x); y=start_y+row*(card_h+gap_y) - y_off
            if y + card_h < start_y or y > config.SCREEN_HEIGHT - 10:
                continue
            r=pygame.Rect(x,y,card_w,card_h)
            is_cur=t["id"]==self.save.get("theme","beyaz")
            is_cursor=idx==self.theme_index
            is_owned=t["id"] in self._owned_theme_ids()
            gfx.draw_soft_shadow(surf, r, radius=10, alpha=22 if is_cursor or is_cur else 14)
            pygame.draw.rect(surf, t["bg"] if is_owned else (110,110,115), r, border_radius=11)
            pygame.draw.rect(surf, (0,0,0,130), r, width=2, border_radius=11)
            if is_cur:
                gfx.draw_glow(surf, r.center, 16, (0,180,0), 18)
                pygame.draw.rect(surf,(0,188,72), r, width=4, border_radius=11)
            if is_cursor:
                _hg = t.get("accent", (255,215,0))
                _hg3 = (_hg[0],_hg[1],_hg[2]) if isinstance(_hg,(list,tuple)) and len(_hg)>=3 else (255,215,0)
                gfx.draw_glow(surf, r.center, 14, _hg3, 18)
                pygame.draw.rect(surf,_hg3, r, width=3, border_radius=11)
            pygame.draw.line(surf,(255,255,255,42),(r.x+8,r.y+5),(r.right-8,r.y+5),1)
            btn_preview=pygame.Rect(r.x+12, r.y+34, r.width-24, 24)
            pygame.draw.rect(surf, t["button"] if is_owned else (130,130,135), btn_preview, border_radius=6)
            pygame.draw.rect(surf,(0,0,0), btn_preview, width=1, border_radius=6)
            name=self.font_small.render(t["name"], True, t["ui_text"] if is_owned else (90,90,95))
            surf.blit(name, (r.centerx - name.get_width()//2, r.y+10))
            btn_txt=self.font_tiny.render("Buton Önizleme", True, (0,0,0) if t["id"] not in ("siyah","kirmizi_siyah","siyah_mavi","mor_mavi") else (255,255,255))
            surf.blit(btn_txt, (btn_preview.centerx - btn_txt.get_width()//2, btn_preview.centery - btn_txt.get_height()//2))
            # atmosfer preview noktaları: accent / glow / particle
            try:
                _ac = t.get("accent", t["button"]); _gl = t.get("glow", t["button"]); _pa = t.get("particle", t["button"])
                _ac3 = (_ac[0],_ac[1],_ac[2]) if isinstance(_ac,(list,tuple)) and len(_ac)>=3 else (200,200,200)
                _gl3 = (_gl[0],_gl[1],_gl[2]) if isinstance(_gl,(list,tuple)) and len(_gl)>=3 else (200,200,200)
                _pa3 = (_pa[0],_pa[1],_pa[2]) if isinstance(_pa,(list,tuple)) and len(_pa)>=3 else (200,200,200)
                for dx, cc in ((-14,_ac3),(0,_gl3),(14,_pa3)):
                    pygame.draw.circle(surf, cc, (r.centerx+dx, r.y+92), 5)
                    pygame.draw.circle(surf, (0,0,0), (r.centerx+dx, r.y+92), 5, 1)
            except: pass
            status=self.font_tiny.render("✓ SEÇİLİ" if is_cur else ("🔒 KİLİTLİ" if not is_owned else "ENTER ile Seç"), True, (0,120,0) if is_cur else (150,40,40) if not is_owned else (60,60,60))
            surf.blit(status, (r.centerx - status.get_width()//2, r.y+70))
            if is_cur:
                check=self.font_med.render("✓", True, (0,150,0))
                surf.blit(check, (r.right-18, r.y+6))
        # alt preview: hover/cursor temasının atmosferi (bg/accent/glow/particle)
        try:
            hov = config.THEMES[self.theme_index] if 0 <= self.theme_index < len(config.THEMES) else theme
            bar = pygame.Rect(config.SCREEN_WIDTH//2 - 220, config.SCREEN_HEIGHT - 44, 440, 30)
            pygame.draw.rect(surf, hov.get("bg", (40,40,44)), bar, border_radius=8)
            pygame.draw.rect(surf, (0,0,0,120), bar, width=1, border_radius=8)
            _ac = hov.get("accent", (255,215,0)); _gl = hov.get("glow", (255,215,0)); _pa = hov.get("particle", (200,200,200))
            _ac3 = (_ac[0],_ac[1],_ac[2]) if isinstance(_ac,(list,tuple)) and len(_ac)>=3 else (255,215,0)
            _gl3 = (_gl[0],_gl[1],_gl[2]) if isinstance(_gl,(list,tuple)) and len(_gl)>=3 else (255,215,0)
            _pa3 = (_pa[0],_pa[1],_pa[2]) if isinstance(_pa,(list,tuple)) and len(_pa)>=3 else (200,200,200)
            nm = self.font_small.render(f"Önizleme: {hov.get('name','')}", True, hov.get("ui_text",(255,255,255)))
            surf.blit(nm, (bar.x+12, bar.centery - nm.get_height()//2))
            for i, cc in enumerate((_ac3, _gl3, _pa3)):
                pygame.draw.circle(surf, cc, (bar.right-60+i*20, bar.centery), 7)
                pygame.draw.circle(surf, (0,0,0), (bar.right-60+i*20, bar.centery), 7, 1)
        except: pass

    # ---------- FAZ13: Settings helpers (safe display + layout) ----------
    def _settings_layout(self):
        """FAZ13: settings card + row rects — draw ve mouse icin tek kaynak."""
        card = pygame.Rect(40, 68, config.SCREEN_WIDTH-80, 530)
        # slider rows: 0,1,2
        s_y0 = card.y + 18
        s_step = 56
        bars = []
        for i in range(3):
            y = s_y0 + i*s_step
            bar = pygame.Rect(card.x+210, y+18, 380, 14)
            bars.append((y, bar))
        # toggle rows: 3 tutorial, 4 fullscreen, 5 fps, 6 resolution, 7 controls
        t_y = s_y0 + 3*s_step + 12  # tutorial
        rows = {}
        rows[3] = pygame.Rect(card.x+14, t_y, card.width-28, 36)
        rows[4] = pygame.Rect(card.x+14, t_y+44, card.width-28, 36)
        rows[5] = pygame.Rect(card.x+14, t_y+88, card.width-28, 36)
        rows[6] = pygame.Rect(card.x+14, t_y+132, card.width-28, 36)
        rows[7] = pygame.Rect(card.x+14, t_y+176, card.width-28, 36)
        # geri button
        back = pygame.Rect(card.centerx-90, card.bottom-38, 180, 34)
        return {"card": card, "bars": bars, "rows": rows, "back": back, "t_y": t_y}

    def _try_apply_display(self, fullscreen=None, resolution=None):
        """FAZ13: fullscreen/resolution degisimini guvenli uygula. Basarisizsa fallback.
        Main loop'un screen referansini tazelemesi icin _display_changed bayragi ayarlar."""
        try:
            s = self.save.get("settings", {})
            fs = bool(s.get("fullscreen", False)) if fullscreen is None else bool(fullscreen)
            res = str(s.get("resolution", "900x700")) if resolution is None else str(resolution)
            # Android'de PC display ayarlari uygulanmaz (letterbox korunur)
            try:
                from android_controls import is_android as _is_and
                if _is_and():
                    return True
            except:
                pass
            if fs:
                # fullscreen: desktop native kullan (0,0) en guvenli
                try:
                    pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                except:
                    # fallback: istenen cozunurluk ile fullscreen dene
                    try:
                        w, h = map(int, res.split("x"))
                        pygame.display.set_mode((w, h), pygame.FULLSCREEN)
                    except:
                        pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.FULLSCREEN)
            else:
                # windowed: istenen cozunurluk, basarisizsa 900x700
                try:
                    w, h = map(int, res.split("x"))
                    if (w, h) not in [(900,700),(1280,720),(1600,900),(1920,1080)]:
                        w, h = 900, 700
                    pygame.display.set_mode((w, h))
                except:
                    pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            self._display_changed = True
            return True
        except Exception as e:
            print(f"[Display] apply fail: {e}")
            try:
                pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
                self._display_changed = True
            except:
                pass
            return False

    def _fps_label(self, v):
        try:
            iv = int(v)
        except:
            iv = 60
        if iv == 0:
            return "SINIRSIZ"
        return f"{iv} FPS"

    def _resolution_label(self, r):
        return str(r)

    def draw_settings(self, surf, theme):
        surf.fill(theme["bg"])
        title=self.font_big.render("AYARLAR", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 14))
        hint=self.font_small.render("↑↓ Seç  |  ←→ Ayarla  |  ENTER Onayla  |  ESC Geri  |  Mouse ile sürükle", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 42))
        lay = self._settings_layout()
        card = lay["card"]
        # glass card (larger, holds 9 rows)
        gfx.draw_soft_shadow(surf, card, radius=16, alpha=32)
        gfx.glass_panel(surf, card, fill=(255,255,255,242) if theme["id"]=="beyaz" else (38,38,44,242), border=(0,0,0,110), radius=14)
        pygame.draw.rect(surf, (255,215,0), pygame.Rect(card.x, card.y, card.width, 6), border_radius=4)
        s = self.save["settings"]
        mx,my = pygame.mouse.get_pos()
        # --- sliders 0..2 ---
        labels = [("MASTER SES", s.get("master",0.7), "Genel ses seviyesi"), ("MÜZİK", s.get("music",0.5), "Arka plan müziği"), ("EFEKTLER", s.get("sfx",0.8), "Coin / zıplama / ölüm efektleri")]
        bars = lay["bars"]
        for i,(label, val, desc) in enumerate(labels):
            y, bar = bars[i]
            is_sel = self.settings_index == i
            hover = bar.collidepoint(mx,my) or pygame.Rect(card.x+14, y-4, card.width-28, 36).collidepoint(mx,my)
            if is_sel:
                pygame.draw.rect(surf, (255,215,0, 28), pygame.Rect(card.x+14, y-4, card.width-28, 36), border_radius=8)
            # selection border for row
            if is_sel:
                pygame.draw.rect(surf, (255,215,0), pygame.Rect(card.x+14, y-4, card.width-28, 36), width=2, border_radius=8)
            elif hover:
                pygame.draw.rect(surf, (0,0,0,18), pygame.Rect(card.x+14, y-4, card.width-28, 36), border_radius=8)
            txt = self.font_med.render(label, True, (0,0,0) if is_sel else (30,30,34) if theme["id"]=="beyaz" else (230,230,240))
            surf.blit(txt, (card.x+18, y))
            # bar bg
            pygame.draw.rect(surf, (220,220,220), bar, border_radius=7)
            fill = pygame.Rect(bar.x, bar.y, int(bar.width*max(0,min(1,val))), bar.height)
            col = (255,215,0) if is_sel else (120,180,255) if i==1 else (100,200,100)
            pygame.draw.rect(surf, col, fill, border_radius=7)
            pygame.draw.rect(surf, (0,0,0), bar, width=1, border_radius=7)
            kx = bar.x + int(bar.width*max(0,min(1,val)))
            pygame.draw.circle(surf, (0,0,0), (kx, bar.centery), 9)
            pygame.draw.circle(surf, (255,255,255), (kx, bar.centery), 6)
            if is_sel:
                pygame.draw.rect(surf, (255,215,0), pygame.Rect(bar.x-2, bar.y-2, bar.width+4, bar.height+4), width=2, border_radius=8)
            vtxt = self.font_small.render(f"{int(max(0,min(1,val))*100)}%", True, (0,0,0) if theme["id"]=="beyaz" else (30,30,34))
            surf.blit(vtxt, (bar.right+12, bar.y-2))
            d = self.font_tiny.render(desc, True, (100,100,100) if theme["id"]=="beyaz" else (170,170,180))
            surf.blit(d, (card.x+18, y+28))
        # --- toggle rows 3..7 ---
        rows = lay["rows"]
        # 3 TUTORIAL
        y_row = rows[3]
        is_sel = self.settings_index == 3
        hover = y_row.collidepoint(mx,my)
        if is_sel:
            pygame.draw.rect(surf, (255,215,0), y_row, width=2, border_radius=8)
            gfx.draw_glow(surf, y_row.center, 16, (255,215,0), 12)
        elif hover:
            pygame.draw.rect(surf, (0,0,0,14), y_row, border_radius=8)
        tlbl = self.font_med.render("TUTORIAL GÖSTER", True, (0,0,0) if theme["id"]=="beyaz" else (240,240,250))
        surf.blit(tlbl, (y_row.x+12, y_row.centery - tlbl.get_height()//2))
        cb = pygame.Rect(y_row.right-38, y_row.centery-11, 22, 22)
        checked = bool(s.get("show_tutorial", True))
        pygame.draw.rect(surf, (255,255,255), cb, border_radius=4)
        pygame.draw.rect(surf, (0,0,0), cb, width=2, border_radius=4)
        if checked:
            pygame.draw.rect(surf, (0,180,0), pygame.Rect(cb.x+3, cb.y+3, 16, 16), border_radius=3)
            chk = self.font_small.render("✓", True, (255,255,255))
            surf.blit(chk, (cb.centerx - chk.get_width()//2, cb.centery - chk.get_height()//2))
        # 4 FULLSCREEN
        y_row = rows[4]
        is_sel = self.settings_index == 4
        hover = y_row.collidepoint(mx,my)
        if is_sel:
            pygame.draw.rect(surf, (255,215,0), y_row, width=2, border_radius=8)
            gfx.draw_glow(surf, y_row.center, 14, (255,215,0), 10)
        elif hover:
            pygame.draw.rect(surf, (0,0,0,12), y_row, border_radius=8)
        flbl = self.font_med.render("TAM EKRAN", True, (0,0,0) if theme["id"]=="beyaz" else (240,240,250))
        surf.blit(flbl, (y_row.x+12, y_row.centery - flbl.get_height()//2))
        fs_val = bool(s.get("fullscreen", False))
        fs_txt = self.font_small.render("AÇIK" if fs_val else "KAPALI", True, (0,140,0) if fs_val else (160,40,40))
        surf.blit(fs_txt, (y_row.right-88, y_row.centery - fs_txt.get_height()//2))
        # toggle visual
        tog = pygame.Rect(y_row.right-38, y_row.centery-10, 32, 18)
        pygame.draw.rect(surf, (0,180,0) if fs_val else (180,180,180), tog, border_radius=9)
        pygame.draw.rect(surf, (0,0,0), tog, width=1, border_radius=9)
        knob_x = tog.x+5 if not fs_val else tog.right-13
        pygame.draw.circle(surf, (255,255,255), (knob_x+4, tog.centery), 6)
        pygame.draw.circle(surf, (0,0,0), (knob_x+4, tog.centery), 6, 1)
        hint_fs = self.font_tiny.render("F11 ile hızlı aç/kapat", True, (100,100,110) if theme["id"]=="beyaz" else (170,170,180))
        surf.blit(hint_fs, (y_row.x+12, y_row.y+24))
        # 5 FPS
        y_row = rows[5]
        is_sel = self.settings_index == 5
        hover = y_row.collidepoint(mx,my)
        if is_sel:
            pygame.draw.rect(surf, (255,215,0), y_row, width=2, border_radius=8)
        elif hover:
            pygame.draw.rect(surf, (0,0,0,12), y_row, border_radius=8)
        flbl2 = self.font_med.render("FPS LİMİTİ", True, (0,0,0) if theme["id"]=="beyaz" else (240,240,250))
        surf.blit(flbl2, (y_row.x+12, y_row.centery - flbl2.get_height()//2))
        fps_v = int(s.get("fps_limit", 60))
        fps_txt = self.font_small.render(self._fps_label(fps_v), True, (0,0,0) if theme["id"]=="beyaz" else (200,220,255))
        surf.blit(fps_txt, (y_row.right-110, y_row.centery - fps_txt.get_height()//2))
        # arrows
        arr_l = self.font_small.render("◀", True, (80,80,90))
        arr_r = self.font_small.render("▶", True, (80,80,90))
        surf.blit(arr_l, (y_row.right-148, y_row.centery - arr_l.get_height()//2))
        surf.blit(arr_r, (y_row.right-42, y_row.centery - arr_r.get_height()//2))
        hint_fps = self.font_tiny.render("30/60/90/120/Sınırsız — dt bağımsız fizik korunur", True, (100,100,110) if theme["id"]=="beyaz" else (170,170,180))
        surf.blit(hint_fps, (y_row.x+12, y_row.y+24))
        # 6 RESOLUTION
        y_row = rows[6]
        is_sel = self.settings_index == 6
        hover = y_row.collidepoint(mx,my)
        if is_sel:
            pygame.draw.rect(surf, (255,215,0), y_row, width=2, border_radius=8)
        elif hover:
            pygame.draw.rect(surf, (0,0,0,12), y_row, border_radius=8)
        rlbl = self.font_med.render("ÇÖZÜNÜRLÜK", True, (0,0,0) if theme["id"]=="beyaz" else (240,240,250))
        surf.blit(rlbl, (y_row.x+12, y_row.centery - rlbl.get_height()//2))
        res_v = str(s.get("resolution","900x700"))
        res_txt = self.font_small.render(res_v, True, (0,0,0) if theme["id"]=="beyaz" else (200,220,255))
        surf.blit(res_txt, (y_row.right-116, y_row.centery - res_txt.get_height()//2))
        surf.blit(arr_l, (y_row.right-154, y_row.centery - arr_l.get_height()//2))
        surf.blit(arr_r, (y_row.right-42, y_row.centery - arr_r.get_height()//2))
        hint_res = self.font_tiny.render("Pencere boyutu — tam ekranda etkisiz, güvenli fallback 900x700", True, (100,100,110) if theme["id"]=="beyaz" else (170,170,180))
        surf.blit(hint_res, (y_row.x+12, y_row.y+24))
        # 7 CONTROLS
        y_row = rows[7]
        is_sel = self.settings_index == 7
        hover = y_row.collidepoint(mx,my)
        if is_sel:
            pygame.draw.rect(surf, (255,215,0), y_row, width=2, border_radius=8)
            gfx.draw_glow(surf, y_row.center, 12, (255,215,0), 10)
        elif hover:
            pygame.draw.rect(surf, (0,0,0,12), y_row, border_radius=8)
        clbl = self.font_med.render("KONTROLLER", True, (0,0,0) if theme["id"]=="beyaz" else (240,240,250))
        surf.blit(clbl, (y_row.x+12, y_row.centery - clbl.get_height()//2))
        cinfo = self.font_tiny.render("←→ Hareket  ↑ Zıpla  ↓ Hızlı Düş  SPACE Duraklat  ESC Menü  F/J Saldır  H Yardım  M Marş  F11 Tam Ekran", True, (60,60,70) if theme["id"]=="beyaz" else (200,200,210))
        # wrap if needed
        if cinfo.get_width() > y_row.width - 120:
            # split
            surf.blit(self.font_tiny.render("←→ Hareket  ↑ Zıpla  ↓ Hızlı Düş  SPACE Pause  ESC Menü", True, (60,60,70) if theme["id"]=="beyaz" else (200,200,210)), (y_row.x+12, y_row.y+18))
            surf.blit(self.font_tiny.render("F/J Saldır  H Yardım  M Marş  F11 Tam Ekran", True, (60,60,70) if theme["id"]=="beyaz" else (200,200,210)), (y_row.x+12, y_row.y+28))
        else:
            surf.blit(cinfo, (y_row.x+110, y_row.centery - cinfo.get_height()//2))
        # geri button
        back = lay["back"]
        is_back_sel = self.settings_index == 8
        hover_b = back.collidepoint(mx,my)
        col = (255,215,0) if is_back_sel or hover_b else (230,230,230) if theme["id"]=="beyaz" else (60,60,66)
        gfx.draw_soft_shadow(surf, back, radius=10, alpha=22 if is_back_sel or hover_b else 14)
        pygame.draw.rect(surf, col, back, border_radius=10)
        pygame.draw.rect(surf, (0,0,0), back, width=2, border_radius=10)
        if is_back_sel:
            pygame.draw.rect(surf, (255,215,0), back, width=3, border_radius=10)
            gfx.draw_glow(surf, back.center, 14, (255,215,0), 16)
        btxt = self.font_med.render("GERİ (ESC)", True, (0,0,0) if col==(255,215,0) or theme["id"]=="beyaz" else (255,255,255))
        surf.blit(btxt, (back.centerx - btxt.get_width()//2, back.centery - btxt.get_height()//2))
        # alt bilgi
        info = self.font_tiny.render("Ayarlar save.json'a kaydedilir — eksik dosya olursa varsayılana dönülür. 4GB RAM: particle cap + cache sınırlı.", True, theme["hud"])
        surf.blit(info, (config.SCREEN_WIDTH//2 - info.get_width()//2, config.SCREEN_HEIGHT-14))

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
        # FAZ11: seçili bölüm lore paneli
        try:
            sel = config.LEVELS[self.levels_index] if 0 <= self.levels_index < len(config.LEVELS) else None
            if sel:
                lvl = sel["level"]
                unlocked = lvl in self.save.get("unlocked_levels",[1])
                lore = config.LEVEL_LORE.get(lvl, {"title": sel["name"], "text": "", "detail": ""})
                panel_lore = pygame.Rect(80, config.SCREEN_HEIGHT-78, config.SCREEN_WIDTH-160, 64)
                gfx.draw_soft_shadow(surf, panel_lore, radius=12, alpha=22)
                gfx.glass_panel(surf, panel_lore, fill=(255,255,255,210) if theme["id"]=="beyaz" else (30,30,36,210), border=(0,0,0,90), radius=10)
                if not unlocked:
                    txt = self.font_small.render("Henüz ulaşılmadı. Önce önceki bölümü tamamla.", True, (150,40,40) if theme["id"]=="beyaz" else (255,120,120))
                    surf.blit(txt, (panel_lore.centerx - txt.get_width()//2, panel_lore.centery - txt.get_height()//2))
                else:
                    t1 = self.font_small.render(f"{lore['title']}: {lore['text']}", True, (20,20,24) if theme["id"]=="beyaz" else (240,240,250))
                    # wrap if too long
                    if t1.get_width() > panel_lore.width-20:
                        # split
                        words = f"{lore['title']}: {lore['text']}".split(" ")
                        l1=""; l2=""
                        for w in words:
                            test = (l1+" "+w).strip()
                            if self.font_small.size(test)[0] < panel_lore.width-20:
                                l1=test
                            else:
                                l2+=w+" "
                        surf.blit(self.font_small.render(l1.strip(), True, (20,20,24) if theme["id"]=="beyaz" else (240,240,250)), (panel_lore.x+12, panel_lore.y+10))
                        surf.blit(self.font_tiny.render(l2.strip(), True, (80,80,90) if theme["id"]=="beyaz" else (180,180,190)), (panel_lore.x+12, panel_lore.y+32))
                        det = self.font_tiny.render(lore.get("detail",""), True, (120,120,130) if theme["id"]=="beyaz" else (170,170,180))
                        surf.blit(det, (panel_lore.right - det.get_width() -12, panel_lore.bottom-18))
                    else:
                        surf.blit(t1, (panel_lore.centerx - t1.get_width()//2, panel_lore.y+12))
                        det = self.font_tiny.render(lore.get("detail",""), True, (120,120,130) if theme["id"]=="beyaz" else (170,170,180))
                        surf.blit(det, (panel_lore.centerx - det.get_width()//2, panel_lore.y+32))
        except: pass

    def draw_stats(self, surf, theme):
        surf.fill(theme["bg"])
        gfx.draw_vignette(surf, intensity=0.18)
        title=self.font_big.render("İSTATİSTİKLER", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 18))
        hint=self.font_small.render("ESC ile dön", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 48))
        stats=self.save.get("statistics",{})
        # panel
        panel=pygame.Rect(80, 80, config.SCREEN_WIDTH-160, 460)
        gfx.draw_soft_shadow(surf, panel, radius=18, alpha=42)
        gfx.glass_panel(surf, panel, fill=(255,255,255,242) if theme["id"]=="beyaz" else (38,38,44,242), border=(0,0,0,110), radius=14)
        # rows
        rows=[
            ("Toplam Coin", str(self.save.get("total_coins",0))),
            ("Bölüm", f"{len(self.save.get('completed_levels',[]))} / {len(config.LEVELS)}"),
            ("Yıldız", str(sum(self.save.get("level_stars",{}).values()))),
            ("En Yüksek Combo", f"x{stats.get('max_combo',0)}"),
            ("Ölüm", str(stats.get("total_deaths",0))),
            ("Finish", str(stats.get("levels_completed",0))),
            ("Oynama Süresi", f"{int(stats.get('total_play_time',0)//60)} dk"),
            ("En İyi Mesafe", f"{self.save.get('best_distance',0):.1f} m"),
            ("Açılan Karakter", f"{len(self.save.get('unlocked_characters',[]))} / {len(config.CHARACTERS)}"),
            ("Açılan Eşya", f"{len(self.save.get('owned_items',[]))} / {sum(len(v) for v in config.SHOP_ITEMS.values())}"),
        ]
        y=panel.y+18
        for label, val in rows:
            lbl=self.font_med.render(label, True, (30,30,34) if theme["id"]=="beyaz" else (230,230,240))
            surf.blit(lbl, (panel.x+22, y))
            vsurf=self.font_med.render(val, True, (0,120,60) if theme["id"]=="beyaz" else (120,220,140))
            surf.blit(vsurf, (panel.right-22 - vsurf.get_width(), y))
            y+=38
            pygame.draw.line(surf, (0,0,0,14), (panel.x+18, y-6), (panel.right-18, y-6), 1)
        # back button
        back=pygame.Rect(config.SCREEN_WIDTH//2-90, config.SCREEN_HEIGHT-60, 180, 36)
        hover=back.collidepoint(pygame.mouse.get_pos())
        col=(255,215,0) if hover else (230,230,230)
        gfx.draw_soft_shadow(surf, back, radius=10, alpha=18 if hover else 12)
        pygame.draw.rect(surf, col, back, border_radius=10)
        pygame.draw.rect(surf, (0,0,0,120), back, width=2, border_radius=10)
        txt=self.font_med.render("GERİ", True, (0,0,0))
        surf.blit(txt, (back.centerx - txt.get_width()//2, back.centery - txt.get_height()//2))

    def draw_achievements(self, surf, theme):
        surf.fill(theme["bg"])
        gfx.draw_vignette(surf, intensity=0.18)
        title=self.font_big.render("BAŞARIMLAR", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 18))
        hint=self.font_small.render("ESC ile dön", True, theme["hud"])
        surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, 48))
        ach=self.save.get("achievements",{})
        # definition (id, name, desc)
        defs=[
            ("first_fall","İLK ADIM","İlk bölümü tamamla"),
            ("deep10","KAÇIŞ","10 bölüm tamamla"),
            ("final","ZİRVE","23 bölüm tamamla"),
            ("combo6","KOMBO USTASI","Combo x6"),
            ("coin100","HAZİNE AVCISI","100 coin topla"),
            ("deep10b","YÜKSELİŞ","5 bölüm tamamla"),
            ("collector","KOLEKSİYONCU","10 eşya aç"),
            ("full_gear","TAM DONANIM","20 eşya aç"),
        ]
        panel=pygame.Rect(80, 80, config.SCREEN_WIDTH-160, 460)
        gfx.draw_soft_shadow(surf, panel, radius=18, alpha=42)
        gfx.glass_panel(surf, panel, fill=(255,255,255,242) if theme["id"]=="beyaz" else (38,38,44,242), border=(0,0,0,110), radius=14)
        y=panel.y+16
        for aid, name, desc in defs:
            done = bool(ach.get(aid))
            # icon
            icon_col=(255,215,0) if done else (180,180,180)
            pygame.draw.circle(surf, icon_col, (panel.x+30, y+14), 12)
            pygame.draw.circle(surf, (0,0,0,120), (panel.x+30, y+14), 12, 1)
            if done:
                gfx.draw_glow(surf, (panel.x+30, y+14), 10, (255,215,0), 14)
                chk=self.font_med.render("✓", True, (0,120,0))
                surf.blit(chk, (panel.x+30 - chk.get_width()//2, y+14 - chk.get_height()//2))
            else:
                lk=self.font_small.render("?", True, (90,90,90))
                surf.blit(lk, (panel.x+30 - lk.get_width()//2, y+14 - lk.get_height()//2))
            nsurf=self.font_med.render(name, True, (20,20,24) if theme["id"]=="beyaz" else (240,240,250))
            surf.blit(nsurf, (panel.x+60, y+2))
            dsurf=self.font_tiny.render(desc, True, (90,90,96) if theme["id"]=="beyaz" else (180,180,190))
            surf.blit(dsurf, (panel.x+60, y+22))
            y+=44
            pygame.draw.line(surf, (0,0,0,10), (panel.x+16, y-6), (panel.right-16, y-6), 1)
            if y>panel.bottom-20:
                break
        back=pygame.Rect(config.SCREEN_WIDTH//2-90, config.SCREEN_HEIGHT-60, 180, 36)
        hover=back.collidepoint(pygame.mouse.get_pos())
        col=(255,215,0) if hover else (230,230,230)
        gfx.draw_soft_shadow(surf, back, radius=10, alpha=18 if hover else 12)
        pygame.draw.rect(surf, col, back, border_radius=10)
        pygame.draw.rect(surf, (0,0,0,120), back, width=2, border_radius=10)
        txt=self.font_med.render("GERİ", True, (0,0,0))
        surf.blit(txt, (back.centerx - txt.get_width()//2, back.centery - txt.get_height()//2))

    def draw_lore(self, surf, theme):
        surf.fill(theme["bg"])
        gfx.draw_vignette(surf, intensity=0.20)
        title=self.font_big.render("HİKAYE", True, theme["hud"])
        surf.blit(title, (config.SCREEN_WIDTH//2 - title.get_width()//2, 18))
        sub=self.font_small.render("FREEFALL'ın düşüşü", True, theme["hud"])
        surf.blit(sub, (config.SCREEN_WIDTH//2 - sub.get_width()//2, 48))
        # genel hikaye
        story=[
            "Bir adım attın. Zemin kayboldu.",
            "Şimdi sadece düşüyorsun.",
            "Her katman farklı bir dünya.",
            "Aşağı indikçe dünya daha garip hale geliyor.",
            "Monster hep arkanda. Neden takip ediyor?",
            f"Sembol {config.REPEATING_SYMBOL}  —  ilk HAVA'da, son FINAL'da.",
        ]
        panel=pygame.Rect(70, 80, config.SCREEN_WIDTH-140, 420)
        gfx.draw_soft_shadow(surf, panel, radius=16, alpha=32)
        gfx.glass_panel(surf, panel, fill=(255,255,255,230) if theme["id"]=="beyaz" else (30,30,36,230), border=(0,0,0,90), radius=12)
        y=panel.y+16
        for line in story:
            txt=self.font_small.render(line, True, (30,30,34) if theme["id"]=="beyaz" else (230,230,240))
            surf.blit(txt, (panel.centerx - txt.get_width()//2, y))
            y+=28
        # monster lore
        y+=10
        mlbl=self.font_med.render("MONSTER", True, (160,30,30) if theme["id"]=="beyaz" else (255,120,120))
        surf.blit(mlbl, (panel.centerx - mlbl.get_width()//2, y))
        y+=28
        mtxt=self.font_small.render(config.MONSTER_LORE, True, (60,60,70) if theme["id"]=="beyaz" else (200,200,210))
        surf.blit(mtxt, (panel.centerx - mtxt.get_width()//2, y))
        y+=40
        # 23 bölüme dair küçük ipucu
        tip=self.font_tiny.render("BÖLÜMLER ekranında her bölümün kısa hikayesini görebilirsin. Sembol ◊'yı takip et.", True, (90,90,100) if theme["id"]=="beyaz" else (170,170,180))
        surf.blit(tip, (panel.centerx - tip.get_width()//2, panel.bottom-20))
        back=pygame.Rect(config.SCREEN_WIDTH//2-90, config.SCREEN_HEIGHT-60, 180, 36)
        hover=back.collidepoint(pygame.mouse.get_pos())
        col=(255,215,0) if hover else (230,230,230)
        gfx.draw_soft_shadow(surf, back, radius=10, alpha=18 if hover else 12)
        pygame.draw.rect(surf, col, back, border_radius=10)
        pygame.draw.rect(surf, (0,0,0,120), back, width=2, border_radius=10)
        txt=self.font_med.render("GERİ", True, (0,0,0))
        surf.blit(txt, (back.centerx - txt.get_width()//2, back.centery - txt.get_height()//2))

    def draw_level_complete(self, surf, theme):
        overlay=pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0, 168))
        surf.blit(overlay, (0,0))
        gfx.draw_vignette(surf, intensity=0.22)
        data=self.level_complete_data or {}
        lvl=data.get("level",1); name=data.get("name",""); stars=data.get("stars",1)
        is_final=data.get("is_final", False)
        # FAZ10: panel scale-in (0.32s)
        _t = min(1.0, getattr(self, 'level_complete_timer', 0)/0.32)
        _scale = 0.88 + 0.12*_t
        _alpha = int(242*_t)
        box_w, box_h = 440, 240
        # scale box around center
        _bw, _bh = int(box_w*_scale), int(box_h*_scale)
        box=pygame.Rect(config.SCREEN_WIDTH//2-_bw//2, config.SCREEN_HEIGHT//2-120 + (box_h-_bh)//2, _bw, _bh)
        # use alpha for glass
        gfx.draw_soft_shadow(surf, box, radius=22, alpha=int(64*_t))
        # temporary surface for scale alpha
        _panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        gfx.glass_panel(_panel, pygame.Rect(0,0,box_w,box_h), fill=(255,255,255,_alpha), border=(0,0,0,110), radius=16)
        surf.blit(pygame.transform.smoothscale(_panel, (_bw,_bh)), box.topleft)
        # üst şerit
        pygame.draw.rect(surf, (0,186,70) if not is_final else (90,40,180), pygame.Rect(box.x, box.y, box.width, 6), border_radius=4)
        title=self.font_big.render("BÖLÜM TAMAMLANDI!" if not is_final else "TÜM BÖLÜMLER BİTTİ!", True, (18,18,20))
        title.set_alpha(int(255*_t))
        surf.blit(title, (box.centerx - title.get_width()//2, box.y+16))
        sub=self.font_med.render(f"BÖLÜM {lvl} — {name}", True, (60,60,70))
        sub.set_alpha(int(255*_t))
        surf.blit(sub, (box.centerx - sub.get_width()//2, box.y+48))
        # yıldızlar sequential: her 0.12s bir yıldız
        for s in range(3):
            if _t < 0.18 + s*0.13: continue
            sx=box.centerx -28 + s*28; sy=box.y+82
            col=(255,215,0) if s < stars else (220,220,220)
            # pop scale for earned stars
            _pop = 1.0
            if s < stars:
                _st = max(0, min(1, (_t - (0.18+s*0.13))/0.14))
                _pop = 0.7 + 0.3*_st + 0.08*math.sin(_st*6)
            # draw star with pop
            pts_scale = _pop
            # simple polygon with scale
            _pts = [(sx, sy-10*pts_scale),(sx-4*pts_scale, sy-2*pts_scale),(sx-10*pts_scale, sy),(sx-4*pts_scale, sy+6*pts_scale),(sx, sy+12*pts_scale),(sx+4*pts_scale, sy+6*pts_scale),(sx+10*pts_scale, sy),(sx+4*pts_scale, sy-2*pts_scale)]
            # use precomputed polygon
            pygame.draw.polygon(surf, col, [(sx, sy-10),(sx-4, sy-2),(sx-10, sy),(sx-4, sy+6),(sx, sy+12),(sx+4, sy+6),(sx+10, sy),(sx+4, sy-2)])
            pygame.draw.polygon(surf, (0,0,0), [(sx, sy-10),(sx-4, sy-2),(sx-10, sy),(sx-4, sy+6),(sx, sy+12),(sx+4, sy+6),(sx+10, sy),(sx+4, sy-2)],1)
            if s < stars:
                gfx.draw_glow(surf, (sx, sy+2), int(12*_pop), (255,215,0), int(18*_pop))
        # FAZ5: reward breakdown sequential (0.42s,0.54s,0.66s)
        dist=data.get("distance",0); coins=data.get("coins",0)
        base=data.get("base", coins); combo_b=data.get("combo_bonus",0); risk_b=data.get("risk_bonus",0); near=data.get("near_count",0); earned=data.get("earned", coins)
        y0 = box.y+112
        # coin row (0.42s)
        if _t > 0.42:
            _a1 = int(255*min(1, (_t-0.42)/0.18))
            # coin icon pop
            _pop_c = 1.0 + 0.12*math.sin(max(0,(_t-0.42)/0.12)*3) if _t<0.62 else 1.0
            line1 = f"COIN  +{base}"
            # add small coin icon (circle) before text - just text for now
            stat=self.font_small.render(line1, True, (30,30,34))
            stat.set_alpha(_a1)
            # pop scale via transform
            if _pop_c != 1.0:
                try:
                    stat = pygame.transform.smoothscale(stat, (int(stat.get_width()*_pop_c), int(stat.get_height()*_pop_c)))
                except: pass
            surf.blit(stat, (box.centerx - stat.get_width()//2, y0))
        # combo row (0.54s)
        if combo_b and _t > 0.54:
            _a2 = int(255*min(1, (_t-0.54)/0.16))
            line2 = f"COMBO  +{combo_b}" + (f"  •  NEAR x{near}" if near else "")
            stat2=self.font_small.render(line2, True, (120,80,20))
            stat2.set_alpha(_a2)
            surf.blit(stat2, (box.centerx - stat2.get_width()//2, y0+16))
        # risk row (0.66s)
        if risk_b and _t > 0.66:
            _a3 = int(255*min(1, (_t-0.66)/0.14))
            line3 = f"RISK  +{risk_b}  •  TOPLAM  +{earned}"
            stat3=self.font_small.render(line3, True, (160,40,20))
            stat3.set_alpha(_a3)
            surf.blit(stat3, (box.centerx - stat3.get_width()//2, y0+32 if combo_b else y0+16))
        elif not combo_b and not risk_b and _t > 0.54:
            _a3 = int(255*min(1, (_t-0.54)/0.16))
            line3 = f"TOPLAM  +{earned}"
            stat3=self.font_small.render(line3, True, (30,30,34))
            stat3.set_alpha(_a3)
            surf.blit(stat3, (box.centerx - stat3.get_width()//2, y0+16))
        # total line always at bottom (0.78s)
        if _t > 0.78:
            sub2 = f"Mesafe: {dist:.1f} m  •  Toplam: {self.save.get('total_coins',0)}"
            sub_surf=self.font_tiny.render(sub2, True, (110,110,118))
            sub_surf.set_alpha(int(255*min(1, (_t-0.78)/0.12)))
            surf.blit(sub_surf, (box.centerx - sub_surf.get_width()//2, y0+36 if (combo_b or risk_b) else y0+32))
                # butonlar (0.88s fade-in)
        _btn_a = int(255*min(1, max(0, (_t-0.88)/0.18)))
        if _btn_a <= 0:
            return
        if is_final:
            b1=pygame.Rect(box.x+60, box.bottom-52, 320, 38)
            hover=b1.collidepoint(pygame.mouse.get_pos())
            col=(90,40,180) if hover else (120,60,200)
            # unlock highlight for final is gold
            gfx.draw_soft_shadow(surf, b1, radius=10, alpha=int(22*_btn_a/255))
            # create button surface with alpha
            _b1_surf = pygame.Surface((b1.width,b1.height), pygame.SRCALPHA)
            _b1_surf.fill((*col, _btn_a))
            surf.blit(_b1_surf, b1.topleft)
            pygame.draw.rect(surf, (0,0,0,int(200*_btn_a/255)), b1, width=2, border_radius=10)
            txt=self.font_med.render("FİNALİ İZLE →", True, (255,255,255))
            txt.set_alpha(_btn_a)
            surf.blit(txt, (b1.centerx - txt.get_width()//2, b1.centery - txt.get_height()//2))
        else:
            # check if next level is newly unlocked
            _is_new = (lvl+1) in self.save.get("unlocked_levels",[]) and lvl < len(config.LEVELS)
            b1=pygame.Rect(box.x+20, box.bottom-52, 190, 38)
            b2=pygame.Rect(box.x+230, box.bottom-52, 190, 38)
            mx,my=pygame.mouse.get_pos()
            for b, txt_str in [(b1, "SONRAKİ BÖLÜM"), (b2, "BÖLÜMLER")]:
                hover=b.collidepoint(mx,my)
                base=(0,150,70) if b==b1 else (60,60,70)
                col=(0,180,90) if hover and b==b1 else (80,80,90) if hover else base
                # FAZ10: is_new highlight for next level
                if _is_new and b==b1:
                    col=(0,190,100)
                    gfx.draw_glow(surf, b.center, 14, (255,215,0), int(18*_btn_a/255))
                gfx.draw_soft_shadow(surf, b, radius=10, alpha=int((22 if hover else 14)*_btn_a/255))
                # button surface with alpha
                _bs = pygame.Surface((b.width,b.height), pygame.SRCALPHA)
                _bs.fill((*col, _btn_a))
                surf.blit(_bs, b.topleft)
                pygame.draw.rect(surf, (0,0,0,int(200*_btn_a/255)), b, width=2, border_radius=10)
                if hover:
                    pygame.draw.rect(surf, (255,215,0,int(200*_btn_a/255)), b, width=2, border_radius=10)
                t=self.font_med.render(txt_str, True, (255,255,255))
                t.set_alpha(_btn_a)
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
            self.world.draw(surf, self.camera.y, self.level_info, theme)
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

    def draw_final_cinematic(self, surf, theme):
        # FAZ12: 7 sahne, 19.5s, hafif sinematik
        t = getattr(self, 'final_cinematic_timer', 0)
        surf.fill((6,8,14))
        gfx.draw_vignette(surf, intensity=0.28)
        # slow dim
        dim = int(18 * min(1, t/2.5))
        over = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        over.fill((0,0,0, dim))
        surf.blit(over, (0,0))
        # helper fade
        def _fade(txt, col, y, appear, hold=1.2):
            if t < appear or t > appear+hold+0.4:
                return
            a = 255
            if t < appear+0.3:
                a = int(255 * (t-appear)/0.3)
            elif t > appear+hold:
                a = int(255 * (appear+hold+0.4 - t)/0.4)
            a = max(0, min(255, a))
            s = self.font_med.render(txt, True, col)
            s.set_alpha(a)
            surf.blit(s, (config.SCREEN_WIDTH//2 - s.get_width()//2, y))
        # Scene 1: Oyuncu durur, kamera yavaş aşağı, kararma
        _fade("Sonunda dibe ulaştın.", (255,255,255), config.SCREEN_HEIGHT//2-60, 0.4)
        # Scene 2: Fakat burada hiçbir şey yoktu.
        _fade("Fakat burada hiçbir şey yoktu.", (200,220,255), config.SCREEN_HEIGHT//2-30, 2.2)
        # Scene 2b: symbol appears in different spots
        if 2.8 < t < 4.5:
            for i, (dx, dy) in enumerate([(-160,-80),(120,40),(0,70),(-80,20)]):
                a2 = int(70 * max(0, min(1, (t-(2.8+i*0.2))/0.3)) * max(0, min(1, (4.5 - t)/0.4)))
                if a2<=0: continue
                sym = self.font_small.render(config.REPEATING_SYMBOL, True, (255,255,255))
                sym.set_alpha(a2)
                surf.blit(sym, (config.SCREEN_WIDTH//2 + dx - sym.get_width()//2, config.SCREEN_HEIGHT//2 + dy - sym.get_height()//2))
                gfx.draw_glow(surf, (config.SCREEN_WIDTH//2+dx, config.SCREEN_HEIGHT//2+dy), 10, (255,255,255), int(a2*0.2))
        # Scene 3: Onu daha önce görmüştün.
        _fade("Onu daha önce görmüştün.", (255,215,0), config.SCREEN_HEIGHT//2-20, 5.0)
        _fade("İlk düştüğün yerde.", (255,215,0), config.SCREEN_HEIGHT//2+10, 6.4)
        _fade("Ve her katmanda.", (255,215,0), config.SCREEN_HEIGHT//2+40, 7.8)
        # Scene 4: symbols converge
        if 9.0 < t < 12.0:
            prog = (t-9.0)/3.0
            for i in range(5):
                ang = i*72 + prog*30
                rad = math.radians(ang)
                dist = 80 * (1-prog*0.6)
                x = config.SCREEN_WIDTH//2 + math.cos(rad)*dist
                y = config.SCREEN_HEIGHT//2 + math.sin(rad)*dist*0.5
                a3 = int(90 * (1-prog*0.3))
                sym = self.font_small.render(config.REPEATING_SYMBOL, True, (255,255,255))
                sym.set_alpha(a3)
                surf.blit(sym, (int(x - sym.get_width()//2), int(y - sym.get_height()//2)))
        # Scene 5: Monster silhouette
        if 12.2 < t < 13.8:
            a4 = int(180 * min(1, (t-12.2)/0.4) * min(1, (13.8-t)/0.4))
            # silhouette at center bottom
            mx = config.SCREEN_WIDTH//2
            my = config.SCREEN_HEIGHT//2 + 60
            # simple monster silhouette using theme glow
            gfx.draw_glow(surf, (mx, my), 24, (90,90,110), int(a4*0.15))
            # body as dark rect
            s = pygame.Surface((60,40), pygame.SRCALPHA)
            s.fill((20,20,30, a4))
            surf.blit(s, (mx-30, my-20))
            # eyes
            pygame.draw.circle(surf, (255,60,60, a4), (mx-12, my-8), 3)
            pygame.draw.circle(surf, (255,60,60, a4), (mx+12, my-8), 3)
        # Scene 6: Belki de seni takip eden o değildi.
        _fade("Belki de seni takip eden o değildi.", (220,220,230), config.SCREEN_HEIGHT//2-10, 14.2, hold=1.1)
        _fade("Belki de sen onu takip ediyordun.", (220,220,230), config.SCREEN_HEIGHT//2+20, 15.8, hold=1.1)
        # Scene 7: only symbol remains, then FREEFALL
        if t > 17.0:
            a5 = int(90 * min(1, (t-17.0)/0.6) * min(1, (19.5-t)/0.8)) if t<19.5 else 0
            if a5>0:
                sym = self.font_big.render(config.REPEATING_SYMBOL, True, (255,255,255))
                # scale down slowly
                sc = 1.0 - (t-17.0)*0.04
                sc = max(0.6, sc)
                sw, sh = sym.get_size()
                sym2 = pygame.transform.smoothscale(sym, (int(sw*sc), int(sh*sc)))
                sym2.set_alpha(a5)
                surf.blit(sym2, (config.SCREEN_WIDTH//2 - sym2.get_width()//2, config.SCREEN_HEIGHT//2-10 - sym2.get_height()//2))
        if t > 18.2:
            a6 = int(255 * min(1, (t-18.2)/0.5))
            txt = self.font_huge.render("FREEFALL", True, (255,215,0))
            txt.set_alpha(a6)
            surf.blit(txt, (config.SCREEN_WIDTH//2 - txt.get_width()//2, config.SCREEN_HEIGHT//2+40))
            sub = self.font_small.render("Bu düşüş burada bitmedi.", True, (180,180,190))
            sub.set_alpha(a6)
            surf.blit(sub, (config.SCREEN_WIDTH//2 - sub.get_width()//2, config.SCREEN_HEIGHT//2+90))
        # skip hint
        if t < 19.0:
            hint=self.font_tiny.render("ESC ile geç", True, (120,120,130))
            hint.set_alpha(int(120 * min(1, t/1.0)))
            surf.blit(hint, (config.SCREEN_WIDTH//2 - hint.get_width()//2, config.SCREEN_HEIGHT-24))
        # final buttons after cinematic (handled in update, but draw hint)
        if t > 19.5:
            # will be handled as level_complete, but draw hint
            pass

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
        # nick / id kartı — ayrı gösterim, ????? yok
        nick = self._get_display_nick()
        pid = self._get_display_id()
        guest = self.is_guest()
        card = pygame.Rect(config.SCREEN_WIDTH//2-180, 78, 360, 34)
        pygame.draw.rect(surf, (0,0,0,48), card, border_radius=9)
        pygame.draw.rect(surf, (255,215,0,110), card, width=1, border_radius=9)
        if guest:
            txt = self.font_med.render(f"Oyuncu: {nick}  •  MİSAFİR (ONLINE kilitli)", True, (180,140,60))
        else:
            txt = self.font_med.render(f"Oyuncu: {nick}  •  ID: {pid}", True, (255,255,255) if "siyah" in theme["id"] else (30,30,34))
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
        # kendi nick/id + bağlantı durumu — ayrı, ????? yok
        my_nick = self._get_display_nick()
        my_id = self._get_display_id()
        me_txt = self.font_small.render(f"Oyuncu: {my_nick}  •  ID: {my_id}", True, theme["hud"])
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