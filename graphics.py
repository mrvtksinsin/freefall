import pygame
import math
import random

# Cache for gradients and glows — performansı korurken kalite artar
_gradient_cache = {}
_glow_cache = {}
_bevel_cache = {}
_cloud_cache = {}

def vertical_gradient(surf, top_color, bottom_color):
    """High-quality vertical gradient with dithering + cache."""
    h = surf.get_height()
    w = surf.get_width()
    key = (w,h,top_color,bottom_color)
    if key in _gradient_cache:
        surf.blit(_gradient_cache[key], (0,0))
        return
    grad = pygame.Surface((w,h))
    # subtle noise for banding-free gradient (dithering)
    for y in range(h):
        t = y / max(1, h-1)
        # smoothstep for more natural blend
        ts = t*t*(3 - 2*t)
        r = int(top_color[0]*(1-ts) + bottom_color[0]*ts)
        g = int(top_color[1]*(1-ts) + bottom_color[1]*ts)
        b = int(top_color[2]*(1-ts) + bottom_color[2]*ts)
        # tiny dither to break banding
        d = (hash((y,w)) % 5) - 2
        r = max(0,min(255,r+d)); g = max(0,min(255,g+d)); b = max(0,min(255,b+d))
        pygame.draw.line(grad, (r,g,b), (0,y), (w,y))
    _gradient_cache[key] = grad.copy()
    surf.blit(grad, (0,0))

def horizontal_gradient(surf, rect, left_color, right_color):
    """Horizontal gradient inside rect."""
    for x in range(rect.width):
        t = x / max(1, rect.width-1)
        ts = t*t*(3-2*t)
        r = int(left_color[0]*(1-ts)+right_color[0]*ts)
        g = int(left_color[1]*(1-ts)+right_color[1]*ts)
        b = int(left_color[2]*(1-ts)+right_color[2]*ts)
        pygame.draw.line(surf, (r,g,b), (rect.x+x, rect.y), (rect.x+x, rect.bottom))

def draw_rounded_rect(surf, rect, color, radius=10, border=0, border_color=(0,0,0)):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border_color, rect, width=border, border_radius=radius)

