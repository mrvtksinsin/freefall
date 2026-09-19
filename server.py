"""
FREEFALL Online Sunucu - Hesap + Session + Server-Authoritative Game Data
Aktif root server - freefall/server.py
Port: 47822
Protokol: JSON satir (newline)
"""
import socket
import threading
import json
import time
import random
import sqlite3
import os
import hashlib
import secrets
import re
from datetime import datetime, timedelta

HOST = "0.0.0.0"
PORT = 47822

# Legacy registry (file-based) for backward compat
REGISTRY = {}
SESSIONS = {}
REG_LOCK = threading.Lock()
SESSION_LOCK = threading.Lock()

# New SQLite DB for accounts
DB_PATH = os.path.join(os.path.dirname(__file__), "accounts.db")
DB_LOCK = threading.Lock()

# Try Argon2id, fallback to PBKDF2
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    _ph = PasswordHasher(time_cost=2, memory_cost=102400, parallelism=8)
    def hash_password(pw: str) -> str:
        return _ph.hash(pw)
    def verify_password(stored: str, pw: str) -> bool:
        try:
            _ph.verify(stored, pw)
            return True
        except:
            return False
    print("[Server] Argon2id aktif", flush=True)
except ImportError:
    def hash_password(pw: str) -> str:
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), 120000)
        return f"pbkdf2${salt}${dk.hex()}"
    def verify_password(stored: str, pw: str) -> bool:
        try:
            if stored.startswith("pbkdf2$"):
                _, salt, h = stored.split("$", 2)
                dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), 120000)
                return secrets.compare_digest(dk.hex(), h)
            # legacy argon without prefix? try pbkdf2 fallback
            return False
        except:
            return False
    print("[Server] PBKDF2 fallback aktif", flush=True)

NICK_RE = re.compile(r"^[A-Za-z0-9_]+$")  # auto nickname user_xxxxxx only

def is_valid_password(pw: str) -> bool:
    return isinstance(pw, str) and 3 <= len(pw) <= 32

def generate_nickname():
    for _ in range(100):
        nick = f"user_{random.randint(100000, 999999):06d}"
        # check not taken and not deleted
        with DB_LOCK:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM accounts WHERE nickname=? AND deleted=0", (nick,))
            exists = cur.fetchone()
            conn.close()
        if not exists:
            return nick
    return f"user_{random.randint(100000, 999999):06d}"

def generate_player_id():
    for _ in range(100):
        pid = f"{random.randint(10000, 99999):05d}"
        with DB_LOCK:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM accounts WHERE player_id=?", (pid,))
            if not cur.fetchone() and pid not in REGISTRY:
                conn.close()
                return pid
            conn.close()
    return f"{random.randint(10000, 99999):05d}"

