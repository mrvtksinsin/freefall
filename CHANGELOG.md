# CHANGELOG — FREEFALL

Tarihsel fazlar; yapılmamış özellik eklenmedi.

## v1.2 — Final (F4-F16)
- **F16 (Final QA):** VS BOT duplicate death_timer (2× increment) ve gameover M intercept düzeltildi. 32/32 PASS, 6 UNVERIFIED (gerçek cihaz).
- **F15 (Android):** `android_controls` multitouch OR + safe_margin 14, `buildozer.spec` portrait→landscape, `main.py` letterbox + touch scaling, 24/24 headless PASS.
- **F14 (Audio/UI Final):** İzmir Marşı kaldırıldı, `menu_rock`/`threat_rock` procedural dark rock, `tension` crossfade (normal duck 0.6 / threat 0.88), M → genel `music_enabled` toggle, menu HUD `M: Müzik`, settings/shop/characters/inventory/themes vignette polish, version label dinamik.
- **F13 (Settings/PC):** Settings 9 item (MASTER/MUSIC/SFX/tutorial/fullscreen/FPS 30/60/90/120/unlimited/resolution 4/controls/GERI), `F11` safe display, `_display_changed` stale surface fix, FPS dt bağımsız, vignette.
- **F12 (Final Cinematic):** 19.5s FINAL, `final_cinematic_seen`, auto→level_complete, skip.
- **F11 (Lore):** 23 `LEVEL_LORE` + 18 `CHARACTER_LORE` + `MONSTER_LORE` + `seen_lore` + opening 7.2s + level intro 1.6s + ◊ sembolü.
- **F10 (HUD/Result):** HUD glass + coin/combo/weapon, `level_complete` star sequential + reward rows + new unlock glow.
- **F9 (Atmosphere):** 23 `LEVEL_ATMOSPHERES` (bg/secondary/glow/particle/density/cap/vignette/music_key), `world/particles` `particle_cap` 10-28, `audio` per-level `music_key`.
- **F8 (Menu):** 12-item menu (OYNA…CIKIS), adaptive 11→320×38, preview char bob, soft shadow/glow, hover/pressed distinct.
- **F7 (Theme):** 28 tema (beyaz…royal_gold) + `LEVEL_ATMOSPHERES` ayrımı, `graphics` cache.
- **F6 (Combat):** `WEAPONS` fist (88 range) / beam_sword (148), `try_attack` 0.22/0.33s, hitbox, stagger, shop/weapon tab, inventory weapon.
- **F5 (Economy):** coin 1/5, combo bonus, risk bonus cap 6, `level_run_*` tracking, HUD coin flash, near-miss.
- **F4 (Core):** Procedural world (5 pattern, gap 130→92, spacing 220→170), camera `1-exp(-6*dt)`, player `GRAVITY 1400, MAX_FALL 650`, crush 0.7s, particles cap 200, online `SERVER/` 5-digit ID, bot, save `level` progression.

## v1.0 – v1.1 (ilk iskelet)
- Pencere 900×700, sonsuz dünya, 10 karakter/tema/shop, data-driven `data/` otomatik oluşturma, tek can, `save.json` JSON, `audio` placeholder tone.

## Not
- Telifli müzik gömülmedi (procedural).
- Fizik/difficulty/hitbox F4’ten beri sabit.
- Eski save’ler kayıpsız açılır (settings default’ları ile).
