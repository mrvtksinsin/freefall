import socket
import json
import threading
import time

# Merkezi config — SERVER/config.py
try:
    from SERVER.config import CLIENT_HOST, CLIENT_PORT
    DEFAULT_HOST = CLIENT_HOST
    DEFAULT_PORT = CLIENT_PORT
except:
    try:
        import os, sys
        # fallback: SERVER/config.py'yi dinamik yükle
        import importlib.util
        cfg_path = os.path.join(os.path.dirname(__file__), "SERVER", "config.py")
        if os.path.exists(cfg_path):
            spec = importlib.util.spec_from_file_location("server_cfg", cfg_path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            DEFAULT_HOST = getattr(m, "CLIENT_HOST", "127.0.0.1")
            DEFAULT_PORT = getattr(m, "CLIENT_PORT", 47822)
        else:
            DEFAULT_HOST = "127.0.0.1"
            DEFAULT_PORT = 47822
    except:
        DEFAULT_HOST = "127.0.0.1"
        DEFAULT_PORT = 47822

def is_valid_id(pid):
    return isinstance(pid, str) and pid.isdigit() and len(pid) == 5

class OnlineManager:
    def __init__(self, save):
        self.save = save
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT
        self.connected = False
        self.last_error = ""
        self.opponent_info = None
        self.session_id = None
        self._sock = None
        self._remote_state = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._online_status = False  # sunucuya bağlı mı
        # Persistent lobby/invite
        self._persistent_sock = None
        self._persistent_thread = None
        self._persistent_running = False
        self._persistent_buf = b""
        self._pending_invites = []
        self._lobby = None
        self._game_start_lobby = None
        self._lobby_updates = []
        self._remote_states = {}
        self._invite_rejects = []

    def _connect(self, timeout=1.5):
        try:
            print(f"[CLIENT] Connecting to {self.host}:{self.port} ...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((self.host, self.port))
            s.settimeout(None)
            self._sock = s
            self.connected = True
            print(f"[CLIENT] Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[CLIENT] Connection failed {self.host}:{self.port} -> {e}")
            self.last_error = str(e)
            self.connected = False
            return False

    def _send_json(self, obj):
        if not self._sock:
            return False
        try:
            data = json.dumps(obj, ensure_ascii=False) + "\n"
            self._sock.sendall(data.encode("utf-8"))
            return True
        except Exception as e:
            self.last_error = str(e)
            self.connected = False
            return False

    def _recv_line(self, timeout=2.0):
        if not self._sock:
            return None
        try:
            self._sock.settimeout(timeout)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    break
            if not buf:
                return None
            line = buf.split(b"\n")[0].decode("utf-8").strip()
            if not line:
                return None
            return json.loads(line)
        except Exception as e:
            self.last_error = str(e)
            return None
        finally:
            try: self._sock.settimeout(None)
            except: pass

    # --- Yeni protokol: server ID üretir ---
    def register_new(self, nickname):
        """Yeni oyuncu kaydı — server 5 haneli ID üretir."""
        nick = str(nickname).strip()
        print(f"[CLIENT] REGISTER request for '{nick}'")
        if len(nick) < 2 or len(nick) > 16:
            return False, "Nickname 2-16 karakter olmalı"
        if not self._connect(timeout=2.0):
            print(f"[CLIENT] REGISTER failed: Sunucuya bağlanılamadı.")
            return False, "Sunucuya bağlanılamadı."
        ok = self._send_json({"type": "register", "nickname": nick})
        if not ok:
            try: self._sock.close()
            except: pass
            return False, "Gönderim hatası"
        resp = self._recv_line(timeout=2.0)
        try: self._sock.close()
        except: pass
        self.connected=False
        if not resp:
            print(f"[CLIENT] REGISTER no response")
            return False, "Sunucudan yanıt yok"
        print(f"[CLIENT] REGISTER response: {resp}")
        if resp.get("ok") and resp.get("player_id"):
            pid = str(resp["player_id"])
            if is_valid_id(pid):
                print(f"[CLIENT] Generated ID: {pid} for {nick}")
                # save'e yaz
                self.save["nickname"] = nick
                self.save["player_id"] = pid
                # kalıcı kaydet (save_system'e bırakacağız ama burada da dene)
                try:
                    import save_system
                    save_system.save_game(self.save)
                except: pass
                self._online_status = True
                return True, pid
            else:
                print(f"[CLIENT] Invalid ID from server: {pid}")
                return False, "Server geçersiz ID üretti"
        print(f"[CLIENT] REGISTER failed: {resp}")
        return False, resp.get("error", "Kayıt hatası")

    def login(self):
        """Var olan ID ile giriş — online ol."""
        pid = str(self.save.get("player_id","")).strip()
        nick = str(self.save.get("nickname","")).strip()
        print(f"[CLIENT] LOGIN {pid} ({nick})")
        if not is_valid_id(pid):
            return False, "Geçersiz ID"
        if not self._connect(timeout=1.5):
            print(f"[CLIENT] LOGIN failed: Sunucuya bağlanılamadı.")
            self._online_status=False
            return False, "Sunucuya bağlanılamadı."
        self._send_json({"type":"login","player_id":pid,"nickname":nick})
        resp=self._recv_line(timeout=1.5)
        try: self._sock.close()
        except: pass
        self.connected=False
        if resp and resp.get("ok"):
            print(f"[CLIENT] Login successful: {pid}")
            self._online_status=True
            return True, "ok"
        print(f"[CLIENT] Login failed: {resp}")
        self._online_status=False
        return False, resp.get("error","Giriş hatası") if resp else "Sunucudan yanıt yok"

    def check_connection(self):
        """Online mı?"""
        # heartbeat deneyerek kontrol
        pid=str(self.save.get("player_id","")).strip()
        if not is_valid_id(pid):
            self._online_status=False
            return False
        if not self._connect(timeout=0.9):
            self._online_status=False
            return False
        self._send_json({"type":"heartbeat","player_id":pid})
        resp=self._recv_line(timeout=0.9)
        try: self._sock.close()
        except: pass
        self.connected=False
        ok = bool(resp and resp.get("ok"))
        self._online_status=ok
        return ok

    def is_online(self):
        return self._online_status

    # --- Persistent bağlantı: lobby/invite için ---
    def connect_persistent(self):
        """ONLINE ekranında kalıcı bağlantı — invite/lobby için."""
        if self._persistent_sock:
            try: self._persistent_sock.close()
            except: pass
            self._persistent_sock = None
        pid = str(self.save.get("player_id","")).strip()
        nick = str(self.save.get("nickname","")).strip()
        if not is_valid_id(pid):
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            s.settimeout(None)
            # login üzerinden persistent
            s.sendall((json.dumps({"type":"login","player_id":pid,"nickname":nick}) + "\n").encode("utf-8"))
            # short read for login response (2s)
            s.settimeout(2.0)
            buf=b""
            while b"\n" not in buf:
                chunk=s.recv(4096)
                if not chunk: break
                buf+=chunk
                if len(buf)>8192: break
            s.settimeout(None)
            if not buf:
                s.close()
                return False
            line=buf.split(b"\n")[0].decode("utf-8").strip()
            resp=json.loads(line) if line else {}
            if not resp.get("ok"):
                s.close()
                return False
            self._persistent_sock = s
            self._online_status = True
            self._persistent_running = True
            # listener thread
            self._persistent_thread = threading.Thread(target=self._persistent_listener, daemon=True)
            self._persistent_thread.start()
            # leftover buffer handling
            self._persistent_buf = buf.split(b"\n",1)[1] if b"\n" in buf else b""
            print(f"[CLIENT] Persistent connected {pid}", flush=True)
            return True
        except Exception as e:
            print(f"[CLIENT] Persistent failed: {e}")
            try: s.close()
            except: pass
            return False

    def _persistent_listener(self):
        buf = getattr(self, "_persistent_buf", b"")
        s = self._persistent_sock
        if not s:
            return
        s.settimeout(30.0)
        # extra state
        if not hasattr(self, "_pending_invites"):
            self._pending_invites = []
        if not hasattr(self, "_lobby"):
            self._lobby = None
        if not hasattr(self, "_game_start_lobby"):
            self._game_start_lobby = None
        if not hasattr(self, "_lobby_updates"):
            self._lobby_updates = []
        if not hasattr(self, "_remote_states"):
            self._remote_states = {}
        while self._persistent_running and s:
            try:
                # read line
                while b"\n" not in buf:
                    chunk = s.recv(4096)
                    if not chunk:
                        raise ConnectionError("closed")
                    buf += chunk
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                msg = json.loads(line.decode("utf-8"))
                t = msg.get("type")
                print(f"[CLIENT] Persistent recv: {t}", flush=True)
                if t == "invite":
                    # server -> us: someone invited us
                    with self._lock:
                        if not hasattr(self, "_pending_invites"):
                            self._pending_invites = []
                        self._pending_invites.append({"from_id": msg.get("from_id"), "from_nick": msg.get("from_nick")})
                elif t == "lobby_joined":
                    with self._lock:
                        self._lobby = {"lobby_id": msg.get("lobby_id"), "players": msg.get("players", []), "ready": {p: False for p in msg.get("players", [])}}
                        self._game_start_lobby = None
                elif t == "lobby_update":
                    with self._lock:
                        if self._lobby and self._lobby.get("lobby_id")==msg.get("lobby_id"):
                            self._lobby["ready"] = msg.get("ready", {})
                        else:
                            self._lobby = {"lobby_id": msg.get("lobby_id"), "players": msg.get("players", []), "ready": msg.get("ready", {})}
                elif t == "game_start":
                    with self._lock:
                        self._game_start_lobby = msg.get("lobby_id")
                elif t == "player_state":
                    pid = msg.get("player_id")
                    state = msg.get("state", {})
                    with self._lock:
                        if not hasattr(self, "_remote_states"):
                            self._remote_states = {}
                        self._remote_states[pid] = state
                elif t == "invite_reject":
                    with self._lock:
                        if not hasattr(self, "_invite_rejects"):
                            self._invite_rejects = []
                        self._invite_rejects.append(msg)
                elif t == "lobby_leave" or t == "player_leave":
                    with self._lock:
                        self._lobby = None
                        self._game_start_lobby = None
                # heartbeat ack etc ignore
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[CLIENT] Persistent error: {e}")
                break
        print(f"[CLIENT] Persistent disconnected", flush=True)
        self._online_status = False
        try:
            if s:
                s.close()
        except: pass
        self._persistent_sock = None

    def disconnect_persistent(self):
        self._persistent_running = False
        if self._persistent_sock:
            try: self._persistent_sock.close()
            except: pass
            self._persistent_sock = None

    # Eski register (client ID gönderirdi) artık kullanılmıyor — geriye dönük stub
    def register(self):
        # Artık register_new kullanılmalı
        pid=str(self.save.get("player_id",""))
        nick=str(self.save.get("nickname",""))
        if is_valid_id(pid):
            return self.login()
        return self.register_new(nick)

    def send_invite(self, to_id):
        """A -> B davet gönder."""
        from_id = str(self.save.get("player_id","")).strip()
        to_id = str(to_id).strip()
        if not is_valid_id(from_id) or not is_valid_id(to_id):
            return False, "Geçersiz ID"
        if not self._connect(timeout=1.4):
            return False, "Sunucuya bağlanılamadı."
        self._send_json({"type":"invite","from_id":from_id,"to_id":to_id})
        resp=self._recv_line(timeout=1.4)
        try: self._sock.close()
        except: pass
        self.connected=False
        if resp and resp.get("ok"):
            print(f"[CLIENT] INVITE {from_id}->{to_id} ok")
            return True, "ok"
        return False, resp.get("error","Davet gönderilemedi.") if resp else "Sunucuya bağlanılamadı."

    def accept_invite(self, from_id):
        to_id=str(self.save.get("player_id","")).strip()
        from_id=str(from_id).strip()
        if not self._connect(timeout=1.4):
            return False, "Sunucuya bağlanılamadı."
        self._send_json({"type":"invite_accept","from_id":from_id,"to_id":to_id})
        resp=self._recv_line(timeout=1.4)
        try: self._sock.close()
        except: pass
        self.connected=False
        if resp and resp.get("ok"):
            return True, resp.get("lobby_id","")
        return False, resp.get("error","") if resp else "Sunucuya bağlanılamadı."

    def reject_invite(self, from_id):
        to_id=str(self.save.get("player_id","")).strip()
        from_id=str(from_id).strip()
        if not self._connect(timeout=1.4):
            return False, "Sunucuya bağlanılamadı."
        self._send_json({"type":"invite_reject","from_id":from_id,"to_id":to_id})
        resp=self._recv_line(timeout=1.4)
        try: self._sock.close()
        except: pass
        self.connected=False
        return True, "ok"

    def send_ready(self, lobby_id, ready):
        pid=str(self.save.get("player_id","")).strip()
        if self._persistent_sock and self._persistent_running:
            try:
                self._persistent_sock.sendall((json.dumps({"type":"ready","lobby_id":lobby_id,"player_id":pid,"ready":bool(ready)}) + "\n").encode("utf-8"))
                return True
            except: pass
        if not self._connect(timeout=1.0):
            return False
        self._send_json({"type":"ready","lobby_id":lobby_id,"player_id":pid,"ready":bool(ready)})
        try: self._sock.close()
        except: pass
        self.connected=False
        return True

    def leave_lobby(self, lobby_id):
        pid=str(self.save.get("player_id","")).strip()
        if self._persistent_sock and self._persistent_running:
            try:
                self._persistent_sock.sendall((json.dumps({"type":"lobby_leave","lobby_id":lobby_id,"player_id":pid}) + "\n").encode("utf-8"))
            except: pass
        if not self._connect(timeout=1.0):
            return
        self._send_json({"type":"lobby_leave","lobby_id":lobby_id,"player_id":pid})
        try: self._sock.close()
        except: pass
        self.connected=False
        with self._lock:
            self._lobby=None
            self._game_start_lobby=None

    def send_player_state(self, lobby_id, state):
        pid=str(self.save.get("player_id","")).strip()
        if self._persistent_sock and self._persistent_running:
            try:
                self._persistent_sock.sendall((json.dumps({"type":"player_state","lobby_id":lobby_id,"player_id":pid,"state":state}) + "\n").encode("utf-8"))
                return True
            except: pass
        # fallback one-shot
        if not self._connect(timeout=0.8):
            return False
        self._send_json({"type":"player_state","lobby_id":lobby_id,"player_id":pid,"state":state})
        resp=self._recv_line(timeout=0.8)
        try: self._sock.close()
        except: pass
        self.connected=False
        return bool(resp and resp.get("ok"))

    def poll_invite(self):
        # Polling via server (one-shot)
        pid = str(self.save.get("player_id","")).strip()
        if not is_valid_id(pid):
            # fallback to local
            with self._lock:
                lst=getattr(self, "_pending_invites", [])
                if lst:
                    return lst.pop(0)
            return None
        if not self._connect(timeout=1.0):
            with self._lock:
                lst=getattr(self, "_pending_invites", [])
                if lst:
                    return lst.pop(0)
            return None
        self._send_json({"type":"get_invites","player_id":pid})
        resp=self._recv_line(timeout=1.0)
        try: self._sock.close()
        except: pass
        self.connected=False
        if resp and resp.get("invites"):
            lst=resp["invites"]
            if lst:
                return lst[0]
        # fallback local
        with self._lock:
            lst=getattr(self, "_pending_invites", [])
            if lst:
                return lst.pop(0)
        return None

    def poll_lobby(self):
        pid=str(self.save.get("player_id","")).strip()
        if not is_valid_id(pid):
            with self._lock:
                return getattr(self, "_lobby", None)
        if not self._connect(timeout=1.0):
            with self._lock:
                return getattr(self, "_lobby", None)
        self._send_json({"type":"get_lobby","player_id":pid})
        resp=self._recv_line(timeout=1.0)
        try: self._sock.close()
        except: pass
        self.connected=False
        if resp and resp.get("lobby"):
            with self._lock:
                self._lobby=resp["lobby"]
            return resp["lobby"]
        # check if lobby was closed (server returns None)
        if resp and resp.get("lobby") is None:
            with self._lock:
                if getattr(self, "_lobby", None):
                    # lobby closed
                    self._lobby=None
                    return None
        with self._lock:
            return getattr(self, "_lobby", None)

    def poll_game_start(self, lobby_id=None):
        # lobby_id verildiyse tekrar get_lobby yapma
        lid = lobby_id
        if not lid:
            lobby=self.poll_lobby()
            if lobby:
                lid=lobby.get("lobby_id")
            if not lid:
                with self._lock:
                    gid=getattr(self, "_game_start_lobby", None)
                    if gid:
                        self._game_start_lobby=None
                        return gid
                return None
        if not self._connect(timeout=1.0):
            with self._lock:
                gid=getattr(self, "_game_start_lobby", None)
                if gid:
                    self._game_start_lobby=None
                    return gid
            return None
        self._send_json({"type":"check_game_start","lobby_id":lid})
        resp=self._recv_line(timeout=1.0)
        try: self._sock.close()
        except: pass
        self.connected=False
        if resp and resp.get("game_start"):
            with self._lock:
                self._game_start_lobby=None
            return lid
        with self._lock:
            gid=getattr(self, "_game_start_lobby", None)
            if gid:
                self._game_start_lobby=None
                return gid
        return None

    def poll_remote_states(self, lobby_id=None):
        pid=str(self.save.get("player_id","")).strip()
        lid=lobby_id
        if not lid:
            lobby=self.poll_lobby()
            if not lobby or not lobby.get("lobby_id"):
                with self._lock:
                    return dict(getattr(self, "_remote_states", {}))
            lid=lobby["lobby_id"]
        if not self._connect(timeout=1.0):
            with self._lock:
                return dict(getattr(self, "_remote_states", {}))
        self._send_json({"type":"get_player_states","lobby_id":lid,"player_id":pid})
        resp=self._recv_line(timeout=1.0)
        try: self._sock.close()
        except: pass
        self.connected=False
        if resp and "states" in resp:
            with self._lock:
                self._remote_states=resp["states"]
            return resp["states"]
        with self._lock:
            return dict(getattr(self, "_remote_states", {}))

    def search_player(self, target_id):
        tid=str(target_id).strip()
        print(f"[CLIENT] SEARCH {tid}")
        if not is_valid_id(tid):
            print(f"[CLIENT] SEARCH invalid ID")
            return None, "Geçerli bir 5 haneli ID gir."
        if tid==str(self.save.get("player_id")):
            print(f"[CLIENT] SEARCH self")
            return None, "Kendi ID'nizi giremezsiniz"
        if not self._connect(timeout=1.4):
            print(f"[CLIENT] SEARCH failed: Sunucuya bağlanılamadı.")
            return None, "Sunucuya bağlanılamadı."
        self._send_json({"type":"search","target_id":tid})
        resp=self._recv_line(timeout=1.6)
        try: self._sock.close()
        except: pass
        self.connected=False
        if not resp:
            print(f"[CLIENT] SEARCH no response -> Sunucu bağlantısı kesildi.")
            return None, "Sunucu bağlantısı kesildi."
        if resp.get("found"):
            print(f"[CLIENT] SEARCH found {resp.get('player')}")
            info=resp.get("player")
            # uyumluluk: nick/id alanları
            if info and "nick" not in info and "nickname" in info:
                info["nick"]=info["nickname"]
            if info and "id" not in info and "player_id" in info:
                info["id"]=info["player_id"]
            self.opponent_info=info
            return info, "ok"
        else:
            # Spec: "Bu ID ile oyuncu bulunamadı." / "Sunucu bağlantısı kesildi."
            err = resp.get("error") or "Bu ID ile oyuncu bulunamadı."
            if "Sunucuya bağlanılamadı" in err:
                err = "Sunucuya bağlanılamadı."
            elif "çevrimiçi" in err:
                err = "Bu ID ile oyuncu bulunamadı."
            print(f"[CLIENT] SEARCH result: {err}")
            return None, err

    def create_match(self, opponent_id):
        # Bu aşamada maç yok — sadece sahte session
        import random
        self.session_id=f"mock-{random.randint(1000,9999)}"
        return True, self.session_id

    def start_sync(self, get_local_fn):
        pass
    def stop_sync(self):
        pass
    def get_remote_state(self):
        with self._lock:
            return dict(self._remote_state)
    def disconnect(self):
        pid=str(self.save.get("player_id","")).strip()
        if is_valid_id(pid):
            try:
                if self._connect(timeout=0.8):
                    self._send_json({"type":"disconnect","player_id":pid})
                    try: self._sock.close()
                    except: pass
            except: pass
        self._online_status=False
