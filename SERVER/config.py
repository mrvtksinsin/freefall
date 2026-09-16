import os

# FREEFALL Online Server Config — Merkezi ayar
# Client da bu dosyayı import eder (SERVER_HOST/PORT)

# Server dinleme adresi:
# - Aynı bilgisayarda test: 127.0.0.1
# - LAN'de başka bilgisayardan test: 0.0.0.0 (tüm interface) ve client'ta server IP'si
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 47822

# Client'ın bağlanacağı adres — oyun bu değeri kullanır
# Varsayılan 127.0.0.1 (tek PC test). LAN'de iki PC için server IP'sini
# ortam değişkeni ile ver: set FREEFALL_SERVER_IP=192.168.1.91 (Windows)
# veya Linux/macOS: export FREEFALL_SERVER_IP=192.168.1.91
# Kod bozulmadan GitHub'a kişisel IP gitmez.
CLIENT_HOST = os.environ.get("FREEFALL_SERVER_IP", "127.0.0.1")
CLIENT_PORT = 47822
# Kolay alias — iki isim de aynı anlama gelir
SERVER_IP = CLIENT_HOST

# Database
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "database", "players.db")

# Validation
NICK_MIN = 2
NICK_MAX = 16
PLAYER_ID_LEN = 5
