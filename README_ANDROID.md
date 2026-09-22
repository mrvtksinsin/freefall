# FREEFALL - Android Sürümü

## Özet
PC için `pygame` ile yazılan FREEFALL, **hiçbir grafik/kod kaybı olmadan** Android'e taşındı.
- Oyun mantığı aynı: `900x700` sanal çözünürlük, Android'de otomatik ölçeklenir (fullscreen letterbox).
- Dokunmatik: sol/sağ kaydır, ortaya dokun zıpla, aşağı kaydır hızlı düş/roll.
- Kayıt: `save.json` Android özel klasörde (`app_storage_path` / `ANDROID_PRIVATE`), PC'deki gibi kalıcı.
- Geri tuşu: `shop/characters` → menü, `playing` → pause, `gameover` → menü.

## Yapılan Değişiklikler
- `android_controls.py` yeni: `TouchControls` (3 bölge + alt bar) `main.py:9-65` entegrasyonu
- `save_system.py:6` `_get_save_path()` Android özel yol
- `main.py:24-65` Android fullscreen ölçeklendirme (`game_surf` + `smoothscale` + `offset_x/y`)
- `main.py:89-130` `FINGER`/`MOUSE` dokunmatik → `handle_event` ölçek dönüşümü, `K_AC_BACK` geri tuşu
- `buildozer.spec` eklendi (p4a sdl2 bootstrap, `python3,pygame==2.6.1`, `api 33`, `landscape`)

## Gereksinimler (PC'de build için - Linux/WSL önerilir)
```bash
pip install buildozer cython
# Ubuntu/WSL:
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
```

## Build
```bash
# proje kökünde (freefall/)
buildozer android debug
# ilk build 15-40 dk sürebilir, SDK/NDK otomatik indirilir
# sonuç: bin/freefall-1.2-debug.apk
```
Ardından:
```bash
buildozer android deploy run
# veya adb install bin/*.apk
```

## Alternatif (Docker - Windows'ta en kolay)
```bash
docker run --rm -v "%cd%":/home/user/hostcwd kivy/buildozer android debug
```

## Test (PC'de Android modunu taklit)
`main.py` masaüstünde aynı kalır, dokunmatik aktif olmaz. Zorla test için:
```python
# main.py başına geçici:
import os; os.environ['ANDROID_ARGUMENT']='1'
```

## Dokunmatik Kontroller (Android)
- **Ekran alt bar:** `◀ 100x60` sol, `▶ 100x60` sağ, orta `ZIPLA / HIZLI DÜŞ`
- **Oyun alanı:** sol %33 = sol, sağ %33 = sağ, orta = tek dokunuşta zıpla
- **Üst bar:** orijinal UI, dokunmatik oyun alanına iletilmez
- **Geri tuşu:** Android sistem geri → pause/menü

## Performans Notları
- `FPS 60`, `dt clamp 1/20`, particle cap 200, `WORLD_CLEAN_BEHIND 1500` korundu
- Ölçeklendirme için `smoothscale` sadece bir kez/frame, `game_surf` 900x700 sabit → GPU dostu
- Ses `audio.py` `mixer init 44100 buffer 512` Android'de de çalışır, yoksa sessiz moda düşer

## Sorun Giderme
- `buildozer` Windows native'de çalışmaz → **WSL2 Ubuntu** veya Docker kullan
- `p4a` pygame recipe yoksa: `requirements = python3,pygame` yerine `python3,kivy,pygame` deneyin
- `save.json` PC'deki ile Android'deki ayrıdır, manuel taşımak için `adb pull/push`
- Ekran siyah kalırsa `buildozer.spec` `fullscreen = 0` → `1` yapıp yeniden deneyin
