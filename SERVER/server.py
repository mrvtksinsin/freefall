"""
FREEFALL Gerçek Server — SQLite + TCP (one-shot polling)
"""
import socket
import threading
import json
import sqlite3
import os
import random
import re
import time
import secrets
import base64
import hashlib
import hmac
from datetime import datetime

try:
    from config import SERVER_HOST, SERVER_PORT, DB_PATH, NICK_MIN, NICK_MAX
except ImportError:
    SERVER_HOST = "0.0.0.0"
    SERVER_PORT = 47822
    DB_PATH = os.path.join(os.path.dirname(__file__), "database", "players.db")
    NICK_MIN = 2
    NICK_MAX = 16

# Argon2id (varsa), değilse PBKDF2-HMAC-SHA256 fallback (master §15)
try:
    import argon2 as _argon2
except Exception:
    _argon2 = None

PBKDF2_ITER = 200000

DB_LOCK = threading.Lock()
LOBBY_LOCK = threading.Lock()

NICK_RE = re.compile(r"^[A-Za-z0-9_ÇĞİÖŞÜçğıöşü ]+$")

# Yeni hesabın temel oyun verisi (başlangıç)
GAME_DATA_DEFAULT = {
    "total_coins": 0,
    "best_distance": 0.0,
    "level": 1,
    "current_level": 1,
    "selected_character": "cop_adam",
    "selected_hat": None,
    "selected_bag": None,
    "selected_glasses": None,
    "selected_cane": None,
    "owned_items": [],
    "theme": "beyaz",
    "unlocked_characters": ["cop_adam"],
    "unlocked_levels": [1],
    "completed_levels": [],
    "level_stars": {},
    "final_completed": False,
}

invites = {}
lobbies = {}
lobby_counter = 0

def hash_password(password):
    """Şifreyi hash'le — Argon2id öncelikli, PBKDF2 fallback."""
    if _argon2 is not None:
        try:
            ph = _argon2.PasswordHasher()
            return "argon2id$" + ph.hash(str(password))
        except Exception:
            pass
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, PBKDF2_ITER)
    return "pbkdf2$" + base64.b64encode(salt).decode("ascii") + "$" + base64.b64encode(dk).decode("ascii")

def verify_password(password, stored):
    """Hash doğrula — argon2id / pbkdf2 biçimlerini anlar."""
    if not stored or not isinstance(stored, str):
        return False
    try:
        if stored.startswith("argon2id$"):
            if _argon2 is None:
                return False
            ph = _argon2.PasswordHasher()
            try:
                return ph.verify(stored.split("$", 1)[1], str(password))
            except Exception:
                return False
        if stored.startswith("pbkdf2$"):
            parts = stored.split("$")
            if len(parts) != 3:
                return False
            try:
                salt = base64.b64decode(parts[1])
                dk = base64.b64decode(parts[2])
            except Exception:
                return False
            dk2 = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, PBKDF2_ITER)
            return hmac.compare_digest(dk, dk2)
    except Exception:
        return False
    return False

def make_session_token():
    return secrets.token_hex(16)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_id TEXT PRIMARY KEY,
                nickname TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                online INTEGER DEFAULT 0
            )
        """)
        # migrasyon: hesap desteği (şifre + oturum + oyun verisi)
        try:
            conn.execute("ALTER TABLE players ADD COLUMN password_hash TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE players ADD COLUMN account_type TEXT DEFAULT 'legacy'")
        except Exception:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_data (
                player_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    print(f"[Server] DB hazır: {DB_PATH}", flush=True)

def get_game_data(pid):
    """Oyuncunun sunucu tarafı oyun verisi (server yetkili kaynak §23)."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT data FROM game_data WHERE player_id=?", (pid,))
        row = cur.fetchone()
        conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None

