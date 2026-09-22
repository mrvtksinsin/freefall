# FREEFALL

Dikey düşüş tabanlı, tek can odaklı bir arcade oyunu. Oyuncu yukarıdan aşağı düşerken engeller arasındaki boşluklardan süzülür, coin toplar, canavardan kaçar ve 23 katmanı aşmaya çalışır.

## Oyun Hakkında
FREEFALL sonsuz ve bölümlü modları birleştirir. Sonsuz modda mesafe ile seviye yükselir; bölümlü modda her katman kendi atmosferi, lore’u ve final portalıyla 23 bölümde ilerler. Tek can sistemi vardır — sıkışma (0.7s) ölümle biter. Mağaza, karakter ilerlemesi, tema ve lore sistemi oyuna bağlıdır.

## Özellikler
- **23 Bölüm:** HAVA’dan FINAL’a sıralı ilerleme
- **18 Karakter:** seviye ile açılır, herbiri lore’a sahip
- **40 Shop Item:** 10 şapka / 10 çanta / 10 gözlük / 10 baston
- **28 Tema:** beyaz/siyah/crimson/ice/forest/desert/ocean/neon_cyan/golden/blood_moon vb. (tema ≠ bölüm atmosferi)
- **Coin/Combo/Risk:** near-miss, combo x2..x6, risk bonusu, HUD flash
- **Monster:** Gap tabanlı kovalama (gap <180 tension, <90 yüksek), stagger/knockback, hit
- **VS BOT / ONLINE:** 5 haneli ID ile eşleşme, lobby/ready, server-authoritative
- **Story/Lore:** 23 level lore + 18 karakter lore + ◊ sembolü + opening 7.2s + FINAL 19.5s cinematic
- **Achievements/Statistics:** 8 başarım, play time/deaths/coins/combo/vs vb.
- **Settings:** MASTER/MUSIC/SFX, tutorial, fullscreen, FPS 30/60/90/120/unlimited, resolution 900x700/1280x720/1600x900/1920x1080, PC controls + F11
- **PC + Android:** aynı 900×700 sanal yüzey, Android’de letterbox + multitouch

## Bölümler (23)
1. HAVA — 2. TOPRAK — 3. KAYA — 4. MAGMA — 5. BUZUL — 6. DERIN — 7. KATMAN KAYASI — 8. KANALIZASYON — 9. CAFE — 10. OFIS — 11. BACKROOMS — 12. GUC SANTRALI — 13. MUZE — 14. SINIF — 15. FABRIKA — 16. POLIGAN — 17. ORMAN — 18. SARAY — 19. KOY — 20. SEHIR — 21. TOKYO — 22. FRANSA — 23. FINAL

## Kontroller

**PC**
- `← → / A D` — hareket (ivmeli 9 / sürtünme 7)
- `↑ / W` — zıpla (engel üstünde)
- `↓ / S` — hızlı düşüş / yuvarlanma (+25% max fall)
- `SPACE` — pause / resume
- `ESC` — menü (pause’u temizler, doğrudan ana menü)
- `F / J` veya sol tık — saldırı (yumruk/ışın kılıcı)
- `H` — NASIL OYNANIR? modal
- `M` — genel MUSIC toggle (tüm müzikler)
- `F11` — fullscreen toggle
- Menü: `↑↓←→` + `ENTER/SPACE` + mouse + scroll

**Android**
- Alt bar: sol %40 = sol, sağ %40 = sağ, orta üst = zıpla, orta alt = hızlı düş
- Oyun alanı: sol %33 = sol, sağ %33 = sağ, orta = zıpla
- Sağ üst `HIT` = saldırı, alt bar yarı şeffaf + safe margin 14px (notch/gesture)
- Multitouch: hareket + saldırı + zıpla aynı anda (OR)
- Geri tuşu: shop/characters/settings → menü, playing → menü, gameover → menü

## Oyun Modları
- **Offline Sonsuz:** mesafe ile seviye, canavar yok
- **Bölümler:** canavarlı kaçış, bitiş portalına ulaş, yıldız 1-3, bir sonrakini aç (sequential `1..maxCompleted+1`)
- **VS BOT:** 160m yarış, bitiş çizgisi, canavar her iki yarışçıyı kovalar
- **ONLINE:** hesap/misafir kapısı → OYNA → ONLINE → 5 haneli ID ara → davet/lobby/ready → `vs_online` (server yoksa offline bozulmaz)

## Save Sistemi
`save_system.py` → `save.json` (JSON). `total_coins/best_distance/level/unlocked_levels/completed_levels/level_stars/owned_items/owned_weapons/equipped_weapon/selected_character/theme/statistics/achievements/seen_lore/opening_shown/final_cinematic_seen/settings{master,music,sfx,show_tutorial,fullscreen,fps_limit,resolution,music_enabled}`. Eksik/bozuk dosya → default’a düşer, `is_valid_nick/player_id` sanitize, invalid item/theme temizlenir, `settings` clamp. **Backward compatible** — eski save (sadece master) yeni sürümde kayıpsız açılır, `unlock_next_level` sıralı açmayı korur.

