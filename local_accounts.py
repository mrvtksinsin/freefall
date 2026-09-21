import json
import os
import secrets
import hashlib

# Hesap kapısı (HESAP OLUŞTUR / GİRİŞ YAP) artık tamamen çevrimdışıdır.
# Hesaplar yalnızca bu yerel dosyada tutulur (PBKDF2 hash + salt).
# ONLINE oyun bağlantısı bundan bağımsızdır ve sadece OYNA->ONLINE'da açılır.

_ACCOUNTS_PATH = os.path.join(os.path.dirname(__file__), "local_accounts.json")

_ITERATIONS = 120000


def _load():
    try:
        with open(_ACCOUNTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save(data):
    try:
        with open(_ACCOUNTS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LocalAccount] kaydetme hatasi: {e}")


def _hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", (password or "").encode("utf-8"), salt, _ITERATIONS
    ).hex()


def register(nickname, password):
    """Yerel hesap oluştur — sunucuya BAĞLANMAZ. (ok, err) döndürür."""
    data = _load()
    key = str(nickname or "").strip()
    if not key:
        return False, "Nickname gerekli"
    if key in data:
        return False, "Bu nickname zaten kayıtlı"
    salt = secrets.token_bytes(16)
    data[key] = {"salt": salt.hex(), "hash": _hash(password, salt)}
    _save(data)
    return True, "ok"


def login(identifier, password):
    """Yerel hesap girişi — sunucuya BAĞLANMAZ. (ok, err) döndürür."""
    data = _load()
    key = str(identifier or "").strip()
    rec = data.get(key)
    if not rec:
        return False, "Hesap bulunamadı"
    try:
        salt = bytes.fromhex(str(rec.get("salt") or ""))
        stored = str(rec.get("hash") or "")
    except Exception:
        return False, "Hesap verisi bozuk"
    if not salt or not stored:
        return False, "Hesap verisi bozuk"
    if _hash(password, salt) == stored:
        return True, "ok"
    return False, "Şifre hatalı"


def has_account(nickname):
    return str(nickname or "").strip() in _load()