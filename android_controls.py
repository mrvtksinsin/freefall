"""
Android dokunmatik kontroller - FREEFALL
Ekranı 3 bölgeye ayırır: sol/sağ hareket, orta üst zıpla, orta alt hızlı düşüş
Ayrıca sol üst pause ve sağ üst menü butonları.
"""
import pygame
import config

# Android mi kontrolü
def is_android():
    try:
        import sys
        return hasattr(sys, 'getandroidapilevel') or 'ANDROID_ARGUMENT' in __import__('os').environ
    except:
        return False

class TouchControls:
    def __init__(self):
        self.left_pressed = False
        self.right_pressed = False
        self.up_pressed = False
        self.down_pressed = False
        self.attack_pressed = False  # FAZ6: combat
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.screen_w = config.SCREEN_WIDTH
        self.screen_h = config.SCREEN_HEIGHT
        self.real_w = config.SCREEN_WIDTH
        self.real_h = config.SCREEN_HEIGHT
        self.offset_x = 0
        self.offset_y = 0
        # swipe scroll için
        self._swipe_start_y = None
        self._swipe_last_y = None
        self._swipe_threshold = 22  # game px, küçük hareketi swipe sayma
        # FAZ15: multitouch + safe area (notch/gesture)
        self.active_touches = {}
        self.safe_margin = 14  # px game, kenardan güvenli mesafe
        # FAZ15: multitouch tracking (finger_id -> gx,gy) — single-touch de calisir
        self.active_touches = {}
        # safe area margin (notch/gesture) — top/bottom/edge
        self.safe_margin = 14  # px game koordinatinda, kenardan uzak tut

    def set_screen_info(self, real_w, real_h, scale_x, scale_y, offset_x=0, offset_y=0):
        self.real_w = real_w
        self.real_h = real_h
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.offset_x = offset_x
        self.offset_y = offset_y

    def _to_game_pos(self, pos):
        """Gerçek ekran posunu oyun 900x700 koordinatına çevir (letterbox offset çıkar)"""
        x, y = pos
        gx = (x - self.offset_x) / self.scale_x if self.scale_x else x
        gy = (y - self.offset_y) / self.scale_y if self.scale_y else y
        return gx, gy

    def handle_touch(self, event, game_state=None, game=None):
        """MOUSE/FINGER eventlerini işle, True dönerse oyun handle_etmemeli"""
        # Swipe scroll sadece shop/inventory/levels için (Android)
        if game_state in ("shop", "inventory", "levels") and game is not None:
            if event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
                x = event.x * self.real_w
                y = event.y * self.real_h
                gx, gy = self._to_game_pos((x, y))
                return self._handle_swipe(gx, gy, event.type, game_state, game)
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                if hasattr(event, 'pos'):
                    gx, gy = self._to_game_pos(event.pos)
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        return self._handle_swipe(gx, gy, pygame.FINGERDOWN, game_state, game)
                    elif event.type == pygame.MOUSEBUTTONUP:
                        self._swipe_start_y = None
                        self._swipe_last_y = None
                        return False
                    elif event.type == pygame.MOUSEMOTION and getattr(event, 'buttons', (0,))[0]:
                        return self._handle_swipe(gx, gy, pygame.FINGERMOTION, game_state, game)

        # FAZ15: multitouch — finger_id ile OR, tek parmak fallback korunur
        if event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            fid = getattr(event, 'finger_id', 0)
            x = event.x * self.real_w
            y = event.y * self.real_h
            gx, gy = self._to_game_pos((x, y))
            if event.type == pygame.FINGERDOWN:
                self.active_touches[fid] = (gx, gy)
            elif event.type == pygame.FINGERMOTION:
                self.active_touches[fid] = (gx, gy)
            elif event.type == pygame.FINGERUP:
                self.active_touches.pop(fid, None)
            if not self.active_touches:
                return self._update_from_pos(gx, gy, event.type)
            return self._update_from_multitouch(event.type)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            if hasattr(event, 'pos'):
                gx, gy = self._to_game_pos(event.pos)
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.active_touches['mouse'] = (gx, gy)
                    return self._update_from_pos(gx, gy, pygame.FINGERDOWN)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.active_touches.pop('mouse', None)
                    self.left_pressed = False
                    self.right_pressed = False
                    self.down_pressed = False
                    self.up_pressed = False
                    self.attack_pressed = False
                    self.active_touches.clear()
                    self._swipe_start_y = None
                    self._swipe_last_y = None
                    return False
                elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
                    self.active_touches['mouse'] = (gx, gy)
                    return self._update_from_pos(gx, gy, pygame.FINGERMOTION)
        return False

    def _update_from_multitouch(self, typ):
        """FAZ15: tum aktif dokunmalarin OR'u — hareket+jump+attack ayni anda."""
        if typ == pygame.FINGERUP and not self.active_touches:
            self.left_pressed = False
            self.right_pressed = False
            self.down_pressed = False
            self.up_pressed = False
            self.attack_pressed = False
            return False
        lp = rp = up = dp = ap = False
        for gx, gy in self.active_touches.values():
            if gx > config.SCREEN_WIDTH - 100 and gy < 120 and gy > 70:
                ap = True
                continue
            if gy < 70:
                continue
            if gy > config.SCREEN_HEIGHT - 140:
                if gx < config.SCREEN_WIDTH * 0.4:
                    lp = True
                elif gx > config.SCREEN_WIDTH * 0.6:
                    rp = True
                else:
                    if gy < config.SCREEN_HEIGHT - 70:
                        up = True
                    else:
                        dp = True
            else:
                if gx < config.SCREEN_WIDTH * 0.33:
                    lp = True
                elif gx > config.SCREEN_WIDTH * 0.66:
                    rp = True
                else:
                    up = True
        self.left_pressed = lp
        self.right_pressed = rp
        self.up_pressed = up
        self.down_pressed = dp
        self.attack_pressed = ap
        return bool(lp or rp or up or dp or ap)

    def _handle_swipe(self, gx, gy, typ, game_state, game):
        """Shop/inventory/levels için dikey swipe scroll"""
        if typ == pygame.FINGERDOWN:
            self._swipe_start_y = gy
            self._swipe_last_y = gy
            return False  # tap'e izin ver
        elif typ == pygame.FINGERUP:
            self._swipe_start_y = None
            self._swipe_last_y = None
            return False
        elif typ == pygame.FINGERMOTION:
            if self._swipe_start_y is None:
                return False
            dy = gy - self._swipe_start_y
            if abs(dy) < self._swipe_threshold:
                return False  # küçük hareketi swipe sayma
            # yeterli hareket -> bir adım scroll
            delta = 1 if dy < 0 else -1  # yukarı swipe -> index +1 (aşağı kaydır)
            if game_state == "shop":
                lst, _ = game.current_shop_list()
                n = len(lst)
                if n:
                    new = max(0, min(n - 1, game.shop_index + delta))
                    if new != game.shop_index:
                        game.shop_index = new
                        try: game._ensure_selection_visible("shop")
                        except: pass
            elif game_state == "inventory":
                tabs = ["hat","bag","glasses","cane"]
                key = tabs[game.inv_tab] if hasattr(game,'inv_tab') else 'hat'
                try:
                    import config as _cfg
                    lst = [it for it in _cfg.SHOP_ITEMS[key] if it["id"] in game.save.get("owned_items",[])]
                except:
                    lst = []
                n = len(lst)
                if n:
                    new = max(0, min(n - 1, game.inv_index + delta))
                    if new != game.inv_index:
                        game.inv_index = new
                        try: game._ensure_selection_visible("inventory")
                        except: pass
            elif game_state == "levels":
                n = len(game.save.get("unlocked_levels",[])) if False else 23  # config.LEVELS length
                try:
                    import config as _cfg2
                    n = len(_cfg2.LEVELS)
                except:
                    n = 23
                new = max(0, min(n - 1, game.levels_index + delta))
                game.levels_index = new
            # bir adım sonrası için start'ı kaydır (sürekli swipe)
            self._swipe_start_y = gy
            self._swipe_last_y = gy
            return True
        return False

    def _update_from_pos(self, gx, gy, typ):
        # FAZ6: attack button (top-right, only in playing) - 88x88 at 800,16
        if typ == pygame.FINGERDOWN:
            # attack area check before other controls (top-right corner)
            if gx > config.SCREEN_WIDTH - 100 and gy < 120 and gy > 70:
                self.attack_pressed = True
                return True
        if typ == pygame.FINGERUP:
            self.left_pressed = False
            self.right_pressed = False
            self.down_pressed = False
            self.up_pressed = False
            self.attack_pressed = False
            return False

        # pause alanı (üst bar) - but attack area already handled above
        if gy < 70:
            # if attack area, already handled; else let UI handle
            if gx > config.SCREEN_WIDTH - 100 and gy < 120:
                return True
            return False  # oyun UI'sine bırak

        # alt kontrol bölgesi
        if gy > config.SCREEN_HEIGHT - 140:
            # sol %40 = sol hareket, sağ %40 = sağ hareket, orta %20 = zıpla/hızlı düş
            if gx < config.SCREEN_WIDTH * 0.4:
                self.left_pressed = True
                self.right_pressed = False
            elif gx > config.SCREEN_WIDTH * 0.6:
                self.right_pressed = True
                self.left_pressed = False
            else:
                # orta: yukarı/aşağı kaydırma
                if gy < config.SCREEN_HEIGHT - 70:
                    self.up_pressed = True
                else:
                    self.down_pressed = True
            return True
        else:
            # oyun alanında: dokunulan yere göre hareket
            if gx < config.SCREEN_WIDTH * 0.33:
                self.left_pressed = True
                self.right_pressed = False
            elif gx > config.SCREEN_WIDTH * 0.66:
                self.right_pressed = True
                self.left_pressed = False
            else:
                # ortaya dokunma = zıpla
                if typ == pygame.FINGERDOWN:
                    self.up_pressed = True
            return True

    def reset_frame(self):
        # tek seferlik up (zıpla) ve attack bir frame sonra bırak
        self.up_pressed = False
        self.attack_pressed = False

    def get_keys(self):
        """pygame.key.get_pressed() benzeri dict döndür"""
        # dummy keys objesi için kullanılacak
        return self

    def __getitem__(self, key):
        if key in (pygame.K_LEFT, pygame.K_a):
            return self.left_pressed
        if key in (pygame.K_RIGHT, pygame.K_d):
            return self.right_pressed
        if key in (pygame.K_UP, pygame.K_w):
            return self.up_pressed
        if key in (pygame.K_DOWN, pygame.K_s):
            return self.down_pressed
        if key == pygame.K_SPACE:
            return False
        return False

    def draw(self, surf, game_state):
        """Alt kontrol overlay çiz - sadece playing'de + FAZ6 attack button"""
        if game_state not in ("playing", "vs_bot", "vs_online"):
            return
        # FAZ6: attack button top-right
        atk_rect = pygame.Rect(config.SCREEN_WIDTH - 92, 16, 76, 76)
        atk_col = (255, 80, 80, 180) if self.attack_pressed else (255, 220, 80, 110)
        # use normal surface for attack button (not bar)
        pygame.draw.rect(surf, (255, 255, 255, 70), atk_rect, border_radius=14)
        pygame.draw.rect(surf, (0,0,0,160), atk_rect, width=2, border_radius=14)
        if self.attack_pressed:
            pygame.draw.rect(surf, (255, 60, 60), atk_rect, width=3, border_radius=14)
        font = pygame.font.SysFont("Arial", 22, bold=True)
        txt = font.render("HIT", True, (0,0,0))
        surf.blit(txt, (atk_rect.centerx - txt.get_width()//2, atk_rect.centery - txt.get_height()//2 - 6))
        small = pygame.font.SysFont("Arial", 9, bold=True)
        t2 = small.render("SALDIR", True, (0,0,0))
        surf.blit(t2, (atk_rect.centerx - t2.get_width()//2, atk_rect.centery + 10))
        if game_state != "playing":
            return
        # yarı şeffaf bar
        bar_h = 90
        bar = pygame.Surface((config.SCREEN_WIDTH, bar_h), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 70))
        surf.blit(bar, (0, config.SCREEN_HEIGHT - bar_h))
        # sol ok — FAZ15: safe margin + pressed glow
        left_col = (255, 215, 0, 180) if self.left_pressed else (255, 255, 255, 90)
        # safe area: kenardan 14px icte (notch/gesture)
        left_rect = pygame.Rect(20 + self.safe_margin//2, config.SCREEN_HEIGHT - 75, 100, 60)
        pygame.draw.rect(surf, (255, 255, 255, 60), left_rect, border_radius=12)
        pygame.draw.rect(surf, (0, 0, 0, 180), left_rect, width=2, border_radius=12)
        if self.left_pressed:
            pygame.draw.rect(surf, (255, 215, 0), left_rect, width=3, border_radius=12)
        font = pygame.font.SysFont("Arial", 28, bold=True)
        txt = font.render("◀", True, (0, 0, 0) if not self.left_pressed else (0, 0, 0))
        surf.blit(txt, (left_rect.centerx - txt.get_width() // 2, left_rect.centery - txt.get_height() // 2))
        # sağ ok
        right_rect = pygame.Rect(config.SCREEN_WIDTH - 120 - self.safe_margin//2, config.SCREEN_HEIGHT - 75, 100, 60)
        pygame.draw.rect(surf, (255, 255, 255, 60), right_rect, border_radius=12)
        pygame.draw.rect(surf, (0, 0, 0, 180), right_rect, width=2, border_radius=12)
        txt2 = font.render("▶", True, (0, 0, 0))
        surf.blit(txt2, (right_rect.centerx - txt2.get_width() // 2, right_rect.centery - txt2.get_height() // 2))
        # orta zıpla / hızlı düş
        mid_rect = pygame.Rect(config.SCREEN_WIDTH // 2 - 60, config.SCREEN_HEIGHT - 75, 120, 60)
        pygame.draw.rect(surf, (120, 220, 120, 100), mid_rect, border_radius=12)
        pygame.draw.rect(surf, (0, 0, 0, 180), mid_rect, width=2, border_radius=12)
        small = pygame.font.SysFont("Arial", 11, bold=True)
        t1 = small.render("ZIPLA", True, (0, 0, 0))
        t2 = small.render("HIZLI DÜŞ", True, (0, 0, 0))
        surf.blit(t1, (mid_rect.centerx - t1.get_width() // 2, mid_rect.y + 8))
        surf.blit(t2, (mid_rect.centerx - t2.get_width() // 2, mid_rect.y + 32))
        # ipucu
        tiny = pygame.font.SysFont("Arial", 10)
        hint = tiny.render("Sola/Sağa kaydır  •  Ortaya dokun zıpla  •  Aşağı kaydır hızlı düş", True, (200, 200, 200))
        surf.blit(hint, (config.SCREEN_WIDTH // 2 - hint.get_width() // 2, config.SCREEN_HEIGHT - 18))
