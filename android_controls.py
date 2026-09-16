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
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.screen_w = config.SCREEN_WIDTH
        self.screen_h = config.SCREEN_HEIGHT
        self.real_w = config.SCREEN_WIDTH
        self.real_h = config.SCREEN_HEIGHT

    def set_screen_info(self, real_w, real_h, scale_x, scale_y):
        self.real_w = real_w
        self.real_h = real_h
        self.scale_x = scale_x
        self.scale_y = scale_y

    def _to_game_pos(self, pos):
        """Gerçek ekran posunu oyun 900x700 koordinatına çevir"""
        x, y = pos
        gx = x / self.scale_x
        gy = y / self.scale_y
        return gx, gy

    def handle_touch(self, event):
        """MOUSE/FINGER eventlerini işle, True dönerse oyun handle_etmemeli"""
        if event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            # finger x,y 0-1 normalize
            x = event.x * self.real_w
            y = event.y * self.real_h
            gx, gy = self._to_game_pos((x, y))
            return self._update_from_pos(gx, gy, event.type)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            # Android'de mouse olarak da gelebilir
            if hasattr(event, 'pos'):
                gx, gy = self._to_game_pos(event.pos)
                if event.type == pygame.MOUSEBUTTONDOWN:
                    return self._update_from_pos(gx, gy, pygame.FINGERDOWN)
                elif event.type == pygame.MOUSEBUTTONUP:
                    # parmak kalktı - tümünü bırak
                    self.left_pressed = False
                    self.right_pressed = False
                    self.down_pressed = False
                    self.up_pressed = False
                    return False
                elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
                    return self._update_from_pos(gx, gy, pygame.FINGERMOTION)
        return False

    def _update_from_pos(self, gx, gy, typ):
        # alt %30'luk alanda dokunmatik joystick
        # ekranı dikeyde 3'e böl: üst %15 pause, orta oyun, alt %25 kontroller
        if typ == pygame.FINGERUP:
            self.left_pressed = False
            self.right_pressed = False
            self.down_pressed = False
            self.up_pressed = False
            return False

        # pause alanı (üst bar)
        if gy < 70:
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
        # tek seferlik up (zıpla) bir frame sonra bırak
        self.up_pressed = False

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
        """Alt kontrol overlay çiz - sadece playing'de"""
        if game_state != "playing":
            return
        # yarı şeffaf bar
        bar_h = 90
        bar = pygame.Surface((config.SCREEN_WIDTH, bar_h), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 70))
        surf.blit(bar, (0, config.SCREEN_HEIGHT - bar_h))
        # sol ok
        left_col = (255, 215, 0, 180) if self.left_pressed else (255, 255, 255, 90)
        left_rect = pygame.Rect(20, config.SCREEN_HEIGHT - 75, 100, 60)
        pygame.draw.rect(surf, (255, 255, 255, 60), left_rect, border_radius=12)
        pygame.draw.rect(surf, (0, 0, 0, 180), left_rect, width=2, border_radius=12)
        font = pygame.font.SysFont("Arial", 28, bold=True)
        txt = font.render("◀", True, (0, 0, 0) if not self.left_pressed else (0, 0, 0))
        surf.blit(txt, (left_rect.centerx - txt.get_width() // 2, left_rect.centery - txt.get_height() // 2))
        # sağ ok
        right_rect = pygame.Rect(config.SCREEN_WIDTH - 120, config.SCREEN_HEIGHT - 75, 100, 60)
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
