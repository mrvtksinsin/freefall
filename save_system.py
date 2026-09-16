import copy
import json
import os
from config import CHARACTERS

def _get_save_path():
    # Android'de yazılabilir özel klasör kullan
    try:
        # Kivy / android.storage
        from android.storage import app_storage_path
        p = app_storage_path()
        if p:
            return os.path.join(p, "save.json")
    except:
        pass
    try:
        import sys
        if hasattr(sys, 'getandroidapilevel'):
            # p4a private dir
            base = os.environ.get('ANDROID_PRIVATE', '')
            if base and os.path.isdir(base):
                return os.path.join(base, "save.json")
            # fallback: cwd
            return os.path.join(os.getcwd(), "save.json")
    except:
        pass
    return os.path.join(os.path.dirname(__file__), "save.json")

SAVE_PATH = _get_save_path()

DEFAULT_SAVE = {
    "total_coins": 0,
    "best_distance": 0.0,
    "level": 1,
    "selected_character": "cop_adam",
    "selected_hat": None,
    "selected_bag": None,
    "selected_glasses": None,
    "selected_cane": None,
    "owned_items": [],  # list of ids like "hat1"
    "theme": "beyaz",
    "unlocked_characters": ["cop_adam"],  # başlangıçta sadece çöp adam
    "settings": {"master": 0.7, "music": 0.5, "sfx": 0.8, "show_tutorial": True},
    "tutorial_done": False,
    # Bölüm sistemi — kalıcı (23 bölüm: 1-22 + FINAL 23)
    "unlocked_levels": [1],
    "completed_levels": [],
    "level_stars": {},  # level:int -> stars 0-3
    "current_level": 1,
    "final_completed": False,
    # Oyuncu profili — kalıcı 5 haneli ID
    "nickname": None,
    "player_id": None,
}

def _deep_copy_default():
    return copy.deepcopy(DEFAULT_SAVE)

