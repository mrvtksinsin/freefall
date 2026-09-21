"""
Eşya ikonları - FREEFALL
Gerçek bitmap asset yok; oyundaki eşyalar procedural çizilir (player.py _draw_*).
Bu modül, oyunda kuşanılan eşyanın birebir aynı görselini küçük bir ikon olarak üretir
ve cache'ler. Böylece Mağaza/Envanter görseli ile karakter üzerindeki görsel tutarlı olur.
"""
import pygame
from player import Player

_TRACKED_SURFACES = {}  # (item_id, size) -> Surface


def get_item_icon(item, size=54):
    """item dict'inden oyun içi görselle birebir aynı ikonu döndürür (cache'li)."""
    iid = str(item.get("id", ""))
    key = (iid, size)
    if key in _TRACKED_SURFACES:
        return _TRACKED_SURFACES[key]
    surf = _render(item, size)
    _TRACKED_SURFACES[key] = surf
    return surf


def clear_cache():
    _TRACKED_SURFACES.clear()


def _render(item, size):
    iid = str(item.get("id", ""))
    # eşyayı rahatça sığdıracak kadar geniş geçici surface
    tmp = pygame.Surface((size + 24, size + 24), pygame.SRCALPHA)
    ox = 12
    oy = 12 + size - 12  # alt bölge; aşağıda sınırlayıcı kutu alınıyor
    try:
        if iid.startswith("hat"):
            # _draw_hat(x, y): şapka (x,y) çevresinde çizilir
            Player._draw_hat(None, tmp, ox + 4, oy - 6, iid)
        elif iid.startswith("glasses"):
            # _draw_glasses(cx, cy): merkez etrafında çizilir
            Player._draw_glasses(None, tmp, ox + size // 2, oy - 10, iid)
        elif iid.startswith("bag"):
            # _draw_bag(rect): gövde rect ile verilir
            Player._draw_bag(None, tmp, pygame.Rect(ox, oy - 24, size - 18, int(size * 0.42)), iid)
        elif iid.startswith("cane"):
            # _draw_cane(rect, state): sap rect + baş yukarı
            Player._draw_cane(None, tmp, pygame.Rect(ox + size // 2 - 3, oy - 30, 6, size - 6), iid, "idle")
        else:
            # bilinmeyen eşya: metin ikonu (eski davranış)
            f = pygame.font.SysFont("Arial", 20, bold=True)
            t = f.render(str(item.get("icon", "?")), True, (40, 40, 44))
            tmp.blit(t, (tmp.get_width() // 2 - t.get_width() // 2,
                         tmp.get_height() // 2 - t.get_height() // 2))
    except Exception:
        f = pygame.font.SysFont("Arial", 18, bold=True)
        t = f.render(str(item.get("icon", "?")), True, (50, 50, 55))
        tmp.blit(t, (tmp.get_width() // 2 - t.get_width() // 2,
                     tmp.get_height() // 2 - t.get_height() // 2))

    # opak sayılabilir sınırlayıcı kutu (zarif glow'ları dışarıda bırak)
    bbox = tmp.get_bounding_rect(min_alpha=8)
    if bbox.w <= 1 or bbox.h <= 1:
        bbox = tmp.get_rect()
    crop = tmp.subsurface(bbox).copy()

    # kenar boşluğu ile sığdır
    pad = max(2, size // 18)
    max_w = size - pad * 2
    max_h = size - pad * 2
    scale = min(max_w / float(crop.get_width()), max_h / float(crop.get_height()), 1.0)
    if scale < 1.0:
        crop = pygame.transform.smoothscale(
            crop,
            (max(1, int(crop.get_width() * scale)),
             max(1, int(crop.get_height() * scale))),
        )

    out = pygame.Surface((size, size), pygame.SRCALPHA)
    out.blit(crop, (size // 2 - crop.get_width() // 2,
                    size // 2 - crop.get_height() // 2))
    return out