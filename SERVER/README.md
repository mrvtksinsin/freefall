# FREEFALL — Gerçek Server

Gerçek TCP + SQLite server. Client'ın ID'sini **server üretir** (5 rakam, benzersiz).

## Dosya Yapısı
```
SERVER/
  server.py        # Gerçek server (SQLite)
  config.py        # HOST/PORT/DB_PATH
  database/
    players.db     # SQLite (otomatik oluşur)
  requirements.txt
  README.md
```

## Çalıştırma

### 1. Bağımlılık
Ek bağımlılık yok (sadece Python 3 stdlib).

```bash
pip install -r requirements.txt  # boş, opsiyonel
```

### 2. Server'ı Başlat
```bash
# Proje kökünden:
python SERVER/server.py
# veya SERVER klasöründen:
cd SERVER
python server.py
```

Çıktı:
```
[Server] DB hazır: .../database/players.db
[Server] FREEFALL Gerçek Server dinleniyor 0.0.0.0:47822
[Server] LAN IP (tahmini): 192.168.1.20
```

### 3. Aynı Bilgisayarda Test (Local)
- Oyunu aç: `python main.py`
- İlk açılışta Nick gir → `OLUŞTUR` → ana menü (henüz ID yok, server gerekmez)
- `OYNA` → `ONLINE` → server bağlanır → ilk kez ID oluşturulur (örn: 58321) → `Merve ID:58321` görünür, `● Sunucuya bağlı`
- İkinci client (aynı PC'de ikinci oyun penceresi) farklı nick ile kayıt olur, `OYUNCU ARA` → `58321` yaz → server bulur → Nick gösterilir.

### 4. İki Bilgisayarda Test (LAN)
1. Server bilgisayarında `python SERVER/server.py` çalıştır
2. Server konsolundaki `LAN IP` not et (örn: `192.168.1.20`)
3. **Her iki bilgisayarda** `SERVER/config.py` içindeki `CLIENT_HOST` değerini server IP'si yap:
   ```python
   CLIENT_HOST = "192.168.1.20"
   ```
4. İki bilgisayarda da `python main.py` aç
5. Her biri Nick oluşturur (server farklı 5 haneli ID verir)
6. B bilgisayarı → `OYNA` → `ONLINE` → A'nın ID'sini gir → `OYUNCU ARA`

### 5. Hata Durumları
- **Geçersiz ID (5 rakam değil):** “ID 5 rakam olmalı”
- **Kendi ID:** “Kendi ID'nizi giremezsiniz”
- **Bulunamadı:** “Bu ID ile çevrimiçi bir oyuncu bulunamadı.”
- **Server kapalı:** “Sunucuya bağlanılamadı.” (oyun çökmez, BÖLÜMLER çalışır)

## Protokol (JSON satır)
- `register {nickname}` → `{ok, player_id}`
- `login {player_id}` → `{ok, player}`
- `search {target_id}` → `{found, player}`
- `heartbeat {player_id}`

## Not
- `BÖLÜMLER` modu server'dan bağımsız, offline çalışır.
- Bu aşama sadece ID arama testidir; yarış eşleşmesi sonraki aşamada.