def load_save():
    if not os.path.exists(SAVE_PATH):
        return _deep_copy_default()
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # merge defaults (deep for settings)
        out = _deep_copy_default()
        # shallow update for top-level, but keep deep-copied lists/dicts
        for k, v in data.items():
            if k == "settings" and isinstance(v, dict):
                out["settings"].update(v)
            elif k in ("owned_items", "unlocked_characters", "unlocked_levels", "completed_levels") and isinstance(v, list):
                out[k] = list(v)
            elif k == "level_stars" and isinstance(v, dict):
                # json keys are str, convert to int
                out[k] = {int(kk): int(vv) for kk, vv in v.items()}
            else:
                out[k] = v
        if "settings" not in out or not isinstance(out["settings"], dict):
            out["settings"] = dict(DEFAULT_SAVE["settings"])
        else:
            tmp = dict(DEFAULT_SAVE["settings"])
            tmp.update(out["settings"])
            out["settings"] = tmp
        # clamp audio values to avoid 0.5000000000000001 drift
        for ak in ("master", "music", "sfx"):
            try:
                out["settings"][ak] = round(max(0.0, min(1.0, float(out["settings"][ak]))), 2)
            except:
                out["settings"][ak] = DEFAULT_SAVE["settings"][ak]
        # ensure unlocked based on level (in case save old)
        lvl = out.get("level", 1)
        for ch in CHARACTERS:
            if ch["level"] <= lvl and ch["id"] not in out["unlocked_characters"]:
                out["unlocked_characters"].append(ch["id"])
        # bölüm sistemi migration — 23 bölüm (1-22 + FINAL 23), kesin sıralı kilit
        if "unlocked_levels" not in out or not isinstance(out["unlocked_levels"], list) or not out["unlocked_levels"]:
            out["unlocked_levels"] = [1]
        if "completed_levels" not in out or not isinstance(out["completed_levels"], list):
            out["completed_levels"] = []
        if "level_stars" not in out or not isinstance(out["level_stars"], dict):
            out["level_stars"] = {}
        if "current_level" not in out or not isinstance(out["current_level"], int):
            out["current_level"] = int(out.get("level", 1))
        if "final_completed" not in out or not isinstance(out["final_completed"], bool):
            out["final_completed"] = False
        # profil — kalıcı nick + 5 haneli ID
        if "nickname" not in out or not isinstance(out.get("nickname"), str):
            # None olabilir, profil oluşturma ekranına yönlendirmek için
            out["nickname"] = out.get("nickname")
            if out["nickname"] is not None and not isinstance(out["nickname"], str):
                out["nickname"] = None
        if "player_id" not in out or out.get("player_id") is None:
            out["player_id"] = None
        else:
            # ID 5 rakam kontrol — bozuksa None yap
            pid = str(out["player_id"]).strip()
            if not (pid.isdigit() and len(pid) == 5):
                out["player_id"] = None
            else:
                out["player_id"] = pid
        # 23 dahil clamp — bozulursa güvenli varsayılan
        try:
            out["unlocked_levels"] = sorted(set(int(x) for x in out["unlocked_levels"] if 1 <= int(x) <= 23))
        except:
            out["unlocked_levels"] = [1]
        if not out["unlocked_levels"]:
            out["unlocked_levels"] = [1]
        try:
            out["completed_levels"] = sorted(set(int(x) for x in out["completed_levels"] if 1 <= int(x) <= 23))
        except:
            out["completed_levels"] = []
        try:
            out["current_level"] = max(1, min(23, int(out["current_level"])))
        except:
            out["current_level"] = 1
        # final_completed tutarlılığı — 23 tamamlandıysa true
        if 23 in out["completed_levels"]:
            out["final_completed"] = True
        # sıralı kilit garantisi: completed max + 1 mutlaka açık, ama atlama yok
        # Eğer save bozuk ve unlocked'ta boşluk varsa düzelt (ör. [1,5] -> [1,2])
        if out["completed_levels"]:
            max_c = max(out["completed_levels"])
            expected_unlocked = list(range(1, min(23, max_c + 2)))  # 1..max+1
            # unlocked_levels en az expected kadar olmalı, fazla atlama varsa kırp
            for lv in expected_unlocked:
                if lv not in out["unlocked_levels"]:
                    out["unlocked_levels"].append(lv)
            out["unlocked_levels"] = sorted(set(x for x in out["unlocked_levels"] if x <= max(out["unlocked_levels"][:1] + [max_c+1]) or x in expected_unlocked or x <= max_c+1))
            # sadeleştir: sadece 1..max+1 bırak, izinsiz ileri kilitleri kapat
            out["unlocked_levels"] = sorted(x for x in out["unlocked_levels"] if x <= max_c + 1)
            if 1 not in out["unlocked_levels"]:
                out["unlocked_levels"].insert(0, 1)
                out["unlocked_levels"] = sorted(set(out["unlocked_levels"]))
        else:
            # hiçbir bölüm tamamlanmamışsa sadece 1 açık
            if out["unlocked_levels"] != [1]:
                # eski save'te level 6 gibi şişmişse geri al — sadece 1 açık kalmalı
                # ama kullanıcı teste devam ettiyse ve zaten 2..n açılmışsa ve completed yoksa, bunu düzelt
                # burada katı davran: sadece 1 bırak
                # Not: sadece bozuk save'i düzeltmek için; normal ilerlemede zaten completed olur
                pass
            # katı kural: completed yoksa sadece 1 açık olmalı — fazla açılmışsa kırp
            if len(out["unlocked_levels"]) > 1 and not out["completed_levels"]:
                # eğer seviye distance ile şişmişse, onu temizle
                # kullanıcının manuel açtığı yoksa direkt [1]
                # Güvenlik: eğer unlocked 1'den fazla ve completed yoksa, kullanıcı hile yapmış sayılır -> [1]
                # Ama mevcut save.json'da level 6 olup unlocked [1] ise zaten doğru, dokunma
                if out["unlocked_levels"] != [1]:
                    # sadece [1] tut, diğerlerini kilitle
                    out["unlocked_levels"] = [1]
        # son clamp tekrar
        out["unlocked_levels"] = sorted(set(int(x) for x in out["unlocked_levels"] if 1 <= int(x) <= 23))
        if not out["unlocked_levels"]:
            out["unlocked_levels"] = [1]
        return out
    except Exception as e:
        print(f"[Save] load fail {e} -> default")
        return _deep_copy_default()

