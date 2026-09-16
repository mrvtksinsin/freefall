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

    # Eski register (client ID gönderirdi) artık kullanılmıyor — geriye dönük stub
    def register(self):
        # Artık register_new kullanılmalı
        pid=str(self.save.get("player_id",""))
        nick=str(self.save.get("nickname",""))
        if is_valid_id(pid):
            return self.login()
        return self.register_new(nick)

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
