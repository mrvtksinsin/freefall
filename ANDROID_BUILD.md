# Android APK - Nasıl Alınır (3 Yöntem)

Bu proje Windows'ta doğrudan APK üretemez (Android SDK/NDK Linux ister).
Aşağıdaki 3 yöntemden biriyle APK alabilirsin - hepsi hazırlandı.

## Yöntem 1: GitHub Actions (ÖNERİLEN - 1 Tık, En Kolay)
1. Bu `freefall` klasörünü GitHub'a push et (zaten `.github/workflows/build-apk.yml` hazır)
2. GitHub → Actions → "Build FREEFALL APK" → Run workflow
3. 15-25dk sonra Artifacts → `freefall-apk` → `freefall-1.2-debug.apk` indir
4. Telefonda `Ayarlar → Bilinmeyen kaynaklara izin ver` → APK kur

## Yöntem 2: WSL Ubuntu (Kendi PC'nde)
```bash
# Windows'ta WSL kuruluysa (Microsoft Store → Ubuntu)
wsl
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev cmake libffi-dev libssl-dev
pip install buildozer cython==0.29.36
cd /mnt/c/Users/BEAR/Desktop/freefall
buildozer android debug
# bin/freefall-1.2-debug.apk oluşur
# Telefona at: adb install bin/*.apk  veya dosyayı telefona kopyala
```

## Yöntem 3: Pydroid 3 (APK Olmadan Hemen Oyna - 2dk)
1. Play Store → Pydroid 3 kur
2. Pydroid → pip → `pygame` kur
3. `freefall` klasörünü telefona kopyala (Telegram/Drive ile)
4. Pydroid → Open → `main.py` → Run
   - Dokunmatik zaten aktif (is_android algılar)
   - Kayıt otomatik Android klasöründe tutulur

## Dosya Hazırlığı (Zaten Yapıldı)
- `buildozer.spec` → `python3,pygame==2.6.1` sdl2 bootstrap, portrait, api 33
- `android_controls.py` → sol/sağ/zıpla/hızlı düş dokunmatik bar
- `main.py` → fullscreen letterbox + scale + K_AC_BACK
- `save_system.py` → Android özel yol

## Test
PC'de hala `python main.py` ile aynı kalır, Android'de otomatik dokunmatik açılır.
