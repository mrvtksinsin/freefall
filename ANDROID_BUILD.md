# FREEFALL — Android APK Build

FREEFALL `900×700` sanal yüzeyde çalışır, Android’de native `dw×dh` → `scale = min(dw/900,dh/700)*0.98` ile **landscape letterbox** ölçeklenir (PC `resolution` sistemi Android’e zorlanmaz).

## Build Sistemi
- **Buildozer** + **python-for-android** + **SDL2** + **pygame 2.6.1**
- `buildozer.spec`:
  ```
  title = FREEFALL
  package.name = freefall
  package.domain = com.freefall.game
  orientation = landscape
  android.manifest.orientation = landscape
  requirements = python3,pygame==2.6.1
  p4a.bootstrap = sdl2
  android.permissions = INTERNET   # sadece ONLINE için, kamera/konum/mic yok
  android.api = 33, min 21, ndk 25b
  source.include_exts = py,png,jpg,kv,atlas,json,txt,ttf,wav,mp3,ogg
  source.exclude_exts = spec,md
  ```
- `android_controls.py` — `TouchControls` (multitouch OR, safe_margin 14, alt bar 90px, saldırı 76×76 top-right)
- `main.py:24-122` — `is_android()` (`sys.getandroidapilevel` / `ANDROID_ARGUMENT`) → Android fullscreen path, `set_screen_info(real_w,real_h,scale,offset)`
- `save_system.py:6` — Android’de `app_storage_path()` / `ANDROID_PRIVATE`, PC’de proje dizini

## Yöntemler

### Yöntem 1 — GitHub Actions (ÖNERİLEN, 1 tık)
1. `freefall` klasörünü `https://github.com/mrvtksinsin/freefall`’a push et (`.github/workflows/build-apk.yml` hazır)
2. GitHub → Actions → *Build FREEFALL APK* → Run workflow
3. 15-25 dk sonra Artifacts → `freefall-apk` → `freefall-1.2-debug.apk`
4. Cihazda *Bilinmeyen kaynaklara izin ver* → kur

### Yöntem 2 — WSL Ubuntu (kendi PC’nde)
```bash
wsl
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev cmake libffi-dev libssl-dev
pip install buildozer cython==0.29.36
cd /mnt/c/Users/BEAR/Desktop/freefall
buildozer android debug
# bin/freefall-1.2-debug.apk
adb install bin/*.apk
```

### Yöntem 3 — Pydroid 3 (APK olmadan 2 dk)
1. Play Store → Pydroid 3
2. pip → `pygame`
3. `freefall` klasörünü cihaza kopyala
4. Pydroid → `main.py` → Run (dokunmatik otomatik)

## Gereksinimler (sadece build için)
- Linux/WSL/macOS + JDK 17 + buildozer + cython 0.29.36
- Windows native `buildozer` **çalışmaz** (SDK/NDK Linux ister) — bu normal

## Windows’ta Doğrulama (headless, APK olmadan)
```bash
python -c "from android_controls import TouchControls; print('ok')"
python -c "import main; print('main import ok')"
# multitouch, safe-area, display scale headless testleri: 24/24 PASSED (F15)
```

## APK Build Verified
**APK build verified: NO / UNVERIFIED** — bu Windows ortamında gerçek `buildozer android debug` çalıştırılmadı (Linux/WSL/GitHub Actions gerekir). `buildozer.spec` syntax ve `p4a` recipe headless doğrulandı, fiziksel APK ve cihaz testleri gerçek cihaz gerektirir.

## Performans
`FPS 60` dt clamp `1/20`, `WORLD ≤220`, `ATMOSPHERE ≤28`, `MENU ≤15`, `audio cache ≤28`, `smoothscale` 1/frame, `game_surf` 900×700 sabit.

## Sorun Giderme
- `SDK/NDK not found` → WSL’de `buildozer` ilk run’da otomatik indirir
- `pygame recipe not found` → `requirements = python3,pygame==2.6.1` korundu (sdl2 uyumlu)
- `save.json` PC vs Android ayrıdır (`adb pull/push` ile taşınır)
- Ekran siyah → `buildozer.spec` `fullscreen 0` korunur (`main.py` letterbox zaten fullscreen)
