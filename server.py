"""
FREEFALL Online Sunucu — 5 haneli ID benzersizlik + Eşleşme + Sync
Çalıştır: python server.py
Port: 47822
Protokol: JSON satır (newline)
"""
import socket
import threading
import json
import time

HOST = "0.0.0.0"
PORT = 47822

# Bellek içi registry — kalıcı için dosyaya da yazıyoruz
REGISTRY = {}  # id -> {nick, id, char, last_seen}
SESSIONS = {}  # session_id -> {p1,p2, states: {id: state}}
REG_LOCK = threading.Lock()
SESSION_LOCK = threading.Lock()

def load_registry():
    try:
        with open("online_registry.json","r",encoding="utf-8") as f:
            data = json.load(f)
            for k,v in data.items():
                REGISTRY[k]=v
        print(f"[Server] registry yüklendi {len(REGISTRY)} oyuncu")
    except:
        pass

def save_registry():
    try:
        with open("online_registry.json","w",encoding="utf-8") as f:
            json.dump(REGISTRY, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[Server] save fail",e)

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
                if t == "register":
                    pid = str(msg.get("id","")).strip()
                    nick = str(msg.get("nick","")).strip()
                    char = str(msg.get("char","cop_adam"))
                    if not (pid.isdigit() and len(pid)==5):
                        resp={"ok":False,"error":"ID 5 rakam olmalı"}
                    elif len(nick)<2:
                        resp={"ok":False,"error":"Nick çok kısa"}
                    else:
                        with REG_LOCK:
                            # benzersizlik: aynı ID farklı nick ile kayıtlı ise reddet (sahte değilse)
                            if pid in REGISTRY and REGISTRY[pid].get("nick") != nick:
                                # Aynı ID farklı nick — çakışma, reddet
                                resp={"ok":False,"error":f"ID {pid} zaten kullanımda"}
                            else:
                                REGISTRY[pid]={"nick":nick,"id":pid,"char":char,"last_seen": time.time()}
                                save_registry()
                                resp={"ok":True}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    return
                elif t == "search":
                    pid = str(msg.get("id","")).strip()
                    with REG_LOCK:
                        found = pid in REGISTRY
                        player = REGISTRY.get(pid)
                    if found:
                        resp={"found":True,"player": player}
                    else:
                        resp={"found":False}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    return
                elif t == "match":
                    from_id = str(msg.get("from_id","")).strip()
                    to_id = str(msg.get("to_id","")).strip()
                    with REG_LOCK:
                        if from_id not in REGISTRY or to_id not in REGISTRY:
                            resp={"ok":False,"error":"Oyuncu bulunamadı"}
                            conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                            return
                    sess = f"sess_{from_id}_{to_id}_{int(time.time())}"
                    with SESSION_LOCK:
                        SESSIONS[sess]={"p1":from_id,"p2":to_id,"states":{}}
                    resp={"ok":True,"session_id": sess}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    return
                elif t == "sync":
                    pid = str(msg.get("id","")).strip()
                    sess = str(msg.get("session",""))
                    state = msg.get("state",{})
                    with SESSION_LOCK:
                        sess_obj = SESSIONS.get(sess)
                        if sess_obj:
                            sess_obj["states"][pid]= state
                            # rakibi bul
                            other = sess_obj["p2"] if sess_obj["p1"]==pid else sess_obj["p1"]
                            other_state = sess_obj["states"].get(other, {})
                            resp={"state": other_state}
                        else:
                            resp={"state":{}}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    return
                else:
                    resp={"ok":False,"error":"Bilinmeyen type"}
                    conn.sendall((json.dumps(resp)+"\n").encode("utf-8"))
                    return
    except Exception as e:
        # sessiz
        pass
    finally:
        try: conn.close()
        except: pass

def main():
    load_registry()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(64)
    print(f"[Server] FREEFALL Online listening {HOST}:{PORT}")
    print(f"[Server] 5 haneli ID benzersizlik aktif")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn,addr), daemon=True).start()

if __name__ == "__main__":
    main()
