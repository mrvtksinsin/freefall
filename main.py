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

def _apply_pc_display(save, is_android_runtime):
    """FAZ13: PC display uygula — fullscreen/resolution guvenli, fallback'li.
    Returns (screen, game_surf, rw, rh, offset_x, offset_y, scale_x, scale_y, real_w, real_h)"""
    try:
        if is_android_runtime:
            info = pygame.display.Info()
            dw = info.current_w if info.current_w else 1080
            dh = info.current_h if info.current_h else 1920
            scale = min(dw / config.SCREEN_WIDTH, dh / config.SCREEN_HEIGHT) * 0.98
            rw = int(config.SCREEN_WIDTH * scale)
            rh = int(config.SCREEN_HEIGHT * scale)
            screen = pygame.display.set_mode((dw, dh), pygame.FULLSCREEN)
            pygame.display.set_caption(config.TITLE)
            game_surf = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            real_w, real_h = dw, dh
            scale_x = rw / config.SCREEN_WIDTH
            scale_y = rh / config.SCREEN_HEIGHT
            offset_x = (dw - rw) // 2
            offset_y = (dh - rh) // 2
            return screen, game_surf, rw, rh, offset_x, offset_y, scale_x, scale_y, real_w, real_h
        else:
            pygame.display.set_caption(config.TITLE)
            settings = save.get("settings", {}) if isinstance(save, dict) else {}
            fs = bool(settings.get("fullscreen", False))
            res = str(settings.get("resolution", "900x700"))
            if fs:
                # fullscreen: native desktop (0,0) en guvenli, fallback 900x700 fullscreen
                try:
                    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    info = pygame.display.Info()
                    dw = screen.get_width() if screen else info.current_w
                    dh = screen.get_height() if screen else info.current_h
                    # virtual scaling for fullscreen
                    scale = min(dw / config.SCREEN_WIDTH, dh / config.SCREEN_HEIGHT) * 0.98
                    rw = int(config.SCREEN_WIDTH * scale)
                    rh = int(config.SCREEN_HEIGHT * scale)
                    game_surf = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
                    real_w, real_h = dw, dh
                    scale_x = rw / config.SCREEN_WIDTH
                    scale_y = rh / config.SCREEN_HEIGHT
                    offset_x = (dw - rw) // 2
                    offset_y = (dh - rh) // 2
                    return screen, game_surf, rw, rh, offset_x, offset_y, scale_x, scale_y, real_w, real_h
                except:
                    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.FULLSCREEN)
                    game_surf = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
                    real_w, real_h = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
                    scale_x = scale_y = 1.0
                    offset_x = offset_y = 0
                    rw, rh = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
                    return screen, game_surf, rw, rh, offset_x, offset_y, scale_x, scale_y, real_w, real_h
            else:
                try:
                    w, h = map(int, res.split("x"))
                    if (w, h) not in [(900,700),(1280,720),(1600,900),(1920,1080)]:
                        w, h = 900, 700
                except:
                    w, h = 900, 700
                screen = pygame.display.set_mode((w, h))
                # windowed: direct draw (no virtual scaling) — performans
                game_surf = screen
                real_w, real_h = w, h
                scale_x = scale_y = 1.0
                offset_x = offset_y = 0
                rw, rh = w, h
                return screen, game_surf, rw, rh, offset_x, offset_y, scale_x, scale_y, real_w, real_h
    except Exception as e:
        print(f"[Main] display init fail: {e}")
        # ultimate fallback
        try:
            screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            pygame.display.set_caption(config.TITLE)
        except:
            return None, None, 900,700,0,0,1.0,1.0,900,700
        return screen, screen, config.SCREEN_WIDTH, config.SCREEN_HEIGHT, 0,0,1.0,1.0,config.SCREEN_WIDTH, config.SCREEN_HEIGHT

