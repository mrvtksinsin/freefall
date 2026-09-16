"""
FREEFALL Gerçek Server — SQLite + TCP
Çalıştır: python SERVER/server.py
Port: 47822 (SERVER/config.py)
Protokol: JSON satır (newline-delimited)
"""
import socket
import threading
import json
import sqlite3
import os
import random
import re
import time
from datetime import datetime

# Config
try:
    from config import SERVER_HOST, SERVER_PORT, DB_PATH, NICK_MIN, NICK_MAX
except ImportError:
    SERVER_HOST = "0.0.0.0"
    SERVER_PORT = 47822
    DB_PATH = os.path.join(os.path.dirname(__file__), "database", "players.db")
    NICK_MIN = 2
    NICK_MAX = 16

DB_LOCK = threading.Lock()

NICK_RE = re.compile(r"^[A-Za-z0-9_ÇĞİÖŞÜçğıöşü ]+$")

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
        conn.commit()
        conn.close()
    print(f"[Server] DB hazır: {DB_PATH}", flush=True)

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
        cur = conn.cursor()
        for _ in range(100):
            pid = f"{random.randint(10000, 99999):05d}"
            cur.execute("SELECT 1 FROM players WHERE player_id=?", (pid,))
            if not cur.fetchone():
                conn.close()
                return pid
        conn.close()
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
            if not is_valid_nick(nick):
                resp = {"ok": False, "error": f"Nickname {NICK_MIN}-{NICK_MAX} karakter olmalı"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                return
            pid = generate_unique_id()
            now = datetime.utcnow().isoformat()
            with DB_LOCK:
                conn_db = sqlite3.connect(DB_PATH, check_same_thread=False)
                try:
                    conn_db.execute("INSERT INTO players (player_id, nickname, created_at, last_seen, online) VALUES (?,?,?,?,1)", (pid, nick, now, now))
                    conn_db.commit()
                except sqlite3.IntegrityError:
                    pid = generate_unique_id()
                    conn_db.execute("INSERT INTO players (player_id, nickname, created_at, last_seen, online) VALUES (?,?,?,?,1)", (pid, nick, now, now))
                    conn_db.commit()
                conn_db.close()
            print(f"[SERVER] Generated ID: {pid} for {nick}", flush=True)
            print(f"[SERVER] REGISTER {nick} -> {pid} ({addr[0]})", flush=True)
            resp = {"ok": True, "player_id": pid, "nickname": nick}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        elif t == "login":
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