def draw_bevel_rect(surf, rect, color, radius=9):
    """3D bevel: highlight top-left, shadow bottom-right — Tetris+ kalite."""
    # base
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    # highlight top edge
    hi = tuple(min(255, c+38) for c in color)
    pygame.draw.line(surf, hi, (rect.x+radius//2, rect.y+2), (rect.right-radius//2, rect.y+2), 2)
    # soft inner bevel line
    pygame.draw.rect(surf, (255,255,255,40), rect.inflate(-4,-4), width=1, border_radius=radius-2)
    # shadow bottom
    pygame.draw.line(surf, (0,0,0,70), (rect.x+6, rect.bottom-3), (rect.right-6, rect.bottom-3), 2)
    pygame.draw.rect(surf, (0,0,0), rect, width=2, border_radius=radius)

def draw_soft_shadow(surf, rect, radius=12, alpha=60):
    """Soft drop shadow under a rect."""
    sh = pygame.Surface((rect.width+radius*2, rect.height+radius*2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        a = int(alpha * (1 - r/radius) * 0.45)
        pygame.draw.rect(sh, (0,0,0,a), pygame.Rect(radius-r, radius-r, rect.width+r*2, rect.height+r*2), border_radius=9+r)
    surf.blit(sh, (rect.x - radius, rect.y - radius))

def draw_glow(surf, pos, radius, color, alpha=90):
    """Soft glow circle — 2x smoother falloff + cache."""
    key = (radius, color, alpha)
    if key not in _glow_cache:
        size = radius*2 + 8
        s = pygame.Surface((size,size), pygame.SRCALPHA)
        cx = size//2
        for r in range(radius, 0, -1):
            # quadratic falloff for softer edge
            f = 1 - (r/radius)
            a = int(alpha * f * f * 0.68)
            pygame.draw.circle(s, (*color, a), (cx, cx), r)
        _glow_cache[key] = s
    else:
        s = _glow_cache[key]
    surf.blit(s, (pos[0]-s.get_width()//2, pos[1]-s.get_height()//2), special_flags=pygame.BLEND_RGBA_ADD)

_vignette_cache = {}

def draw_vignette(surf, intensity=0.22):
    """Subtle vignette — depth feel without cost."""
    key = (surf.get_size(), int(round(intensity, 3) * 1000))
    vig = _vignette_cache.get(key)
    if vig is None:
        w, h = surf.get_size()
        vig = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        maxd = math.hypot(cx, cy)
        for y in range(0, h, 2):
            for x in range(0, w, 4):
                d = math.hypot(x - cx, y - cy) / maxd
                a = int(intensity * 160 * (d ** 1.7))
                if a > 4:
                    vig.set_at((x, y), (0, 0, 0, a))
                    if x + 1 < w: vig.set_at((x + 1, y), (0, 0, 0, a))
        _vignette_cache[key] = vig
    # use multiply-like blend via alpha blit
    surf.blit(vig, (0, 0))

def draw_shadow(surf, rect, alpha=50):
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    shadow.fill((0,0,0, alpha))
    surf.blit(shadow, (rect.x+3, rect.y+4))

def draw_button(surf, rect, base_color, text_surf, is_hover=False, is_selected=False, theme=None):
    # enhanced gradient + bevel + soft shadow + glow
    hover = is_hover or is_selected
    # soft shadow under button
    if hover or is_selected:
        draw_soft_shadow(surf, rect, radius=10, alpha=42)

    top = tuple(min(255, c+34) for c in base_color) if hover else tuple(min(255, c+18) for c in base_color)
    bottom = tuple(max(0, c-22) for c in base_color)
    btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    for y in range(rect.height):
        t = y/rect.height
        # ease
        ts = t*t*(3-2*t)
        r = int(top[0]*(1-ts)+bottom[0]*ts)
        g = int(top[1]*(1-ts)+bottom[1]*ts)
        b = int(top[2]*(1-ts)+bottom[2]*ts)
        pygame.draw.line(btn_surf, (r,g,b), (0,y), (rect.width,y))
    mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255,255,255), (0,0,rect.width,rect.height), border_radius=11)
    btn_surf.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(btn_surf, rect.topleft)
    border_col = (255,215,0) if is_selected else (255,255,255,170) if hover else (0,0,0,160)
    border_w = 3 if is_selected else 2
    if is_selected:
        glow_rect = rect.inflate(12,12)
        draw_glow(surf, glow_rect.center, 30, (255,215,0), 38)
    pygame.draw.rect(surf, border_col if isinstance(border_col,tuple) and len(border_col)==3 else (255,215,0) if is_selected else (0,0,0), rect, width=border_w, border_radius=11)
    # inner highlight specular
    pygame.draw.line(surf, (255,255,255, 88), (rect.x+10, rect.y+4), (rect.x+rect.width-10, rect.y+4), 2)
    # bottom bevel shadow
    pygame.draw.line(surf, (0,0,0, 55), (rect.x+8, rect.bottom-4), (rect.x+rect.width-8, rect.bottom-4), 1)
    if text_surf:
        # subtle text shadow for readability
        sh = text_surf.copy()
        # cheap shadow: blit offset dark
        surf.blit(text_surf, (rect.centerx - text_surf.get_width()//2 +1, rect.centery - text_surf.get_height()//2 +1))
        surf.blit(text_surf, (rect.centerx - text_surf.get_width()//2, rect.centery - text_surf.get_height()//2))

def glass_panel(surf, rect, fill=(255,255,255,210), border=(0,0,0,160), radius=14):
    """Frosted glass panel — used for menus/shop."""
    # shadow
    draw_soft_shadow(surf, rect, radius=16, alpha=50)
    # body
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, fill, (0,0,rect.width,rect.height), border_radius=radius)
    surf.blit(panel, rect.topleft)
    pygame.draw.rect(surf, border if len(border)==3 else (0,0,0), rect, width=2, border_radius=radius)
    # top specular
    pygame.draw.line(surf, (255,255,255,110), (rect.x+14, rect.y+6), (rect.right-14, rect.y+6), 2)

def draw_parallax_layer(surf, cam_y, speed_factor, draw_fn):
    offset = int(cam_y * speed_factor) % 700
    draw_fn(surf, -offset)
    draw_fn(surf, 700 - offset)

def draw_cloud(surf, x, y, scale=1.0, alpha=170):
    # cached, high-detail cloud — 5 ellipses + soft shadow + highlight
    key = (round(scale,2), alpha)
    # we don't fully cache position — just shape
    s = pygame.Surface((int(110*scale), int(50*scale)), pygame.SRCALPHA)
    # shadow base
    pygame.draw.ellipse(s, (200,210,230, int(alpha*0.45)), (10*scale, 22*scale, 74*scale, 18*scale))
    # main puffs
    pygame.draw.ellipse(s, (255,255,255, alpha), (4*scale, 12*scale, 42*scale, 26*scale))
    pygame.draw.ellipse(s, (255,255,255, alpha), (26*scale, 4*scale, 56*scale, 32*scale))
    pygame.draw.ellipse(s, (255,255,255, alpha), (54*scale, 14*scale, 44*scale, 24*scale))
    pygame.draw.ellipse(s, (250,250,255, int(alpha*0.95)), (18*scale, 8*scale, 28*scale, 18*scale))
    # highlight top
    pygame.draw.ellipse(s, (255,255,255, int(alpha*0.75)), (32*scale, 6*scale, 22*scale, 10*scale))
    surf.blit(s, (int(x - s.get_width()//2), int(y - s.get_height()//2)))

def draw_rock_texture(surf, rect, base_color, accent_color, kind="rock"):
    pygame.draw.rect(surf, base_color, rect, border_radius=7)
    rnd = random.Random(hash((rect.x, rect.y, rect.width, rect.height)) % 100000)
    def _safe(a,b):
        return rnd.randint(min(a,b), max(a,b)) if max(a,b)>=min(a,b) else a
    # micro-cracks
    for _ in range(5 if rect.width>80 else 3):
        x1 = _safe(rect.x+6, rect.x+rect.width-8)
        y1 = _safe(rect.y+4, rect.y+rect.height-4)
        x2 = x1 + rnd.randint(-10, 10)
        y2 = y1 + rnd.randint(-6, 6)
        pygame.draw.line(surf, (0,0,0,90), (x1,y1), (x2,y2), 1)
        if rnd.random()<0.5:
            pygame.draw.circle(surf, tuple(max(0,c-22) for c in base_color), (x1,y1), rnd.randint(2,4))
    # highlight top edge with soft bevel
    pygame.draw.line(surf, tuple(min(255,c+42) for c in base_color), (rect.x+5, rect.y+2), (rect.x+rect.width-5, rect.y+2), 2)
    pygame.draw.line(surf, (255,255,255,55), (rect.x+6, rect.y+4), (rect.x+rect.width-6, rect.y+4), 1)
    pygame.draw.line(surf, (0,0,0,70), (rect.x+4, rect.bottom-4), (rect.x+rect.width-8, rect.bottom-4), 2)
    if kind=="magma":
        vx = rect.x + rect.width//2
        for i in range(2):
            px = vx + rnd.randint(-18,18)
            pygame.draw.line(surf, (255,90,20), (px, rect.y+2), (px+rnd.randint(-6,6), rect.y+rect.height-2), 2)
            draw_glow(surf, (px, rect.centery), 14, (255,60,0), 42)

def light_beam(surf, x, w, alpha=14, color=(255,255,210)):
    """Vertical god-ray."""
    beam = pygame.Surface((w, surf.get_height()), pygame.SRCALPHA)
    for i in range(w):
        a = int(alpha * (1 - abs(i - w/2)/(w/2+1)) * 0.9)
        pygame.draw.line(beam, (*color, a), (i,0), (i, surf.get_height()))
    surf.blit(beam, (x - w//2, 0), special_flags=pygame.BLEND_RGBA_ADD)

def noise_texture(surf, rect, alpha=10, color=(0,0,0)):
    """Subtle grain to break flat color."""
    n = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    rnd = random.Random(hash((rect.x,rect.y))%9999)
    for _ in range(rect.width*rect.height//180):
        x = rnd.randint(0, rect.width-1); y=rnd.randint(0, rect.height-1)
        n.set_at((x,y), (*color, rnd.randint(max(0,alpha-6), alpha+6)))
    surf.blit(n, rect.topleft)

def lighting_overlay(surf, color, alpha=38):
    over = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
    over.fill((*color, alpha))
    surf.blit(over, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