## Audio
Tamamen **procedural, telifsiz** (dosya yok, `audio.py` `_make_tone` sine/saw/square). Lisanslı popüler şarkı gömülmedi. SFX (coin/jump/land/roll/click/hover/death/levelup/combo/punch/sword) `MASTER*SFX` ile, music `MASTER*MUSIC` ile bağımsız. `MASTER` ikisini de kontrol eder.
- `menu_rock` (86Hz saw) — ana menü dark rock
- Level music: `LEVEL_ATMOSPHERES` `music_key` → `_MUSIC_PROFILES` (ambient_air … final) — aynı key’de restart yok
- `threat_rock` (58Hz saw) — `monster gap<180` → `tension 0..1` lerp 4.5 → normal `*(1-0.6*tension)` duck, threat `*0.88*tension` rise (soft crossfade, her frame `play()` yok)
- `M` genel toggle, `music_enabled` persist

## Android
`Buildozer + python-for-android + SDL2 + pygame 2.6.1`. `buildozer.spec` `orientation=landscape`, `android.permissions=INTERNET` (sadece online için), `api 33 / min 21`. `ANDROID_BUILD.md`’de 3 yöntem (GitHub Actions — önerilen, WSL, Pydroid). Android native `dw,dh` → `scale=min(dw/900,dh/700)*0.98` letterbox, PC `resolution` sistemi Android’e zorlanmaz. **Gerçek cihaz testleri UNVERIFIED** — headless multitouch/safe-area/display testleri geçti, fiziksel APK install/hoparlor/GPU testleri cihaz gerektirir.

## Performance
Hedef: ~4GB RAM’li eski sistemde makul çalışır (oyun yalnızca 4GB kullanır anlamına gelmez). `WORLD particle ≤220`, `ATMOSPHERE ≤28`, `MENU ≤15`, `audio music cache ≤28 / threat ≤8`, `glow/gradient` cache, `font` cache, per-frame büyük `Surface`/`smoothscale` 1/frame, `particle` cap, `dt clamp 1/20`, dt bağımsız fizik (`GRAVITY 1400, MAX_FALL 650, GAP_MIN 130` sabit).

## Build

**Windows PC**
```bash
pip install -r requirements.txt  # pygame>=2.0.0
python main.py
# veya SERVER ile LAN ONLINE:
python SERVER/server.py
```

**Android**
```bash
# GitHub Actions (önerilen): push → Actions → Build FREEFALL APK → artifact indir
# WSL:
sudo apt install git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev cmake libffi-dev libssl-dev
pip install buildozer cython==0.29.36
buildozer android debug  # bin/freefall-1.2-debug.apk
```
Windows native `buildozer` çalışmaz — WSL/Docker/GitHub Actions gerekir.

## Project Structure
```
main.py            # loop, _apply_pc_display (PC/Android letterbox), FPS, K_AC_BACK
game.py            # 24 state FSM (account_gate→menu→play_select→levels→playing→level_complete/final_cinematic...), HUD, shop/char/inv/theme/settings/stats/lore/help/pause/result
config.py          # SCREEN 900x700, FPS 60, GRAVITY 1400, MAX_FALL 650, GAP 130-190, 23 LEVELS, 18 CHARACTERS, 40 SHOP, 28 THEMES, 2 WEAPONS, 23 LEVEL_ATMOSPHERES, get_music_key
save_system.py     # JSON save, backward compat, sanitize, unlock_next_level
audio.py           # procedural AudioManager, menu_rock/threat_rock crossfade, cache
graphics.py        # gradient/glow/vignette/button/bevel (cache)
particles.py       # ParticleSystem (cap 220)
player.py          # handle_input (accel 9/friction 7), update_physics (gravity, crush 0.7s), draw _costume
monster.py         # update (gap 220-3*lvl, turbo), stagger, check_catch
camera.py          # exp lerp 1-exp(-6*dt)
world.py           # procedural obstacles (5 pattern, gap 130→92, spacing 220→170), coins, decor
bot.py             # BotPlayer AI
online.py          # TCP client (auto-connect, 5-digit ID)
android_controls.py# TouchControls (multitouch OR, safe_margin 14, swipe)
SERVER/            # TCP server (SQLite players.db, sessions)
buildozer.spec     # landscape, sdl2, pygame==2.6.1
data/              # levels/characters/shop/themes json (data_loader)
```

## Testing (F4-F16 özet — tarihsel değiştirilmedi)
- F4 438/438 — world/camera/physics
- F5 54/54 — coin/combo/economy
- F6 73/73 — combat/weapon
- F7 63/63 — theme/polish
- F8 36/36 — menu
- F9 60/60 — atmosphere
- F10 43/43 — HUD/result
- F11 86/86 — lore/cinematic
- F12 46/46 — final cinematic
- F13 12/12 — settings/display
- F14 29/29 — audio crossfade + UI final
- F15 24/24 — Android (headless)
- **F16 32/32 PASSED, 0 FAILED, 6 UNVERIFIED** — UNVERIFIED = fiziksel APK install, multitouch 2-3 parmak, notch/safe area gerçek cihaz, hoparlör, GPU FPS, Android full build (Windows’ta mümkün değil — GitHub Actions/WLS gerekir)

## License
License not yet specified — mevcut repository’de açık lisans dosyası yok, eklenmedi.

## Version
`FREEFALL v1.2` — `buildozer.spec:version = 1.2`, `game.py: v1.2` label, `README` başlığı. Çelişkili versiyon yok.