def create_session(pid):
    token = make_session_token()
    now = datetime.utcnow().isoformat()
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("DELETE FROM sessions WHERE player_id=?", (pid,))
        conn.execute("INSERT INTO sessions (token, player_id, created_at) VALUES (?,?,?)", (token, pid, now))
        conn.commit()
        conn.close()
    return token

def session_player_id(token):
    if not isinstance(token, str) or not token:
        return None
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT player_id FROM sessions WHERE token=?", (token,))
        row = cur.fetchone()
        conn.close()
    return row[0] if row else None

def is_valid_nick(nick):
    if not isinstance(nick, str):
        return False
    n = nick.strip()
    if len(n) < NICK_MIN or len(n) > NICK_MAX:
        return False
    return bool(NICK_RE.match(n))

def is_valid_id(pid):
    return isinstance(pid, str) and pid.isdigit() and len(pid) == 5

def generate_unique_id():
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            cur = conn.cursor()
            for _ in range(100):
                pid = f"{random.randint(10000, 99999):05d}"
                cur.execute("SELECT 1 FROM players WHERE player_id=?", (pid,))
                if not cur.fetchone():
                    return pid
        finally:
            try: conn.close()
            except: pass
    return f"{random.randint(10000, 99999):05d}"

def handle_client(conn, addr):
    print(f"[SERVER] Client connected: {addr[0]}:{addr[1]}", flush=True)
    try:
        conn.settimeout(5.0)
        data = b""
        while b"\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 8192:
                break
        if not data:
            print(f"[SERVER] Client disconnected: {addr[0]} (no data)", flush=True)
            return
        line = data.split(b"\n")[0].decode("utf-8").strip()
        if not line:
            print(f"[SERVER] Client disconnected: {addr[0]} (empty)", flush=True)
            return
        try:
            msg = json.loads(line)
        except:
            resp = {"ok": False, "error": "Geçersiz JSON"}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
            print(f"[SERVER] Request: INVALID_JSON from {addr[0]}", flush=True)
            return
        t = msg.get("type")
        print(f"[SERVER] Request: {t.upper() if t else 'UNKNOWN'} from {addr[0]}", flush=True)

        if t == "register":
            nick = str(msg.get("nickname", "")).strip()
            password = msg.get("password")
            is_account = isinstance(password, str) and len(password) > 0
            if is_account and len(password) < 4:
                resp = {"ok": False, "error": "Şifre en az 4 karakter olmalı"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            if not is_valid_nick(nick):
                resp = {"ok": False, "error": f"Nickname {NICK_MIN}-{NICK_MAX} karakter olmalı"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            pid = generate_unique_id()
            now = datetime.utcnow().isoformat()
            pwd_hash = hash_password(password) if is_account else ""
            acct_type = "account" if is_account else "legacy"
            with DB_LOCK:
                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                try:
                    conn_db.execute("INSERT INTO players (player_id, nickname, created_at, last_seen, online, password_hash, account_type) VALUES (?,?,?,?,1,?,?)", (pid, nick, now, now, pwd_hash, acct_type))
                    conn_db.commit()
                except sqlite3.IntegrityError:
                    pid = generate_unique_id()
                    conn_db.execute("INSERT INTO players (player_id, nickname, created_at, last_seen, online, password_hash, account_type) VALUES (?,?,?,?,1,?,?)", (pid, nick, now, now, pwd_hash, acct_type))
                    conn_db.commit()
                # yeni hesap için temel oyun verisi + oturum
                token = ""
                if is_account:
                    conn_db.execute("INSERT OR REPLACE INTO game_data (player_id, data, updated_at) VALUES (?,?,?)", (pid, json.dumps(GAME_DATA_DEFAULT), now))
                    conn_db.execute("DELETE FROM sessions WHERE player_id=?", (pid,))
                    token = make_session_token()
                    conn_db.execute("INSERT INTO sessions (token, player_id, created_at) VALUES (?,?,?)", (token, pid, now))
                    conn_db.commit()
                conn_db.close()
            print(f"[SERVER] Generated ID: {pid} for {nick}", flush=True)
            print(f"[SERVER] REGISTER {nick} -> {pid} ({addr[0]})", flush=True)
            resp = {"ok": True, "player_id": pid, "nickname": nick}
            if is_account:
                resp["token"] = token
                resp["game_data"] = dict(GAME_DATA_DEFAULT)
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "login":
            # Yeni hesap girişi: identifier (nickname VEYA player_id) + şifre
            if "identifier" in msg:
                ident = str(msg.get("identifier", "")).strip()
                password = str(msg.get("password", ""))
                if not ident:
                    resp = {"ok": False, "error": "Nickname veya Player ID gir"}
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    return
                if not password:
                    resp = {"ok": False, "error": "Şifre girin"}
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    return
                with DB_LOCK:
                    conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                    cur = conn_db.cursor()
                    row = None
                    if is_valid_id(ident):
                        cur.execute("SELECT player_id, nickname, created_at, last_seen, password_hash FROM players WHERE player_id=?", (ident,))
                        row = cur.fetchone()
                    if not row:
                        cur.execute("SELECT player_id, nickname, created_at, last_seen, password_hash FROM players WHERE nickname=? ORDER BY created_at DESC", (ident,))
                        row = cur.fetchone()
                    if not row:
                        conn_db.close()
                        resp = {"ok": False, "error": "Hesap bulunamadı"}
                        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                        return
                    stored_hash = row[4]
                    if not stored_hash:
                        conn_db.close()
                        resp = {"ok": False, "error": "Bu hesap şifresiz kayıtlı. HESAP OLUŞTUR ile tekrar kayıt ol."}
                        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                        return
                    if not verify_password(password, stored_hash):
                        conn_db.close()
                        resp = {"ok": False, "error": "Şifre hatalı"}
                        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                        return
                    now = datetime.utcnow().isoformat()
                    conn_db.execute("UPDATE players SET last_seen=?, online=1 WHERE player_id=?", (now, row[0]))
                    token = make_session_token()
                    conn_db.execute("DELETE FROM sessions WHERE player_id=?", (row[0],))
                    conn_db.execute("INSERT INTO sessions (token, player_id, created_at) VALUES (?,?,?)", (token, row[0], now))
                    conn_db.commit()
                    cur.execute("SELECT data FROM game_data WHERE player_id=?", (row[0],))
                    gd_row = cur.fetchone()
                    conn_db.close()
                try:
                    gd_data = json.loads(gd_row[0]) if gd_row else {}
                except Exception:
                    gd_data = {}
                if not isinstance(gd_data, dict):
                    gd_data = {}
                player = {"player_id": row[0], "nickname": row[1], "created_at": row[2], "last_seen": row[3]}
                print(f"[SERVER] ACCOUNT LOGIN ok: {row[1]} ({row[0]})", flush=True)
                resp = {"ok": True, "player": player, "token": token, "game_data": gd_data}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            # Eski protokol: player_id + (opsiyonel) nickname — şifresiz online olma
            pid = str(msg.get("player_id", "")).strip()
            nick = str(msg.get("nickname", "")).strip()
            if not is_valid_id(pid):
                resp = {"ok": False, "error": "ID 5 rakam olmalı"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            with DB_LOCK:
                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                cur = conn_db.cursor()
                cur.execute("SELECT nickname FROM players WHERE player_id=?", (pid,))
                row = cur.fetchone()
                if not row:
                    conn_db.close()
                    resp = {"ok": False, "error": "ID bulunamadı, yeniden kayıt olun"}
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    return
                if nick and nick != row[0] and is_valid_nick(nick):
                    cur.execute("UPDATE players SET nickname=?, last_seen=?, online=1 WHERE player_id=?", (nick, datetime.utcnow().isoformat(), pid))
                else:
                    cur.execute("UPDATE players SET last_seen=?, online=1 WHERE player_id=?", (datetime.utcnow().isoformat(), pid))
                conn_db.commit()
                cur.execute("SELECT player_id, nickname, created_at, last_seen FROM players WHERE player_id=?", (pid,))
                r2 = cur.fetchone()
                conn_db.close()
                player = {"player_id": r2[0], "nickname": r2[1], "created_at": r2[2], "last_seen": r2[3]}
            print(f"[SERVER] Login successful: {pid} ({player['nickname']})", flush=True)
            resp = {"ok": True, "player": player}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "logout":
            token = str(msg.get("token", "")).strip()
            with DB_LOCK:
                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                if token:
                    cur = conn_db.cursor()
                    cur.execute("SELECT player_id FROM sessions WHERE token=?", (token,))
                    row = cur.fetchone()
                    if row:
                        conn_db.execute("UPDATE players SET online=0 WHERE player_id=?", (row[0],))
                    conn_db.execute("DELETE FROM sessions WHERE token=?", (token,))
                    conn_db.commit()
                conn_db.close()
            print(f"[SERVER] Logout token ok", flush=True)
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "save_game_data":
            token = str(msg.get("token", "")).strip()
            pid = session_player_id(token)
            gd = msg.get("game_data")
            if not pid:
                resp = {"ok": False, "error": "Geçersiz oturum"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            if not isinstance(gd, dict):
                resp = {"ok": False, "error": "Geçersiz veri"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            try:
                data_str = json.dumps(gd, ensure_ascii=False)
            except Exception:
                resp = {"ok": False, "error": "Veri serileştirilemedi"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            if len(data_str.encode("utf-8")) > 262144:
                resp = {"ok": False, "error": "Veri çok büyük (max 256KB)"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            now = datetime.utcnow().isoformat()
            with DB_LOCK:
                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                conn_db.execute("INSERT OR REPLACE INTO game_data (player_id, data, updated_at) VALUES (?,?,?)", (pid, data_str, now))
                conn_db.execute("UPDATE players SET last_seen=?, online=1 WHERE player_id=?", (now, pid))
                conn_db.commit()
                conn_db.close()
            print(f"[SERVER] save_game_data {pid} ({len(data_str)} bytes)", flush=True)
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "load_game_data":
            token = str(msg.get("token", "")).strip()
            pid = session_player_id(token)
            if not pid:
                resp = {"ok": False, "error": "Geçersiz oturum"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            gd = get_game_data(pid)
            if gd is None:
                gd = dict(GAME_DATA_DEFAULT)
            resp = {"ok": True, "game_data": gd}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "search":
            target = str(msg.get("target_id", msg.get("id", ""))).strip()
            if not is_valid_id(target):
                resp = {"found": False, "error": "ID 5 rakam olmalı"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            with DB_LOCK:
                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                cur = conn_db.cursor()
                cur.execute("SELECT player_id, nickname, last_seen FROM players WHERE player_id=?", (target,))
                row = cur.fetchone()
                conn_db.close()
            print(f"[SERVER] Search: {target}", flush=True)
            if row:
                player = {"player_id": row[0], "nickname": row[1], "id": row[0], "nick": row[1], "last_seen": row[2]}
                resp = {"found": True, "player": player}
                print(f"[SERVER] SEARCH {target} -> FOUND {row[1]}", flush=True)
            else:
                resp = {"found": False, "error": "Bu ID ile oyuncu bulunamadı."}
                print(f"[SERVER] SEARCH {target} -> NOT FOUND", flush=True)
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "invite":
            from_id = str(msg.get("from_id", "")).strip()
            to_id = str(msg.get("to_id", "")).strip()
            if not is_valid_id(from_id) or not is_valid_id(to_id):
                resp = {"ok": False, "error": "ID 5 rakam olmalı"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            with DB_LOCK:
                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                cur = conn_db.cursor()
                cur.execute("SELECT nickname FROM players WHERE player_id=?", (from_id,))
                from_row = cur.fetchone()
                cur.execute("SELECT nickname FROM players WHERE player_id=?", (to_id,))
                to_row = cur.fetchone()
                conn_db.close()
            if not from_row or not to_row:
                resp = {"ok": False, "error": "Oyuncu bulunamadı."}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            invites[(from_id, to_id)] = {"from_nick": from_row[0], "timestamp": time.time()}
            print(f"[SERVER] INVITE {from_id} ({from_row[0]}) -> {to_id} ({to_row[0]})", flush=True)
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "get_invites":
            pid = str(msg.get("player_id", "")).strip()
            pending = []
            now = time.time()
            for (frm, to), info in list(invites.items()):
                if to == pid:
                    if now - info["timestamp"] > 60:
                        invites.pop((frm, to), None)
                    else:
                        pending.append({"from_id": frm, "from_nick": info["from_nick"]})
            resp = {"invites": pending}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "invite_accept":
            from_id = str(msg.get("from_id", "")).strip()
            to_id = str(msg.get("to_id", "")).strip()
            if (from_id, to_id) not in invites:
                resp = {"ok": False, "error": "Davet bulunamadı."}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            invites.pop((from_id, to_id), None)
            global lobby_counter
            with LOBBY_LOCK:
                # eski stale lobileri temizle (ayni oyunculari iceren)
                for lid in list(lobbies.keys()):
                    if from_id in lobbies[lid].get("players", []) or to_id in lobbies[lid].get("players", []):
                        lobbies.pop(lid, None)
                        print(f"[SERVER] Stale lobby {lid} cleaned before new", flush=True)
                lobby_counter += 1
                lobby_id = f"lobby_{lobby_counter}_{from_id}_{to_id}"
                lobbies[lobby_id] = {"players": [from_id, to_id], "ready": {from_id: False, to_id: False}, "host": from_id, "states": {}, "created": time.time()}
            print(f"[SERVER] Lobby created: {lobby_id} {from_id} + {to_id}", flush=True)
            resp = {"ok": True, "lobby_id": lobby_id, "players": [from_id, to_id]}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "invite_reject":
            from_id = str(msg.get("from_id", "")).strip()
            to_id = str(msg.get("to_id", "")).strip()
            invites.pop((from_id, to_id), None)
            print(f"[SERVER] Invite rejected: {from_id} -> {to_id}", flush=True)
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "get_lobby":
            pid = str(msg.get("player_id", "")).strip()
            found = None
            with LOBBY_LOCK:
                for lid, lob in lobbies.items():
                    if pid in lob["players"]:
                        found = {"lobby_id": lid, "players": lob["players"], "ready": lob["ready"]}
                        break
            resp = {"lobby": found}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "ready":
            lobby_id = str(msg.get("lobby_id", "")).strip()
            pid = str(msg.get("player_id", "")).strip()
            ready = bool(msg.get("ready", False))
            with LOBBY_LOCK:
                lobby = lobbies.get(lobby_id)
                if lobby and pid in lobby["players"]:
                    lobby["ready"][pid] = ready
                    print(f"[SERVER] READY {pid}={ready} in {lobby_id}", flush=True)
                    if all(lobby["ready"].values()) and len(lobby["players"]) == 2:
                        print(f"[SERVER] GAME_START {lobby_id}", flush=True)
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "check_game_start":
            lobby_id = str(msg.get("lobby_id", "")).strip()
            with LOBBY_LOCK:
                lobby = lobbies.get(lobby_id)
                if lobby and all(lobby["ready"].values()) and len(lobby["players"]) == 2:
                    resp = {"game_start": True, "lobby_id": lobby_id}
                else:
                    resp = {"game_start": False}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "lobby_leave":
            lobby_id = str(msg.get("lobby_id", "")).strip()
            pid = str(msg.get("player_id", "")).strip()
            with LOBBY_LOCK:
                lobby = lobbies.get(lobby_id)
                if lobby and pid in lobby["players"]:
                    lobbies.pop(lobby_id, None)
                    print(f"[SERVER] Lobby {lobby_id} left by {pid}, closed", flush=True)
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "player_state":
            lobby_id = str(msg.get("lobby_id", "")).strip()
            pid = str(msg.get("player_id", "")).strip()
            state = msg.get("state", {})
            with LOBBY_LOCK:
                lobby = lobbies.get(lobby_id)
                if lobby and pid in lobby["players"]:
                    if "states" not in lobby:
                        lobby["states"] = {}
                    lobby["states"][pid] = state
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "get_player_states":
            lobby_id = str(msg.get("lobby_id", "")).strip()
            pid = str(msg.get("player_id", "")).strip()
            with LOBBY_LOCK:
                lobby = lobbies.get(lobby_id)
                if lobby and "states" in lobby:
                    other_states = {k: v for k, v in lobby["states"].items() if k != pid}
                    resp = {"states": other_states}
                else:
                    resp = {"states": {}}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "heartbeat":
            pid = str(msg.get("player_id", "")).strip()
            if is_valid_id(pid):
                with DB_LOCK:
                    conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                    conn_db.execute("UPDATE players SET last_seen=?, online=1 WHERE player_id=?", (datetime.utcnow().isoformat(), pid))
                    conn_db.commit()
                    conn_db.close()
                resp = {"ok": True}
            else:
                resp = {"ok": False}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "disconnect":
            pid = str(msg.get("player_id", "")).strip()
            if is_valid_id(pid):
                with DB_LOCK:
                    conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                    conn_db.execute("UPDATE players SET online=0 WHERE player_id=?", (pid,))
                    conn_db.commit()
                    conn_db.close()
                # lobby cleanup: abrurt disconnectte lobiyi kapat, diger oyuncuyu kurtar
                with LOBBY_LOCK:
                    to_remove = [lid for lid, lob in lobbies.items() if pid in lob.get("players", [])]
                    for lid in to_remove:
                        lobbies.pop(lid, None)
                        print(f"[SERVER] Lobby {lid} closed due to disconnect {pid}", flush=True)
                # pending invite temizle
                for k in list(invites.keys()):
                    if pid in k:
                        invites.pop(k, None)
            resp = {"ok": True}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        else:
            resp = {"ok": False, "error": "Bilinmeyen type"}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

    except Exception as e:
        print(f"[SERVER] Error handling {addr}: {e}", flush=True)
        try:
            resp = {"ok": False, "error": str(e)}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
        except:
            pass
    finally:
        print(f"[SERVER] Client disconnected: {addr[0]}", flush=True)
        try:
            conn.close()
        except:
            pass

def main():
    init_db()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((SERVER_HOST, SERVER_PORT))
    except OSError as e:
        print(f"[Server] Bind hatası {SERVER_HOST}:{SERVER_PORT} -> {e}", flush=True)
        print("[Server] Başka bir server çalışıyor olabilir.", flush=True)
        return
    s.listen(64)
    print(f"[Server] FREEFALL Gerçek Server dinleniyor {SERVER_HOST}:{SERVER_PORT}", flush=True)
    print(f"[Server] DB: {DB_PATH}", flush=True)
    print(f"[Server] 5 haneli ID server tarafından üretiliyor (benzersiz)", flush=True)
    try:
        import socket as _s
        hn = _s.gethostname()
        lan = _s.gethostbyname(hn)
        print(f"[Server] LAN IP (tahmini): {lan} — diğer bilgisayarda CLIENT_HOST olarak kullanın", flush=True)
    except:
        pass
    print("[Server] Kapatmak için Ctrl+C", flush=True)
    while True:
        try:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[Server] Kapatılıyor...", flush=True)
            break
        except Exception as e:
            print(f"[Server] accept hatası: {e}", flush=True)

if __name__ == "__main__":
    main()
