import json, os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_json(name, fallback):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Data] {name} load fail: {e} -> fallback")
        return fallback

def ensure_data_files(config):
    os.makedirs(DATA_DIR, exist_ok=True)
    # characters.json, items.json, themes.json, levels.json yaz (eğer yoksa)
    defaults = {
        "levels.json": config.LEVELS,
        "characters.json": config.CHARACTERS,
        "themes.json": config.THEMES,
        "shop.json": config.SHOP_ITEMS,
    }
    for fname, data in defaults.items():
        p = os.path.join(DATA_DIR, fname)
        if not os.path.exists(p):
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[Data] write {fname} fail: {e}")

def _sanitize_color(v, fallback=(255, 255, 255)):
    try:
        if isinstance(v, (list, tuple)) and len(v) >= 3:
            return (int(v[0]), int(v[1]), int(v[2]))
    except:
        pass
    return fallback

def apply_data_to_config(config):
    """JSON dosyalarından config'i gerçekten yükle (varsa override)."""
    # levels
    lvls = load_json("levels.json", None)
    if isinstance(lvls, list) and lvls:
        clean = []
        for e in lvls:
            try:
                clean.append({
                    "level": int(e.get("level", 0)),
                    "name": str(e.get("name", "")),
                    "distance": int(e.get("distance", 0)),
                    "bg": _sanitize_color(e.get("bg"), (135, 206, 250)),
                    "wall": _sanitize_color(e.get("wall"), (120, 120, 120)),
                    "obstacle": _sanitize_color(e.get("obstacle"), (90, 90, 90)),
                    "accent": _sanitize_color(e.get("accent"), (255, 255, 255)),
                })
            except Exception as ex:
                print(f"[Data] levels sanitize skip: {ex}")
        if clean:
            try:
                clean.sort(key=lambda x: x["distance"])
                config.LEVELS = clean
            except Exception as e:
                print(f"[Data] levels apply fail: {e}")

    # characters
    chars = load_json("characters.json", None)
    if isinstance(chars, list) and chars:
        clean = []
        for c in chars:
            try:
                clean.append({
                    "id": str(c.get("id")),
                    "name": str(c.get("name", c.get("id"))),
                    "level": int(c.get("level", 1)),
                    "color": _sanitize_color(c.get("color"), (80, 80, 80)),
                    "accent": _sanitize_color(c.get("accent"), (200, 200, 200)),
                })
            except Exception as ex:
                print(f"[Data] characters sanitize skip: {ex}")
        if clean:
            config.CHARACTERS = clean

    # themes (12 alanlı palet korunur, eski 6 alanlı ile uyumlu)
    ths = load_json("themes.json", None)
    if isinstance(ths, list) and ths:
        clean = []
        for t in ths:
            try:
                _bg = _sanitize_color(t.get("bg"), (245, 245, 245))
                clean.append({
                    "id": str(t.get("id")),
                    "name": str(t.get("name", t.get("id"))),
                    "bg": _bg,
                    "ui_bg": _sanitize_color(t.get("ui_bg"), (255, 255, 255)),
                    "ui_text": _sanitize_color(t.get("ui_text"), (30, 30, 30)),
                    "button": _sanitize_color(t.get("button"), (220, 220, 220)),
                    "button_hover": _sanitize_color(t.get("button_hover"), (200, 200, 200)),
                    "hud": _sanitize_color(t.get("hud"), (30, 30, 30)),
                    "accent": _sanitize_color(t.get("accent"), _bg),
                    "coin": _sanitize_color(t.get("coin"), (255, 215, 0)),
                    "danger": _sanitize_color(t.get("danger"), (200, 40, 40)),
                    "success": _sanitize_color(t.get("success"), (40, 160, 80)),
                    "border": _sanitize_color(t.get("border"), (200, 200, 200)),
                    "glow": _sanitize_color(t.get("glow"), _bg),
                    "particle": _sanitize_color(t.get("particle"), (200, 200, 210)),
                })
            except Exception as ex:
                print(f"[Data] themes sanitize skip: {ex}")
        if clean:
            config.THEMES = clean

    # shop
    shop = load_json("shop.json", None)
    if isinstance(shop, dict) and shop:
        clean_shop = {}
        for cat in ("hat", "bag", "glasses", "cane"):
            lst = shop.get(cat)
            if isinstance(lst, list):
                cl = []
                for it in lst:
                    try:
                        cl.append({
                            "id": str(it.get("id")),
                            "name": str(it.get("name", it.get("id"))),
                            "price": int(it.get("price", 0)),
                            "icon": str(it.get("icon", "?")),
                        })
                    except Exception as ex:
                        print(f"[Data] shop sanitize skip: {ex}")
                clean_shop[cat] = cl
            else:
                clean_shop[cat] = config.SHOP_ITEMS.get(cat, [])
        # eksik kategori varsa config'ten tamamla
        for k, v in config.SHOP_ITEMS.items():
            if k not in clean_shop:
                clean_shop[k] = v
        config.SHOP_ITEMS = clean_shop