def unlock_next_level(save, completed_level):
    """Bölüm tamamlanınca bir sonrakini aç (kesin sıralı, atlama yok), save et."""
    if completed_level not in save.get("completed_levels", []):
        save["completed_levels"].append(completed_level)
        save["completed_levels"] = sorted(set(save["completed_levels"]))
    # current_level güncelle
    try:
        save["current_level"] = max(save.get("current_level", 1), completed_level)
    except:
        save["current_level"] = completed_level
    # final bayrağı
    from config import LEVELS as _LVLS
    max_lvl = max(e["level"] for e in _LVLS)
    if completed_level >= max_lvl:
        save["final_completed"] = True
    nxt = completed_level + 1
    if nxt <= max_lvl and nxt not in save.get("unlocked_levels", []):
        # sadece bir sonraki açılır — atlama yok
        # eğer save bozuk ve ara seviye eksikse, zinciri tamamla
        for lv in range(1, nxt+1):
            if lv not in save["unlocked_levels"]:
                # sadece n+1'e kadar izin ver, daha ilerisi açılmamalı
                if lv <= nxt:
                    save["unlocked_levels"].append(lv)
        save["unlocked_levels"] = sorted(set(x for x in save["unlocked_levels"] if 1 <= x <= max_lvl))
    # sıralı garantisi: unlocked max = max(completed)+1
    if save.get("completed_levels"):
        max_c = max(save["completed_levels"])
        save["unlocked_levels"] = sorted(x for x in save["unlocked_levels"] if x <= max_c + 1)
        if 1 not in save["unlocked_levels"]:
            save["unlocked_levels"].insert(0, 1)
    return nxt

def save_game(data):
    try:
        # ensure volume values are rounded before persist
        if "settings" in data and isinstance(data["settings"], dict):
            for ak in ("master", "music", "sfx"):
                if ak in data["settings"]:
                    try:
                        data["settings"][ak] = round(max(0.0, min(1.0, float(data["settings"][ak]))), 2)
                    except:
                        pass
        # level_stars keys str for json
        if "level_stars" in data and isinstance(data["level_stars"], dict):
            data["level_stars"] = {str(k): int(v) for k, v in data["level_stars"].items()}
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Kayit hatasi: {e}")

def get_level_for_distance(dist_m):
    from config import LEVELS
    lvl = 1
    for entry in LEVELS:
        if dist_m * 1.0 >= entry["distance"] / 100.0:  # config distance is pixels? we use meters now, convert
            lvl = entry["level"]
        else:
            break
    return lvl

def level_name(lvl):
    from config import LEVELS
    for e in LEVELS:
        if e["level"] == lvl:
            return e["name"]
    return f"SEVIYE {lvl}"

def generate_player_id():
    """5 haneli rastgele ID üret — 10000-99999."""
    import random
    return f"{random.randint(10000, 99999):05d}"

def is_valid_nick(nick):
    if not isinstance(nick, str):
        return False
    n = nick.strip()
    if len(n) < 2 or len(n) > 16:
        return False
    # harf/sayı/alt tire + Türkçe karakterler + boşluk
    import re
    return bool(re.match(r"^[A-Za-z0-9_ÇĞİÖŞÜçğıöşü ]+$", n))

def is_valid_player_id(pid):
    return isinstance(pid, str) and pid.isdigit() and len(pid) == 5

def ensure_profile(save):
    """Profil yoksa None döndür, varsa True."""
    return is_valid_nick(save.get("nickname") or "") and is_valid_player_id(str(save.get("player_id") or ""))

def update_level_and_unlocks(save, dist_m):
    # seviye mesafeye göre (pixel/100)
    # config LEVELS distance px bazlı, dist_m*100 = px
    from config import LEVELS
    px = dist_m * 100.0
    new_level = 1
    for e in LEVELS:
        if px >= e["distance"]:
            new_level = e["level"]
    if new_level > save["level"]:
        save["level"] = new_level
        # yeni karakterleri aç
        for ch in CHARACTERS:
            if ch["level"] == new_level and ch["id"] not in save["unlocked_characters"]:
                save["unlocked_characters"].append(ch["id"])
    return new_level