def main():
    pygame.init()
    is_android_runtime = _is_android_runtime()
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
    # display — save'e gore (FAZ13)
    screen, game_surf, rw, rh, offset_x, offset_y, scale_x, scale_y, real_w, real_h = _apply_pc_display(save, is_android_runtime)
    if screen is None:
        return
    clock = pygame.time.Clock()
    touch = TouchControls() if (_has_touch and is_android_runtime) else None
    if touch:
        touch.set_screen_info(real_w, real_h, scale_x, scale_y, offset_x, offset_y)

    try:
        game = Game(save)
        game.init_fonts()
    except Exception as e:
        print(f"[Main] game init fail: {e}")
        return

    running = True
    while running:
        # FAZ13: dynamic FPS (30/60/90/120/sinirsiz) — dt bbagimsiz fizik korunur
        try:
            fps_lim = int(game.save.get("settings", {}).get("fps_limit", 60)) if 'game' in locals() else 60
            if fps_lim == 0:
                dt = clock.tick(0) / 1000.0
            else:
                # clamp to allowed values
                if fps_lim not in (30,60,90,120):
                    fps_lim = 60
                dt = clock.tick(fps_lim) / 1000.0
        except:
            dt = clock.tick(config.FPS) / 1000.0
        if dt > 1/20:
            dt = 1/20
        # FAZ13: display degisimi algila (fullscreen/resolution) — main screen referansi tazelensin
        try:
            if 'game' in locals() and getattr(game, '_display_changed', False):
                game._display_changed = False
                # save guncel, yeniden uygula
                screen, game_surf, rw, rh, offset_x, offset_y, scale_x, scale_y, real_w, real_h = _apply_pc_display(game.save, is_android_runtime)
                if touch and not is_android_runtime and screen is not None:
                    # PC fullscreen scaling icin touch bilgisi guncelle (gerekirse)
                    try:
                        if game.save["settings"].get("fullscreen", False):
                            touch.set_screen_info(real_w, real_h, scale_x, scale_y, offset_x, offset_y)
                    except: pass
        except Exception as e:
            print(f"[Display] refresh fail: {e}")
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    try: save_system.save_game(game.save)
                    except: pass
                    try:
                        if hasattr(game, 'online_mgr') and game.online_mgr:
                            if getattr(game, 'lobby_id', None):
                                try: game.online_mgr.leave_lobby(game.lobby_id)
                                except: pass
                            try: game.online_mgr.disconnect()
                            except: pass
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
                            handled_by_touch = touch.handle_touch(event, getattr(game, 'state', None), game)
                        except: pass
                    # Dokunma / mouse koordinatini virtual 900x700'e cevir (Android + PC fullscreen)
                    if not handled_by_touch:
                        try:
                            is_scaled = is_android_runtime or (not is_android_runtime and game.save.get("settings",{}).get("fullscreen", False))
                            if is_scaled and hasattr(event, 'pos'):
                                try:
                                    rx, ry = event.pos
                                    gx = (rx - offset_x) / scale_x
                                    gy = (ry - offset_y) / scale_y
                                    # sadece oyun alani icindeyse map et, disinda clamp
                                    if 0 <= gx <= config.SCREEN_WIDTH and 0 <= gy <= config.SCREEN_HEIGHT:
                                        event.pos = (gx, gy)
                                    elif is_scaled:
                                        # fullscreen disinda kalan tiklamalar oyun disinda -> yine map ama clamp ile engelle
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
                        # FAZ6: attack (Android)
                        if touch and getattr(touch, 'attack_pressed', False) and game.state in ("playing","vs_bot","vs_online") and not game.paused and game.player.alive:
                            try:
                                wid = game.save.get("equipped_weapon","fist")
                                if game.player.try_attack(wid):
                                    w = config.get_weapon(wid)
                                    from audio import audio as _audio2
                                    _audio2.play("sword_swing" if wid=="beam_sword" else "punch", 0.7)
                            except: pass

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
            # çizim — FAZ13: PC fullscreen'de de virtual scaling (Android ile ayni yol)
            is_scaled_draw = is_android_runtime or (not is_android_runtime and game.save.get("settings",{}).get("fullscreen", False))
            draw_surf = game_surf if is_scaled_draw else screen
            # need to ensure draw_surf is current display for windowed
            if not is_scaled_draw:
                try:
                    draw_surf = pygame.display.get_surface() or screen
                except:
                    draw_surf = screen
            try:
                game.draw(draw_surf)
                if touch:
                    touch.draw(draw_surf, game.state)
            except Exception as e: print(f"[Draw] {e}")
            if is_scaled_draw:
                # letterbox arka plan + scale blit
                try:
                    screen.fill((0,0,0))
                    scaled = pygame.transform.smoothscale(game_surf, (rw, rh))
                    screen.blit(scaled, (offset_x, offset_y))
                except Exception as e:
                    print(f"[Draw] scale fail: {e}")

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
