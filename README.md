# FREEFALL — Dikey Düşüş Oyunu (v1.2 Professional)

Python + Pygame ile profesyonel seviyeye yakın, dikey aşağı sonsuz düşüş oyunu.

**Çalıştırma**
```bash
pip install -r requirements.txt
python main.py
```

**Kontroller**
- `← → / A D` hareket — ivmeli, sürtünmeli, ani ışınlanma yok
- `↑ / W` zıplama (engel üstünde)
- `↓ / S` hızlı düşüş / yuvarlanma (max hız +25%)
- `SPACE` pause, `ESC` menü, `H` tutorial gizle
- Menülerde `↑↓←→` + `ENTER/SPACE` + Mouse + Scroll

**Çekirdek**
- Kamera karakter odaklı, smoothing (6.0 lerp), world/screen ayrımı, 5.8M'de snap ile kaybolma yok
- Fizik: `GRAVITY=1400`, `HORIZONTAL_ACCEL=9`, `FRICTION=7`, squash/stretch animasyon
- Procedural world: `WORLD_GEN_AHEAD=3000`, `WORLD_CLEAN_BEHIND=1500`, patternler `flat/stepped/notch/zigzag/narrow`, gap garantisi ≥90px, zorluk mesafeyle artar (gap küçülür, spacing 220→170)

**Katmanlar (data-driven)**
`config.py` + `data/levels.json` → HAVA → TOPRAK → KAYA → MAGMA → BUZUL → DERIN. Her katmanda bg/wall/obstacle/accent + atmosfer partikülleri (HAVA tozu, MAGMA kıvılcım, BUZUL kar) değişir. Yeni katman eklemek için `LEVELS` listesine ekle yeterli.

**Tek Can**
Can barı yok, 0.7sn sıkışma → death → parçacık (22) + ses + 1sn sonra Game Over. Crush üstte engel / yan duvar kontrolüyle tespit.

**Coin & Parçacık**
Engel boşluklarında `1/5` değerli coin, bobbing + spin animasyon, toplanınca `emit_coin` parıltı + `coin/coin5` sesi, HUD `COIN: toplam (+bu oyun)` anlık.

**Mağaza / Envanter / Karakter**
- `data/shop.json` ve `data/characters.json` data-driven. Şapka/Çanta/Gözlük/Baston kategorileri, her eşya `id/name/price/icon`, bir kez satın alınır, ortak envanter (karakter değişince kaybolmaz).
- 10 karakter seviye 1-10 ile açılır, `CHAR_OFFSETS` ile her karakterde şapka/gözlük konumu ayrı. Kilidi `🔒 Seviye X`.

**Temalar (8)**
`data/themes.json` → WHITE/BLACK/YELLOW_RED/RED_BLACK/BLACK_BLUE/PURPLE_BLUE/PINK_YELLOW/GREEN_GRAY — UI/bg/button/HUD ayrı, katmandan bağımsız.

**Menüler**
Ana Menü (OYNA/KARAKTERLER/MAGAZA/ENVANTER/TEMALAR/AYARLAR/CIKIS), HUD (seviye/mesafe/progress bar/coin), Pause (DEVAM/AYARLAR/MENU), Game Over (mesafe/coin/seviye/rekor ★, TEKRAR/MENU), Shop/Inventory/Characters/Themes hepsi hover + click sesi, mouse destekli.

**Ayarlar**
MASTER/MUSIC/SFX slider (←→ veya bar'a tıkla) + Tutorial toggle. `save.json → settings` içinde kalıcı, `audio.py` placeholder tone üretimi (dosya yoksa çökmez).

**Animasyon & Efekt**
Idle/Fall/Run/Jump/Roll/Death state, run bob, fall sway, squash on land/jump, spin coin, level-up banner (2.2sn + `emit_levelup`), atmosfer partikülleri (<30, cap 200).

**Kayıt**
`save_system.py` JSON, eksik/bozuk dosyada default'a döner, `settings/tutorial_done` dahil. `data/` klasörü otomatik oluşturulur.

**Performans & Dayanıklılık**
- Görünmeyen obje render yok, particle cap, eski bölüm temizleme, font cache, dt clamp 1/20.
- Tüm draw/update try/except, eksik asset → placeholder, mixer init fail → sessiz mod.
- Sonsuz dünya float tabanlı.

**Online Server (Gerçek)**
```
SERVER/
  server.py     # SQLite + TCP, 5 haneli ID'yi server üretir (benzersiz)
  config.py     # SERVER_HOST/PORT, CLIENT_HOST/PORT, DB_PATH
  database/players.db  # SQLite (otomatik)
  README.md     # Kurulum ve LAN test talimatı
```
- Client `SERVER/config.py` → `CLIENT_HOST/PORT` ile otomatik bağlanır, ID'yi server verir.
- `OYNA → ONLINE` ekranında kendi Nick/ID + `● Sunucuya bağlı / ● Sunucu bağlantısı yok` ve `OYUNCU ARA` (5 rakam) → server `search` → bulunamazsa `Bu ID ile çevrimiçi bir oyuncu bulunamadı.` / kapalıyken `Sunucuya bağlanılamadı.` (çökme yok).
- `BÖLÜMLER` (23 seviye HAVA→FINAL) server'dan bağımsız, offline çalışır.

**Hızlı Test (Local & LAN)**
```bash
# 1. Server'ı başlat
python SERVER/server.py          # 0.0.0.0:47822 dinler, LAN IP'yi yazdırır

# 2. Oyunu aç (aynı PC)
python main.py                   # İlk açılışta Nick gir → OLUŞTUR → server ID verir

# 3. İkinci client (aynı PC ikinci pencere veya başka PC)
#    LAN'de ise SERVER/config.py → CLIENT_HOST = "192.168.1.XX" (server IP) yap
python main.py

# 4. ONLINE → diğer oyuncunun 5 haneli ID'sini yaz → OYUNCU ARA
```

**Proje Yapısı**
```
main.py         # loop, data ensure, error guard
config.py       # tüm sabitler
player.py       # fizik + anim + offsets
camera.py       # smooth follow
world.py        # procedural + difficulty + decoration
particles.py    # particle system
audio.py        # mixer + tone generation
save_system.py  # JSON save (+ nickname/player_id 5 haneli, server ID)
data_loader.py  # json data-driven
data/*.json     # levels/characters/themes/shop (otomatik)
game.py         # tüm state, UI, HUD, ayarlar, tutorial + profil/online/vs
online.py       # TCP client (auto-connect, register/login/search)
bot.py          # Bilgisayara karşı BOT
SERVER/server.py # Gerçek server (SQLite)
```

**Test**
34 maddelik checklist otomatik testte 15/15 geçti (kamera, engel, gap, procedural, 5.8M, coin, mağaza, save, ses, performans, tutorial).