def default_game_data():
    return {
        "level": 1,
        "current_level": 1,
        "unlocked_levels": [1],
        "completed_levels": [],
        "level_stars": {},
        "unlocked_characters": ["cop_adam"],
        "selected_character": "cop_adam",
        "total_coins": 0,
        "best_distance": 0.0,
        "owned_items": [],
        "selected_hat": None,
        "selected_bag": None,
        "selected_glasses": None,
        "selected_cane": None,
        "theme": "beyaz",
        "settings": {"master": 0.7, "music": 0.5, "sfx": 0.8, "show_tutorial": True},
        "final_completed": False
    }

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                player_id TEXT PRIMARY KEY,
                nickname TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                deleted INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_data (
                player_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # legacy players table migration: if exists, keep
        conn.commit()
        conn.close()
    print(f"[Server] DB hazır: {DB_PATH}", flush=True)
    # legacy registry load
    try:
        with open("online_registry.json","r",encoding="utf-8") as f:
            data = json.load(f)
            for k,v in data.items():
                REGISTRY[k]=v
        print(f"[Server] legacy registry yüklendi {len(REGISTRY)}", flush=True)
    except:
        pass

def save_registry():
    try:
        with open("online_registry.json","w",encoding="utf-8") as f:
            json.dump(REGISTRY, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[Server] save fail",e)

def create_session(player_id: str) -> str:
    token = secrets.token_hex(32)
    now = datetime.utcnow()
    exp = now + timedelta(days=30)
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("INSERT INTO sessions (token, player_id, created_at, expires_at, revoked) VALUES (?,?,?,?,0)", (token, player_id, now.isoformat(), exp.isoformat()))
        conn.commit()
        conn.close()
    return token

def verify_session(player_id: str, token: str) -> bool:
    if not token or not player_id:
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT player_id, expires_at, revoked FROM sessions WHERE token=?", (token,))
        row = cur.fetchone()
        conn.close()
    if not row: return False
    pid, exp, rev = row
    if rev: return False
    if pid != player_id: return False
    try:
        exp_dt = datetime.fromisoformat(exp)
        if datetime.utcnow() > exp_dt:
            return False
    except:
        return False
    return True

def get_account_summary(player_id: str):
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT nickname, created_at FROM accounts WHERE player_id=? AND deleted=0", (player_id,))
        acc = cur.fetchone()
        if not acc:
            conn.close()
            return None
        nickname, created_at = acc
        cur.execute("SELECT data FROM game_data WHERE player_id=?", (player_id,))
        row = cur.fetchone()
        conn.close()
    data = json.loads(row[0]) if row else default_game_data()
    return {
        "player_id": player_id,
        "nickname": nickname,
        "created_at": created_at,
        "level": data.get("level",1),
        "current_level": data.get("current_level",1),
        "total_coins": data.get("total_coins",0),
        "unlocked_characters": data.get("unlocked_characters", ["cop_adam"]),
        "unlocked_levels": data.get("unlocked_levels", [1]),
        "game_data": data
    }

def handle_client(conn, addr):
    try:
        conn.settimeout(4.0)
        buf = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n",1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except:
                    resp = {"ok": False, "error": "Geçersiz JSON"}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                t = msg.get("type")
                # ---- ACCOUNT GATE ----
                if t == "account_register":
                    pw = str(msg.get("password",""))
                    pw2 = str(msg.get("password2", msg.get("password_repeat", pw)))
                    # nickname auto generate
                    if not is_valid_password(pw):
                        resp={"ok":False,"error":"Şifre 3-32 karakter olmalı"}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    if pw != pw2:
                        resp={"ok":False,"error":"Şifreler eşleşmiyor"}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    nick = generate_nickname()
                    pid = generate_player_id()
                    phash = hash_password(pw)
                    now = datetime.utcnow().isoformat()
                    with DB_LOCK:
                        conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                        # ensure nickname not taken (retry)
                        for _ in range(5):
                            try:
                                conn_db.execute("INSERT INTO accounts (player_id, nickname, password_hash, created_at, deleted) VALUES (?,?,?,?,0)", (pid, nick, phash, now))
                                break
                            except sqlite3.IntegrityError:
                                pid = generate_player_id()
                                nick = generate_nickname()
                        # game_data default
                        conn_db.execute("INSERT OR IGNORE INTO game_data (player_id, data, updated_at) VALUES (?,?,?)", (pid, json.dumps(default_game_data(), ensure_ascii=False), now))
                        conn_db.commit()
                        conn_db.close()
                    token = create_session(pid)
                    summary = get_account_summary(pid)
                    print(f"[Server] ACCOUNT_REGISTER {nick} -> {pid} ({addr[0]})", flush=True)
                    resp={"ok":True,"player_id":pid,"nickname":nick,"session_token":token,"game_data":summary["game_data"]}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "account_login":
                    login = str(msg.get("login", msg.get("player_id", msg.get("nickname","")))).strip()
                    pw = str(msg.get("password",""))
                    # allow login via nickname or player_id
                    if not login or not is_valid_password(pw):
                        resp={"ok":False,"error":"ID veya şifre hatalı."}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    with DB_LOCK:
                        conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                        cur = conn_db.cursor()
                        # try player_id first, then nickname
                        cur.execute("SELECT player_id, nickname, password_hash FROM accounts WHERE (player_id=? OR LOWER(nickname)=LOWER(?)) AND deleted=0", (login, login))
                        row = cur.fetchone()
                        conn_db.close()
                    if not row:
                        resp={"ok":False,"error":"ID veya şifre hatalı."}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    pid_db, nick_db, phash = row
                    if not verify_password(phash, pw):
                        resp={"ok":False,"error":"ID veya şifre hatalı."}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    token = create_session(pid_db)
                    summary = get_account_summary(pid_db)
                    print(f"[Server] ACCOUNT_LOGIN {nick_db} -> {pid_db} ({addr[0]})", flush=True)
                    resp={"ok":True,"player_id":pid_db,"nickname":nick_db,"session_token":token,"game_data":summary["game_data"]}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "guest":
                    nick = f"guest_{random.randint(100000,999999):06d}"
                    pid = f"guest_{random.randint(10000,99999):05d}"
                    print(f"[Server] GUEST {nick} -> {pid} ({addr[0]})", flush=True)
                    resp={"ok":True,"player_id":pid,"nickname":nick,"guest":True,"session_token":None,"game_data":default_game_data()}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "session_check":
                    pid = str(msg.get("player_id","")).strip()
                    token = str(msg.get("session_token", msg.get("token",""))).strip()
                    if verify_session(pid, token):
                        summary = get_account_summary(pid)
                        resp={"ok":True,"valid":True,"player_id":pid,"nickname":summary["nickname"] if summary else "","game_data":summary["game_data"] if summary else None}
                    else:
                        resp={"ok":True,"valid":False}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "get_game_data":
                    pid = str(msg.get("player_id","")).strip()
                    token = str(msg.get("session_token","")).strip()
                    if not verify_session(pid, token):
                        resp={"ok":False,"error":"Oturum geçersiz"}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    summary = get_account_summary(pid)
                    resp={"ok":True,"game_data":summary["game_data"] if summary else default_game_data()}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "save_game_data":
                    pid = str(msg.get("player_id","")).strip()
                    token = str(msg.get("session_token","")).strip()
                    data = msg.get("game_data")
                    if not verify_session(pid, token):
                        resp={"ok":False,"error":"Oturum geçersiz"}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    if not isinstance(data, dict):
                        resp={"ok":False,"error":"Geçersiz game_data"}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    with DB_LOCK:
                        conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                        conn_db.execute("INSERT OR REPLACE INTO game_data (player_id, data, updated_at) VALUES (?,?,?)", (pid, json.dumps(data, ensure_ascii=False), datetime.utcnow().isoformat()))
                        conn_db.commit()
                        conn_db.close()
                    resp={"ok":True}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "logout":
                    pid = str(msg.get("player_id","")).strip()
                    token = str(msg.get("session_token", msg.get("token",""))).strip()
                    if token:
                        with DB_LOCK:
                            conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                            conn_db.execute("UPDATE sessions SET revoked=1 WHERE token=?", (token,))
                            conn_db.commit()
                            conn_db.close()
                    elif pid:
                        with DB_LOCK:
                            conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                            conn_db.execute("UPDATE sessions SET revoked=1 WHERE player_id=?", (pid,))
                            conn_db.commit()
                            conn_db.close()
                    print(f"[Server] LOGOUT {pid} ({addr[0]})", flush=True)
                    resp={"ok":True}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "delete_account":
                    pid = str(msg.get("player_id","")).strip()
                    pw = str(msg.get("password",""))
                    token = str(msg.get("session_token","")).strip()
                    # require valid session and password
                    if not verify_session(pid, token):
                        resp={"ok":False,"error":"Oturum geçersiz"}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    with DB_LOCK:
                        conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                        cur = conn_db.cursor()
                        cur.execute("SELECT password_hash FROM accounts WHERE player_id=? AND deleted=0", (pid,))
                        row = cur.fetchone()
                        if not row or not verify_password(row[0], pw):
                            conn_db.close()
                            resp={"ok":False,"error":"ID veya şifre hatalı."}
                            conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                            continue
                        # soft delete account, free nickname
                        cur.execute("UPDATE accounts SET deleted=1 WHERE player_id=?", (pid,))
                        cur.execute("DELETE FROM game_data WHERE player_id=?", (pid,))
                        cur.execute("UPDATE sessions SET revoked=1 WHERE player_id=?", (pid,))
                        conn_db.commit()
                        conn_db.close()
                    print(f"[Server] DELETE_ACCOUNT {pid} ({addr[0]})", flush=True)
                    resp={"ok":True}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "account_summary":
                    pid = str(msg.get("player_id","")).strip()
                    token = str(msg.get("session_token","")).strip()
                    if not verify_session(pid, token):
                        resp={"ok":False,"error":"Oturum geçersiz"}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    summary = get_account_summary(pid)
                    if not summary:
                        resp={"ok":False,"error":"Hesap bulunamadı"}
                    else:
                        resp={"ok":True,"summary":summary}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                # ---- legacy ----
                if t == "register":
                    nick = str(msg.get("nickname", msg.get("nick", msg.get("name","")))).strip()
                    char = str(msg.get("char","cop_adam"))
                    if len(nick)<2 or len(nick)>16:
                        resp={"ok":False,"error":"Nick 2-16 karakter olmalı"}
                    else:
                        with REG_LOCK:
                            for _ in range(100):
                                pid = f"{random.randint(10000, 99999):05d}"
                                if pid not in REGISTRY:
                                    break
                            else:
                                pid = f"{random.randint(10000, 99999):05d}"
                            REGISTRY[pid]={"nick":nick,"id":pid,"char":char,"last_seen": time.time(), "player_id": pid, "nickname": nick}
                            save_registry()
                            resp={"ok":True,"player_id":pid,"nickname":nick,"id":pid}
                        print(f"[Server] REGISTER {nick} -> {pid} ({addr[0]})", flush=True)
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "search":
                    pid = str(msg.get("target_id", msg.get("id",""))).strip()
                    # first check new accounts
                    with DB_LOCK:
                        conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                        cur = conn_db.cursor()
                        cur.execute("SELECT player_id, nickname FROM accounts WHERE player_id=? AND deleted=0", (pid,))
                        row = cur.fetchone()
                        conn_db.close()
                    if row:
                        player={"player_id":row[0],"nickname":row[1],"id":row[0],"nick":row[1]}
                        resp={"found":True,"player":player}
                        conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                        continue
                    with REG_LOCK:
                        found = pid in REGISTRY
                        player = REGISTRY.get(pid)
                        if player and "nick" not in player and "nickname" in player:
                            player=dict(player); player["nick"]=player["nickname"]
                        if player and "id" not in player and "player_id" in player:
                            player=dict(player); player["id"]=player["player_id"]
                    if found:
                        resp={"found":True,"player": player}
                    else:
                        resp={"found":False, "error":"Bu ID ile oyuncu bulunamadı."}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "match":
                    from_id = str(msg.get("from_id","")).strip()
                    to_id = str(msg.get("to_id","")).strip()
                    with REG_LOCK:
                        if from_id not in REGISTRY:
                            # also check DB
                            with DB_LOCK:
                                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                                cur = conn_db.cursor()
                                cur.execute("SELECT 1 FROM accounts WHERE player_id=? AND deleted=0", (from_id,))
                                f1=cur.fetchone()
                                cur.execute("SELECT 1 FROM accounts WHERE player_id=? AND deleted=0", (to_id,))
                                f2=cur.fetchone()
                                conn_db.close()
                            if not f1 or not f2:
                                resp={"ok":False,"error":"Oyuncu bulunamadı"}
                                conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                                continue
                        elif to_id not in REGISTRY:
                            resp={"ok":False,"error":"Oyuncu bulunamadı"}
                            conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                            continue
                    sess = f"sess_{from_id}_{to_id}_{int(time.time())}"
                    with SESSION_LOCK:
                        SESSIONS[sess]={"p1":from_id,"p2":to_id,"states":{}}
                    resp={"ok":True,"session_id": sess}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                elif t == "sync":
                    pid = str(msg.get("id","")).strip()
                    sess = str(msg.get("session",""))
                    state = msg.get("state",{})
                    with SESSION_LOCK:
                        sess_obj = SESSIONS.get(sess)
                        if sess_obj:
                            sess_obj["states"][pid]= state
                            other = sess_obj["p2"] if sess_obj["p1"]==pid else sess_obj["p1"]
                            other_state = sess_obj["states"].get(other, {})
                            resp={"state": other_state}
                        else:
                            resp={"state":{}}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
                else:
                    resp={"ok":False,"error":"Bilinmeyen type"}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    continue
    except Exception as e:
        print(f"[Server] Error {addr}: {e}", flush=True)
        try:
            resp={"ok":False,"error":str(e)}
            conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
        except: pass
    finally:
        try: conn.close()
        except: pass

def main():
    init_db()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(64)
    print(f"[Server] FREEFALL listening {HOST}:{PORT}", flush=True)
    print(f"[Server] 5 haneli ID + Argon2/PBKDF2 + session + server-authoritative", flush=True)
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn,addr), daemon=True).start()

if __name__ == "__main__":
    main()
