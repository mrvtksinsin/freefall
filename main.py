import pygame
import sys
import os
import config
import save_system
from game import Game
from data_loader import ensure_data_files, apply_data_to_config

# Android dokunmatik desteği (varsa)
try:
    from android_controls import TouchControls, is_android
    _has_touch = True
except:
    TouchControls = None
    def is_android(): return False
    _has_touch = False

def _is_android_runtime():
    try:
        return is_android()
    except:
        return False

def main():
    pygame.init()
    is_android_runtime = _is_android_runtime()
    # Android'de fullscreen ve ölçeklendirme
    real_w, real_h = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
    scale_x = scale_y = 1.0
    # Ölçeklendirme için ayrı surface (oyun hep 900x700 mantıksal)
    game_surf = None
    try:
        if is_android_runtime:
            # Android fullscreen - gerçek ekran boyutu
            info = pygame.display.Info()
            # info.current_w/h bazen 0 dönebilir, fallback
            dw = info.current_w if info.current_w else 1080
            dh = info.current_h if info.current_h else 1920
            # portrait tut, oyun 900x700'ü ortala ve ölçekle
            scale = min(dw / config.SCREEN_WIDTH, dh / config.SCREEN_HEIGHT) * 0.98
            rw = int(config.SCREEN_WIDTH * scale)
            rh = int(config.SCREEN_HEIGHT * scale)
            screen = pygame.display.set_mode((dw, dh), pygame.FULLSCREEN)
            pygame.display.set_caption(config.TITLE)
            game_surf = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            real_w, real_h = dw, dh
            scale_x = rw / config.SCREEN_WIDTH
            scale_y = rh / config.SCREEN_HEIGHT
            # ortalamak için offset
            offset_x = (dw - rw) // 2
            offset_y = (dh - rh) // 2
        else:
            pygame.display.set_caption(config.TITLE)
            screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            game_surf = screen
            offset_x = offset_y = 0
            rw = config.SCREEN_WIDTH
            rh = config.SCREEN_HEIGHT
    except Exception as e:
        print(f"[Main] display init fail: {e}")
        return
    clock = pygame.time.Clock()
    touch = TouchControls() if (_has_touch and is_android_runtime) else None
    if touch:
        touch.set_screen_info(real_w, real_h, scale_x, scale_y)

    # data-driven dosyaları oluştur (yoksa) ve JSON'dan config'i yükle
    try:
        ensure_data_files(config)
        apply_data_to_config(config)
    except Exception as e:
        print(f"[Main] data files ensure fail: {e}")

    try:
        save = save_system.load_save()
    except Exception as e:
        print(f"[Main] save load fail: {e} -> default")
        import copy as _copy
        save = _copy.deepcopy(save_system.DEFAULT_SAVE)

    try:
        game = Game(save)
        game.init_fonts()
    except Exception as e:
        print(f"[Main] game init fail: {e}")
        return

    running = True
    while running:
        dt = clock.tick(config.FPS) / 1000.0
        if dt > 1/20:
            dt = 1/20
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    try: save_system.save_game(game.save)
                    except: pass
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == getattr(pygame, 'K_AC_BACK', -1):
                    # Android geri tuşu — ESC ile aynı: doğrudan ana menü (pause açma)
                    if game.state in ("shop","characters","inventory","themes","settings"):
                        game.state = "menu"
                    elif game.state == "playing":
                        try:
                            game._return_to_menu()
                        except:
                            game.state = "menu"
                            game.paused = False
                    elif game.state == "gameover":
                        game.state = "menu"
                    else:
                        try: save_system.save_game(game.save)
                        except: pass
                        running = False
                else:
                    # dokunmatik öncelik
                    handled_by_touch = False
                    if touch:
                        try:
                            handled_by_touch = touch.handle_touch(event)
                        except: pass
                    # Android dokunması oyun UI'sine de iletilsin (handle_event içinde mouse'a çevrilir)
                    if not handled_by_touch:
                        try:
                            # Android MOUSE posunu ölçeklendir
                            if is_android_runtime and hasattr(event, 'pos'):
                                # event.pos gerçek ekran -> oyun koordinatı
                                try:
                                    rx, ry = event.pos
                                    gx = (rx - offset_x) / scale_x
                                    gy = (ry - offset_y) / scale_y
                                    event.pos = (gx, gy)
                                except: pass
                            game.handle_event(event)
                        except Exception as e: print(f"[Event] {e}")
                    else:
                        # dokunmatik zıplama tetikle
                        if touch and touch.up_pressed and game.state == "playing" and not game.paused:
                            jumped = game.player.try_jump()
                            if jumped:
                                game.particles.emit_jump(game.player.x + game.player.w//2, game.player.y + game.player.h)
                                from audio import audio as _audio
                                _audio.play("jump")

            # klavye + dokunmatik birleşimi
            keys = pygame.key.get_pressed()
            if touch and game.state == "playing" and not game.paused:
                # touch left/right/down override
                class _K:
                    def __getitem__(self, k):
                        if k in (pygame.K_LEFT, pygame.K_a):
                            return touch.left_pressed or keys[k]
                        if k in (pygame.K_RIGHT, pygame.K_d):
                            return touch.right_pressed or keys[k]
                        if k in (pygame.K_DOWN, pygame.K_s):
                            return touch.down_pressed or keys[k]
                        if k in (pygame.K_UP, pygame.K_w):
                            return touch.up_pressed or keys[k]
                        return keys[k]
                keys = _K()
            try: game.update(dt, keys)
            except Exception as e: print(f"[Update] {e}")
            # çizim
            draw_surf = game_surf if is_android_runtime else screen
            try:
                game.draw(draw_surf)
                if touch:
                    touch.draw(draw_surf, game.state)
            except Exception as e: print(f"[Draw] {e}")
            if is_android_runtime:
                # letterbox arka plan
                screen.fill((0,0,0))
                scaled = pygame.transform.smoothscale(game_surf, (rw, rh))
                screen.blit(scaled, (offset_x, offset_y))

            pygame.display.flip()
            if touch:
                touch.reset_frame()
        except Exception as e:
            print(f"[Loop] {e}")

    try: pygame.quit()
    except: pass
    sys.exit()

if __name__ == "__main__":
    main()
