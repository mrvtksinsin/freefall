import pygame

# Pencere
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
FPS = 60
TITLE = "FREEFALL - Dikey Dusus Oyunu"

# Fizik (gelişmiş)
GRAVITY = 1400.0
MAX_FALL_SPEED = 650.0
JUMP_FORCE = -480.0
# JUMP_SPEED legacy alias - JUMP_FORCE ile aynı
JUMP_SPEED = JUMP_FORCE
ROLL_SPEED_BOOST = 350.0
MOVE_SPEED = 380.0
HORIZONTAL_MAX_SPEED = 420.0
HORIZONTAL_ACCEL = 9.0
HORIZONTAL_FRICTION = 7.0
FAST_FALL_MULTIPLIER = 1.25
FRICTION = 0.88  # legacy, kullanılmıyor (HORIZONTAL_* kullanılıyor)
BOUNCE_DAMP = 0.0

# Zorluk
DIFFICULTY_GAP_SHRINK_PER_100M = 6  # her 100m'de gap 6px küçülür (min 90)
DIFFICULTY_SPACING_MIN = 170
DIFFICULTY_SPACING_START = 220

# Oyuncu boyut
PLAYER_W = 32
PLAYER_H = 42

# Kamera
CAMERA_FOLLOW_Y_RATIO = 0.38  # ekranın üstten %38'inde tut
CAMERA_SMOOTH = 6.0
# CAMERA_MIN_FOLLOW_SPEED legacy - artık kullanılmıyor, kamera lerp ile takip ediyor

# Dünya
WALL_THICKNESS = 28
OBSTACLE_SPACING = 220       # engeller arası dikey mesafe
OBSTACLE_MIN_HEIGHT = 22
OBSTACLE_MAX_HEIGHT = 34
GAP_MIN = 130                # geçilebilir boşluk (kolay oynanabilir)
GAP_MAX = 190
SAFE_START_DISTANCE = 600    # başlangıçta engelsiz alan (px)
WORLD_GEN_AHEAD = 3000       # kamera önünde bu kadar üret
WORLD_CLEAN_BEHIND = 1500    # kamera arkasında bu kadar sonra sil

# VS Bot yarışı — bitiş çizgisi mesafesi (px, ~160m, 70-90sn)
VS_BOT_FINISH_DISTANCE = 16000

# Mesafe
PIXELS_PER_METER = 100.0

# Seviye / Katman - 22 katman (HAVA'dan FRANSA'ya)
LEVELS = [
    {"level": 1,  "name": "HAVA",           "distance": 0,     "bg": (135, 206, 250), "wall": (120, 120, 120), "obstacle": (90, 90, 90),   "accent": (255,255,255)},
    {"level": 2,  "name": "TOPRAK",         "distance": 3000,  "bg": (139, 90, 43),    "wall": (101, 67, 33),  "obstacle": (110, 70, 30),  "accent": (160,120,80)},
    {"level": 3,  "name": "KAYA",           "distance": 7000,  "bg": (100, 100, 110),  "wall": (70, 70, 75),   "obstacle": (60, 60, 65),   "accent": (180,180,180)},
    {"level": 4,  "name": "MAGMA",          "distance": 12000, "bg": (40, 10, 10),     "wall": (80, 20, 20),   "obstacle": (120,30,10),   "accent": (255,80,0)},
    {"level": 5,  "name": "BUZUL",          "distance": 18000, "bg": (200, 230, 255),  "wall": (170,200,230),  "obstacle": (140,180,220),  "accent": (255,255,255)},
    {"level": 6,  "name": "DERIN",          "distance": 26000, "bg": (10, 20, 40),     "wall": (30, 50, 90),   "obstacle": (20,40,80),     "accent": (80,160,255)},
    {"level": 7,  "name": "KATMAN KAYASI",  "distance": 35000, "bg": (68, 58, 52),   "wall": (88, 78, 68),   "obstacle": (62, 52, 44),    "accent": (210,190,170)},
    {"level": 8,  "name": "KANALIZASYON",   "distance": 45000, "bg": (46, 58, 42),   "wall": (58, 72, 52),   "obstacle": (44, 62, 38),    "accent": (140,210,90)},
    {"level": 9,  "name": "CAFE",           "distance": 56000, "bg": (214, 184, 142), "wall": (168, 132, 92), "obstacle": (148, 112, 72),  "accent": (255,228,180)},
    {"level": 10, "name": "OFIS",           "distance": 68000, "bg": (222, 226, 232), "wall": (186, 192, 200), "obstacle": (168, 174, 184),  "accent": (90, 130, 210)},
    {"level": 11, "name": "BACKROOMS",      "distance": 80000, "bg": (205, 180, 120), "wall": (185, 165, 105), "obstacle": (175, 155, 95),   "accent": (255,255,180)},
    {"level": 12, "name": "GUC SANTRALI",   "distance": 93000, "bg": (70, 72, 78),   "wall": (92, 92, 96),   "obstacle": (62, 62, 66),    "accent": (255,220,0)},
    {"level": 13, "name": "MUZE",           "distance": 107000,"bg": (232, 226, 212), "wall": (212, 206, 192), "obstacle": (192, 186, 172),  "accent": (180,160,120)},
    {"level": 14, "name": "SINIF",          "distance": 122000,"bg": (182, 212, 182), "wall": (152, 182, 152), "obstacle": (132, 162, 132),  "accent": (255,255,255)},
    {"level": 15, "name": "FABRIKA",        "distance": 138000,"bg": (52, 52, 56),   "wall": (72, 72, 76),   "obstacle": (46, 46, 50),    "accent": (255,100,40)},
    {"level": 16, "name": "POLIGAN",        "distance": 155000,"bg": (82, 62, 122),  "wall": (102, 82, 142), "obstacle": (92, 72, 132),   "accent": (255,80,180)},
    {"level": 17, "name": "ORMAN",          "distance": 173000,"bg": (32, 72, 42),   "wall": (52, 92, 62),   "obstacle": (42, 82, 52),    "accent": (120,200,80)},
    {"level": 18, "name": "SARAY",          "distance": 192000,"bg": (222, 202, 162), "wall": (182, 162, 122), "obstacle": (162, 142, 102),  "accent": (255,215,0)},
    {"level": 19, "name": "KOY",            "distance": 212000,"bg": (152, 182, 122), "wall": (122, 152, 92),  "obstacle": (102, 132, 72),   "accent": (200,180,140)},
    {"level": 20, "name": "SEHIR",          "distance": 233000,"bg": (72, 82, 98),   "wall": (92, 102, 118), "obstacle": (62, 72, 88),    "accent": (100,180,255)},
    {"level": 21, "name": "TOKYO",          "distance": 255000,"bg": (22, 22, 42),   "wall": (42, 42, 72),   "obstacle": (32, 32, 62),    "accent": (255,50,150)},
    {"level": 22, "name": "FRANSA",         "distance": 278000,"bg": (182, 202, 232), "wall": (152, 172, 202), "obstacle": (132, 152, 182),  "accent": (255,100,100)},
    {"level": 23, "name": "FINAL",          "distance": 302000,"bg": (12,  12,  28),  "wall": (40,  40,  80),  "obstacle": (90,  70,  140),   "accent": (255,215,0)},
]

# Karakterler - FINAL RELEASE: 18 karakter (seviye ile acilma)
CHARACTERS = [
    {"id": "cop_adam",    "name": "Cop Adam",    "level": 1,  "color": (80,80,80),    "accent": (200,200,200)},
    {"id": "soylu",       "name": "Soylu",       "level": 2,  "color": (180,30,30),   "accent": (255,215,0)},
    {"id": "madame",      "name": "Madame",      "level": 3,  "color": (200,50,120),  "accent": (255,180,220)},
    {"id": "kadin",       "name": "Kadin",       "level": 4,  "color": (255,120,150), "accent": (255,200,210)},
    {"id": "soytari",     "name": "Soytari",     "level": 5,  "color": (150,40,160),  "accent": (255,220,60)},
    {"id": "erkek",       "name": "Erkek",       "level": 6,  "color": (30,100,200),  "accent": (180,210,255)},
    {"id": "ayi",         "name": "Ayi",         "level": 7,  "color": (120,80,50),   "accent": (80,50,30)},
    {"id": "noel_baba",   "name": "Noel Baba",   "level": 8,  "color": (200,20,20),   "accent": (255,255,255)},
    {"id": "tavuk",       "name": "Tavuk",       "level": 9,  "color": (255,230,150), "accent": (255,150,40)},
    {"id": "ninja",       "name": "Ninja",       "level": 10, "color": (20,20,20),    "accent": (255,50,50)},
    {"id": "robot",       "name": "Robot",       "level": 11, "color": (150,160,175), "accent": (80,220,255)},
    {"id": "sihirbaz",    "name": "Sihirbaz",    "level": 12, "color": (90,30,150),   "accent": (180,100,255)},
    {"id": "iskelet",     "name": "Iskelet",     "level": 13, "color": (230,230,225), "accent": (120,120,120)},
    {"id": "asker",       "name": "Asker",       "level": 14, "color": (60,100,40),   "accent": (120,180,90)},
    {"id": "korsan",      "name": "Korsan",      "level": 15, "color": (60,55,110),   "accent": (220,180,70)},
    {"id": "balon",       "name": "Balon",       "level": 16, "color": (255,200,50),  "accent": (255,100,100)},
    {"id": "gotik_kiz",   "name": "Gotik Kiz",   "level": 17, "color": (40,20,50),    "accent": (200,60,120)},
    {"id": "gotik_erkek", "name": "Gotik Erkek", "level": 18, "color": (25,25,45),    "accent": (140,80,200)},
]

# Mağaza - her kategori x10 (toplam 40 ürün)
SHOP_ITEMS = {
    "hat": [
        {"id": "hat1",  "name": "Sapka 1",  "price": 10,  "icon": "H1"},
        {"id": "hat2",  "name": "Sapka 2",  "price": 25,  "icon": "H2"},
        {"id": "hat3",  "name": "Sapka 3",  "price": 40,  "icon": "H3"},
        {"id": "hat4",  "name": "Sapka 4",  "price": 60,  "icon": "H4"},
        {"id": "hat5",  "name": "Sapka 5",  "price": 80,  "icon": "H5"},
        {"id": "hat6",  "name": "Sapka 6",  "price": 100, "icon": "H6"},
        {"id": "hat7",  "name": "Sapka 7",  "price": 130, "icon": "H7"},
        {"id": "hat8",  "name": "Sapka 8",  "price": 160, "icon": "H8"},
        {"id": "hat9",  "name": "Sapka 9",  "price": 200, "icon": "H9"},
        {"id": "hat10", "name": "Sapka 10", "price": 250, "icon": "H10"},
    ],
    "bag": [
        {"id": "bag1",  "name": "Canta 1",  "price": 30,  "icon": "C1"},
        {"id": "bag2",  "name": "Canta 2",  "price": 50,  "icon": "C2"},
        {"id": "bag3",  "name": "Canta 3",  "price": 75,  "icon": "C3"},
        {"id": "bag4",  "name": "Canta 4",  "price": 90,  "icon": "C4"},
        {"id": "bag5",  "name": "Canta 5",  "price": 110, "icon": "C5"},
        {"id": "bag6",  "name": "Canta 6",  "price": 135, "icon": "C6"},
        {"id": "bag7",  "name": "Canta 7",  "price": 165, "icon": "C7"},
        {"id": "bag8",  "name": "Canta 8",  "price": 200, "icon": "C8"},
        {"id": "bag9",  "name": "Canta 9",  "price": 240, "icon": "C9"},
        {"id": "bag10", "name": "Canta 10", "price": 285, "icon": "C10"},
    ],
    "glasses": [
        {"id": "glasses1",  "name": "Gozluk 1",  "price": 15,  "icon": "G1"},
        {"id": "glasses2",  "name": "Gozluk 2",  "price": 35,  "icon": "G2"},
        {"id": "glasses3",  "name": "Gozluk 3",  "price": 55,  "icon": "G3"},
        {"id": "glasses4",  "name": "Gozluk 4",  "price": 75,  "icon": "G4"},
        {"id": "glasses5",  "name": "Gozluk 5",  "price": 95,  "icon": "G5"},
        {"id": "glasses6",  "name": "Gozluk 6",  "price": 120, "icon": "G6"},
        {"id": "glasses7",  "name": "Gozluk 7",  "price": 145, "icon": "G7"},
        {"id": "glasses8",  "name": "Gozluk 8",  "price": 175, "icon": "G8"},
        {"id": "glasses9",  "name": "Gozluk 9",  "price": 210, "icon": "G9"},
        {"id": "glasses10", "name": "Gozluk 10", "price": 250, "icon": "G10"},
    ],
    "cane": [
        {"id": "cane1",  "name": "Baston 1",  "price": 50,  "icon": "B1"},
        {"id": "cane2",  "name": "Baston 2",  "price": 80,  "icon": "B2"},
        {"id": "cane3",  "name": "Baston 3",  "price": 120, "icon": "B3"},
        {"id": "cane4",  "name": "Baston 4",  "price": 150, "icon": "B4"},
        {"id": "cane5",  "name": "Baston 5",  "price": 180, "icon": "B5"},
        {"id": "cane6",  "name": "Baston 6",  "price": 215, "icon": "B6"},
        {"id": "cane7",  "name": "Baston 7",  "price": 255, "icon": "B7"},
        {"id": "cane8",  "name": "Baston 8",  "price": 300, "icon": "B8"},
        {"id": "cane9",  "name": "Baston 9",  "price": 350, "icon": "B9"},
        {"id": "cane10", "name": "Baston 10", "price": 400, "icon": "B10"},
    ],
}

# Temalar - 18 tema (genişletildi, uyumlu paletler, mor ana renk yok)
THEMES = [
    {"id": "beyaz",       "name": "BEYAZ",        "bg": (245,245,245), "ui_bg": (255,255,255), "ui_text": (30,30,30),   "button": (220,220,220), "button_hover": (200,200,200), "hud": (30,30,30),   "accent": (255,215,0), "coin": (255,215,0), "danger": (200,40,40), "success": (40,160,80), "border": (200,200,200), "glow": (255,215,0, 60), "particle": (200,200,210)},
    {"id": "siyah",       "name": "SIYAH",        "bg": (18,18,18),   "ui_bg": (35,35,35),   "ui_text": (240,240,240), "button": (60,60,60),   "button_hover": (80,80,80),   "hud": (240,240,240), "accent": (255,215,0), "coin": (255,215,0), "danger": (220,50,50), "success": (80,200,120), "border": (60,60,60), "glow": (255,215,0, 40), "particle": (80,80,90)},
    {"id": "sari_kirmizi", "name": "SARI-KIRMIZI", "bg": (255,240,180), "ui_bg": (255,220,100), "ui_text": (120,20,20),  "button": (255,80,80),   "button_hover": (255,60,60),   "hud": (120,20,20),  "accent": (255,80,80), "coin": (255,215,0), "danger": (180,30,30), "success": (40,160,80), "border": (220,180,100), "glow": (255,80,80, 50), "particle": (255,200,100)},
    {"id": "kirmizi_siyah","name":"KIRMIZI-SIYAH", "bg": (60,10,10),   "ui_bg": (30,10,10),   "ui_text": (255,200,200), "button": (180,30,30),   "button_hover": (200,40,40),   "hud": (255,220,220), "accent": (255,60,60), "coin": (255,215,0), "danger": (220,40,40), "success": (80,200,120), "border": (80,20,20), "glow": (180,30,30, 60), "particle": (180,60,60)},
    {"id": "siyah_mavi",  "name": "SIYAH-MAVI",   "bg": (10,20,40),    "ui_bg": (20,35,70),   "ui_text": (180,220,255), "button": (30,80,150),   "button_hover": (40,100,180),  "hud": (180,220,255), "accent": (80,160,255), "coin": (255,215,0), "danger": (200,60,60), "success": (80,200,120), "border": (30,50,90), "glow": (80,160,255, 50), "particle": (80,140,200)},
    {"id": "mor_mavi",    "name": "MOR-MAVI",     "bg": (40,20,60),    "ui_bg": (60,30,90),   "ui_text": (220,200,255), "button": (120,60,180),  "button_hover": (140,80,200),  "hud": (220,200,255), "accent": (180,120,255), "coin": (255,215,0), "danger": (200,50,80), "success": (80,200,160), "border": (80,50,120), "glow": (120,60,180, 50), "particle": (160,120,220)},
    {"id": "pembe_sari",  "name": "PEMBE-SARI",   "bg": (255,210,230), "ui_bg": (255,230,160), "ui_text": (120,30,80),  "button": (255,150,200), "button_hover": (255,130,180), "hud": (120,30,80),  "accent": (255,100,180), "coin": (255,215,0), "danger": (200,40,80), "success": (80,180,120), "border": (255,200,220), "glow": (255,150,200, 50), "particle": (255,180,220)},
    {"id": "yesil_gri",   "name": "YESIL-GRI",    "bg": (200,220,200), "ui_bg": (180,200,180), "ui_text": (30,60,30),   "button": (100,150,100), "button_hover": (80,130,80),   "hud": (30,60,30),   "accent": (80,160,80), "coin": (255,215,0), "danger": (160,50,50), "success": (40,160,80), "border": (150,180,150), "glow": (80,160,80, 50), "particle": (120,180,120)},
    {"id": "turuncu_siyah","name":"TURUNCU-SIYAH","bg": (32,18,8),    "ui_bg": (58,32,14),    "ui_text": (255,200,120), "button": (220,110,30),  "button_hover": (240,130,40),  "hud": (255,220,160), "accent": (255,140,40), "coin": (255,215,0), "danger": (200,60,40), "success": (80,180,80), "border": (80,40,20), "glow": (220,110,30, 60), "particle": (255,160,80)},
    {"id": "kahve_krem",  "name": "KAHVE-KREM",   "bg": (242,228,210), "ui_bg": (255,242,220), "ui_text": (90,50,20),    "button": (180,130,90),  "button_hover": (200,150,110), "hud": (90,50,20),    "accent": (180,130,90), "coin": (200,160,50), "danger": (160,40,40), "success": (80,160,80), "border": (210,190,170), "glow": (180,130,90, 50), "particle": (200,180,150)},
    {"id": "crimson",     "name": "CRIMSON",      "bg": (28,8,12),    "ui_bg": (48,16,22),    "ui_text": (255,210,210), "button": (160,30,45),   "button_hover": (185,45,60),   "hud": (255,180,180), "accent": (220,50,70), "coin": (255,215,0), "danger": (200,30,30), "success": (80,200,120), "border": (80,20,30), "glow": (160,30,45, 60), "particle": (200,60,80)},
    {"id": "ice",         "name": "ICE",          "bg": (210,235,255), "ui_bg": (235,245,255), "ui_text": (20,40,70),   "button": (120,180,220), "button_hover": (140,200,235), "hud": (20,50,90),    "accent": (80,160,220), "coin": (255,215,0), "danger": (180,50,50), "success": (40,160,100), "border": (180,210,235), "glow": (120,180,220, 50), "particle": (180,220,255)},
    {"id": "forest",      "name": "FOREST",       "bg": (22,38,28),   "ui_bg": (38,58,42),   "ui_text": (190,230,190), "button": (60,110,70),   "button_hover": (80,135,90),   "hud": (170,220,170), "accent": (80,160,80), "coin": (255,215,0), "danger": (160,40,40), "success": (40,160,80), "border": (50,80,60), "glow": (60,110,70, 60), "particle": (80,160,100)},
    {"id": "desert",      "name": "DESERT",       "bg": (232,210,170), "ui_bg": (245,225,185), "ui_text": (90,60,30),   "button": (200,160,110), "button_hover": (215,175,125), "hud": (90,60,30),    "accent": (200,160,110), "coin": (255,215,0), "danger": (160,50,40), "success": (80,160,80), "border": (210,190,160), "glow": (200,160,110, 50), "particle": (220,190,150)},
    {"id": "ocean",       "name": "OCEAN",        "bg": (12,32,58),   "ui_bg": (22,48,82),   "ui_text": (170,210,245), "button": (30,90,140),   "button_hover": (45,110,165),  "hud": (150,200,235), "accent": (80,160,220), "coin": (255,215,0), "danger": (200,60,60), "success": (80,200,120), "border": (30,60,100), "glow": (30,90,140, 60), "particle": (60,140,200)},
    {"id": "neon_cyan",   "name": "NEON CYAN",    "bg": (8,22,26),    "ui_bg": (16,42,48),   "ui_text": (180,255,245), "button": (0,180,170),    "button_hover": (20,200,190),  "hud": (140,255,240), "accent": (0,220,200), "coin": (255,215,0), "danger": (220,40,80), "success": (80,220,160), "border": (20,60,70), "glow": (0,180,170, 60), "particle": (0,220,200)},
    {"id": "golden",      "name": "GOLDEN",       "bg": (28,22,8),    "ui_bg": (48,38,18),   "ui_text": (255,230,160), "button": (180,140,40),   "button_hover": (205,165,55),  "hud": (255,215,100), "accent": (255,215,0), "coin": (255,215,0), "danger": (180,50,40), "success": (80,180,80), "border": (80,60,30), "glow": (180,140,40, 60), "particle": (255,215,100)},
    {"id": "blood_moon",  "name": "BLOOD MOON",   "bg": (32,8,8),     "ui_bg": (52,14,14),   "ui_text": (255,200,180), "button": (140,30,20),   "button_hover": (165,45,30),   "hud": (255,180,160), "accent": (220,60,40), "coin": (255,215,0), "danger": (200,30,30), "success": (80,160,80), "border": (80,20,20), "glow": (140,30,20, 60), "particle": (220,80,60)},
    {"id": "sunset_orange","name": "SUNSET ORANGE","bg": (42,22,12),  "ui_bg": (66,34,20),   "ui_text": (255,225,190), "button": (220,110,40),  "button_hover": (240,130,55),  "hud": (255,215,160), "accent": (255,140,50), "coin": (255,215,0), "danger": (190,50,30), "success": (80,180,90), "border": (90,45,25), "glow": (220,110,40, 60), "particle": (255,170,90)},
    {"id": "rose_white",  "name": "ROSE WHITE",   "bg": (250,240,242), "ui_bg": (255,250,252), "ui_text": (120,40,60),  "button": (235,180,190), "button_hover": (245,200,210), "hud": (120,40,60),  "accent": (220,90,120), "coin": (220,170,50), "danger": (170,40,60), "success": (60,160,100), "border": (225,195,205), "glow": (220,90,120, 45), "particle": (240,180,195)},
    {"id": "industrial_gray","name": "INDUSTRIAL GRAY","bg": (38,40,44), "ui_bg": (58,60,66), "ui_text": (225,228,232), "button": (95,100,108), "button_hover": (115,120,128), "hud": (210,215,220), "accent": (255,200,60), "coin": (255,215,0), "danger": (200,60,60), "success": (80,190,110), "border": (70,72,78), "glow": (150,155,165, 45), "particle": (140,145,155)},
    {"id": "coffee_cream","name": "COFFEE CREAM", "bg": (48,34,24),   "ui_bg": (72,52,36),   "ui_text": (245,230,200), "button": (150,105,70),  "button_hover": (170,125,85),  "hud": (240,220,180), "accent": (220,170,110), "coin": (255,215,0), "danger": (180,60,50), "success": (90,180,110), "border": (90,65,45), "glow": (150,105,70, 55), "particle": (210,180,140)},
    {"id": "arctic_night","name": "ARCTIC NIGHT", "bg": (8,16,32),    "ui_bg": (16,28,54),   "ui_text": (190,220,245), "button": (40,70,110),   "button_hover": (55,90,135),   "hud": (170,205,235), "accent": (120,190,255), "coin": (255,215,0), "danger": (200,70,70), "success": (80,200,150), "border": (25,45,80), "glow": (60,110,180, 55), "particle": (120,180,235)},
    {"id": "toxic_green","name": "TOXIC GREEN",  "bg": (14,28,12),   "ui_bg": (26,48,22),   "ui_text": (200,255,190), "button": (70,160,50),   "button_hover": (90,185,65),   "hud": (180,240,170), "accent": (140,255,100), "coin": (255,235,50), "danger": (200,60,40), "success": (60,200,80), "border": (40,70,35), "glow": (70,160,50, 60), "particle": (140,230,100)},
    {"id": "steel_blue", "name": "STEEL BLUE",   "bg": (32,40,52),   "ui_bg": (50,62,80),   "ui_text": (215,225,235), "button": (90,110,135),  "button_hover": (110,130,155), "hud": (200,215,230), "accent": (140,180,220), "coin": (255,215,0), "danger": (190,60,60), "success": (80,190,120), "border": (65,75,90), "glow": (90,110,135, 50), "particle": (150,175,200)},
    {"id": "retro_arcade","name": "RETRO ARCADE", "bg": (12,10,24),   "ui_bg": (24,20,48),   "ui_text": (255,240,180), "button": (220,60,120),  "button_hover": (240,80,140),  "hud": (255,220,120), "accent": (0,230,200), "coin": (255,235,0), "danger": (230,40,80), "success": (60,230,140), "border": (50,40,90), "glow": (220,60,120, 55), "particle": (0,230,200)},
    {"id": "monochrome", "name": "MONOCHROME",   "bg": (32,32,32),   "ui_bg": (55,55,55),   "ui_text": (240,240,240), "button": (120,120,120), "button_hover": (150,150,150), "hud": (230,230,230), "accent": (240,240,240), "coin": (230,230,230), "danger": (120,120,120), "success": (200,200,200), "border": (80,80,80), "glow": (200,200,200, 40), "particle": (180,180,180)},
    {"id": "royal_gold", "name": "ROYAL GOLD",   "bg": (20,16,8),    "ui_bg": (38,30,14),   "ui_text": (250,235,190), "button": (170,130,50),   "button_hover": (195,155,65),  "hud": (245,225,160), "accent": (255,215,0), "coin": (255,225,80), "danger": (190,60,40), "success": (90,190,110), "border": (70,55,25), "glow": (200,165,60, 60), "particle": (250,215,120)},
]

# --- FAZ 4: Bolum Atmosfer Kimligi (veri tabanli, tema'dan bagimsiz) ---
# Her bolum icin: background_tint/secondary_tint/glow/particle_type/particle_density/ambient_strength/music_key
# world.py ve particles.py mevcut sistemi koruyarak bu veriyi referans alir.
# Tema overlay'i ayri katmanda cok dusuk alpha ile blend edilir - bolum kimligi korunur.
LEVEL_ATMOSPHERES = {
    "HAVA":           {"background_tint": (135,206,250), "secondary_tint": (210,235,255), "glow": (255,255,220), "particle_type": "dust",  "particle_density": 0.55, "particle_cap": 24, "ambient_strength": 0.10, "vignette": 0.10, "music_key": "ambient_air"},
    "TOPRAK":         {"background_tint": (139, 90, 43),  "secondary_tint": ( 68, 44, 20), "glow": (255,220,160), "particle_type": "dust",  "particle_density": 0.38, "particle_cap": 16, "ambient_strength": 0.08, "vignette": 0.14, "music_key": "earthy"},
    "KAYA":           {"background_tint": (100,100,110),  "secondary_tint": ( 28, 28, 34), "glow": (180,180,190), "particle_type": "dust",  "particle_density": 0.32, "particle_cap": 14, "ambient_strength": 0.18, "vignette": 0.18, "music_key": "dark_rock"},
    "MAGMA":          {"background_tint": ( 40, 10, 10),  "secondary_tint": ( 18,  6,  8), "glow": (255, 70, 20), "particle_type": "spark", "particle_density": 0.46, "particle_cap": 20, "ambient_strength": 0.22, "vignette": 0.20, "music_key": "magma"},
    "BUZUL":          {"background_tint": (200,230,255),  "secondary_tint": (172,202,232), "glow": (200,230,255), "particle_type": "snow",  "particle_density": 0.62, "particle_cap": 28, "ambient_strength": 0.12, "vignette": 0.12, "music_key": "ice"},
    "DERIN":          {"background_tint": ( 10, 20, 40),  "secondary_tint": (  6, 10, 22), "glow": ( 80,140,255), "particle_type": "dust",  "particle_density": 0.36, "particle_cap": 18, "ambient_strength": 0.28, "vignette": 0.28, "music_key": "deep"},
    "KATMAN KAYASI":  {"background_tint": ( 68, 58, 52),  "secondary_tint": ( 52, 44, 40), "glow": (160,140,120), "particle_type": "dust",  "particle_density": 0.30, "particle_cap": 12, "ambient_strength": 0.12, "vignette": 0.16, "music_key": "strata"},
    "KANALIZASYON":   {"background_tint": ( 46, 58, 42),  "secondary_tint": ( 36, 48, 34), "glow": (120,180, 80), "particle_type": "smoke", "particle_density": 0.28, "particle_cap": 12, "ambient_strength": 0.14, "vignette": 0.18, "music_key": "sewer"},
    "CAFE":           {"background_tint": (214,184,142),  "secondary_tint": (196,164,122), "glow": (255,200,140), "particle_type": "smoke", "particle_density": 0.26, "particle_cap": 10, "ambient_strength": 0.10, "vignette": 0.10, "music_key": "cafe"},
    "OFIS":           {"background_tint": (222,226,232),  "secondary_tint": (210,216,224), "glow": (200,220,255), "particle_type": "dust",  "particle_density": 0.20, "particle_cap": 10, "ambient_strength": 0.08, "vignette": 0.10, "music_key": "office"},
    "BACKROOMS":      {"background_tint": (205,180,120),  "secondary_tint": (188,164,108), "glow": (255,240,160), "particle_type": "dust",  "particle_density": 0.30, "particle_cap": 12, "ambient_strength": 0.14, "vignette": 0.16, "music_key": "backrooms"},
    "GUC SANTRALI":   {"background_tint": ( 70, 72, 78),  "secondary_tint": ( 58, 60, 66), "glow": (255,220,  0), "particle_type": "spark", "particle_density": 0.22, "particle_cap": 10, "ambient_strength": 0.16, "vignette": 0.18, "music_key": "power"},
    "MUZE":           {"background_tint": (232,226,212),  "secondary_tint": (216,210,196), "glow": (255,230,160), "particle_type": "spark", "particle_density": 0.18, "particle_cap": 10, "ambient_strength": 0.10, "vignette": 0.12, "music_key": "museum"},
    "SINIF":          {"background_tint": (182,212,182),  "secondary_tint": (158,188,158), "glow": (255,255,220), "particle_type": "dust",  "particle_density": 0.24, "particle_cap": 10, "ambient_strength": 0.08, "vignette": 0.10, "music_key": "classroom"},
    "FABRIKA":        {"background_tint": ( 52, 52, 56),  "secondary_tint": ( 42, 42, 46), "glow": (255,100, 40), "particle_type": "smoke", "particle_density": 0.26, "particle_cap": 12, "ambient_strength": 0.16, "vignette": 0.18, "music_key": "factory"},
    "POLIGAN":        {"background_tint": ( 82, 62,122),  "secondary_tint": ( 68, 48,108), "glow": (255, 80,180), "particle_type": "dust",  "particle_density": 0.28, "particle_cap": 12, "ambient_strength": 0.12, "vignette": 0.14, "music_key": "polygon"},
    "ORMAN":          {"background_tint": ( 32, 72, 42),  "secondary_tint": ( 28, 60, 38), "glow": (120,200, 80), "particle_type": "dust",  "particle_density": 0.30, "particle_cap": 12, "ambient_strength": 0.12, "vignette": 0.14, "music_key": "forest"},
    "SARAY":          {"background_tint": (222,202,162),  "secondary_tint": (208,188,148), "glow": (255,215,  0), "particle_type": "spark", "particle_density": 0.24, "particle_cap": 10, "ambient_strength": 0.12, "vignette": 0.14, "music_key": "palace"},
    "KOY":            {"background_tint": (152,182,122),  "secondary_tint": (132,162,102), "glow": (255,200,100), "particle_type": "dust",  "particle_density": 0.28, "particle_cap": 12, "ambient_strength": 0.10, "vignette": 0.10, "music_key": "village"},
    "SEHIR":          {"background_tint": ( 72, 82, 98),  "secondary_tint": ( 60, 68, 84), "glow": (100,180,255), "particle_type": "smoke", "particle_density": 0.22, "particle_cap": 10, "ambient_strength": 0.14, "vignette": 0.16, "music_key": "city"},
    "TOKYO":          {"background_tint": ( 22, 22, 42),  "secondary_tint": ( 18, 18, 32), "glow": (255, 50,150), "particle_type": "spark", "particle_density": 0.24, "particle_cap": 10, "ambient_strength": 0.18, "vignette": 0.20, "music_key": "tokyo"},
    "FRANSA":         {"background_tint": (182,202,232),  "secondary_tint": (162,182,212), "glow": (255,200,200), "particle_type": "dust",  "particle_density": 0.26, "particle_cap": 12, "ambient_strength": 0.10, "vignette": 0.10, "music_key": "france"},
    "FINAL":          {"background_tint": ( 12, 12, 28),  "secondary_tint": (  8,  8, 18), "glow": (255,215,  0), "particle_type": "spark", "particle_density": 0.42, "particle_cap": 20, "ambient_strength": 0.32, "vignette": 0.32, "music_key": "final"},
}

# --- FAZ6: Combat / Silahlar (arcade, moduler) ---
WEAPONS = {
    "fist": {
        "id": "fist", "name": "YUMRUK", "price": 0,
        "damage": 1, "range": 88, "cooldown": 0.34, "duration": 0.22,
        "hitbox_w": 28, "hitbox_h": 28, "knockback": 48, "stagger": 0.42,
        "color": (255, 220, 180), "trail": None, "icon": "F"
    },
    "beam_sword": {
        "id": "beam_sword", "name": "IŞIN KILICI", "price": 150,
        "damage": 2, "range": 148, "cooldown": 0.62, "duration": 0.33,
        "hitbox_w": 42, "hitbox_h": 32, "knockback": 72, "stagger": 0.68,
        "color": (80, 220, 255), "trail": (80, 220, 255), "icon": "S"
    },
}

def get_weapon(weapon_id):
    return WEAPONS.get(weapon_id, WEAPONS["fist"])

# --- FAZ11: Lore / World Building ---
LEVEL_LORE = {
    1:  {"title": "HAVA",           "text": "İlk düşüş burada başlar. Aşağıda ne olduğunu henüz bilmiyorsun.", "detail": "◊"},
    2:  {"title": "TOPRAK",         "text": "Zemin artık daha yakın. Güvenli görünen hiçbir şey gerçekten güvenli değil.", "detail": "Kökler arasında bir işaret var."},
    3:  {"title": "KAYA",           "text": "Taşlar üst üste. Biri kayarsa hepsi kayar.", "detail": "Duvarlarda çizikler."},
    4:  {"title": "MAGMA",          "text": "Sıcaklık kemiklerine işliyor. Işık aşağıdan geliyor.", "detail": "◊ yine burada."},
    5:  {"title": "BUZUL",          "text": "Soğuk nefesini kesiyor. Yukarısı çok uzakta.", "detail": "Buzun altında bir şey var."},
    6:  {"title": "DERİN",          "text": "Işık yok. Sadece derinliğin sesi var.", "detail": "◊ derinde parlıyor."},
    7:  {"title": "KATMAN KAYASI",  "text": "Katmanlar yılları sayıyor. Sen sadece bir çizgisin.", "detail": "Taş aynı sembolü taşıyor."},
    8:  {"title": "KANALİZASYON",   "text": "Su yavaş akıyor. Kokunun ardında bir şey saklanıyor.", "detail": "Borularda fısıltı."},
    9:  {"title": "KAFE",           "text": "Bir zamanlar burada kahve kokusu vardı. Şimdi sadece toz.", "detail": "Bir fincan hâlâ sıcak."},
    10: {"title": "OFİS",           "text": "Masalar boş. Ekranlar hâlâ açık.", "detail": "E-postalar hiç gönderilmemiş."},
    11: {"title": "BACKROOMS",      "text": "Sarı ışık hiç sönmüyor. Zaman yok gibi.", "detail": "◊ tavanda."},
    12: {"title": "GÜÇ SANTRALİ",   "text": "Kablolar uğulduyor. Enerji hâlâ bir yere gidiyor.", "detail": "◊ panoda yanıyor."},
    13: {"title": "MÜZE",           "text": "Eserler yerinde. Ziyaretçiler yok.", "detail": "Bir kayıt: 'Aşağı bakma.'"},
    14: {"title": "SINIF",          "text": "Tahta silinmiş ama bir cümle kalmış: 'Unutma'.", "detail": "Sıralar düzenli."},
    15: {"title": "FABRİKA",        "text": "Metal gıcırdıyor. Fabrika hâlâ çalışıyor.", "detail": "Makine aynı sembolü damgalıyor."},
    16: {"title": "POLİGON",        "text": "Hedef tahtaları boş. Atışlar yukarıdan değil, aşağıdan gelmiş.", "detail": "Mermiler erimiş."},
    17: {"title": "ORMAN",          "text": "Yapraklar düşmüyor, yükseliyor. Garip.", "detail": "Ağaçlar izliyor."},
    18: {"title": "SARAY",          "text": "Altın solmuş. Taht boş, ama ayak izleri taze.", "detail": "◊ tahtın arkasında."},
    19: {"title": "KÖY",            "text": "Evler sessiz. Kapılar dışarıdan kilitli.", "detail": "Bir evde ışık yanıyor."},
    20: {"title": "ŞEHİR",          "text": "Şehir uyumuyor, sadece izliyor.", "detail": "Tabelalar aynı sembolü gösteriyor."},
    21: {"title": "TOKYO",          "text": "Neonlar yanıp sönüyor. Kalabalık yok, ama gölgeler var.", "detail": "◊ her tabelada."},
    22: {"title": "FRANSA",         "text": "Işık zarif, ama hava ağır. Son kapı yakın.", "detail": "Son kayıt: 'Buradaydı.'"},
    23: {"title": "FINAL",          "text": "En alttasın. Monster sustu. Düşüş bitti mi, yoksa yeni mi başlıyor?", "detail": "◊ artık her yerde."},
}

CHARACTER_LORE = {
    "cop_adam":    "Sokakları bilir. Düşerken bile etrafını izler.",
    "soylu":       "Altın solsa da duruşu değişmez.",
    "madame":      "Zarafeti düşerken bile bozulmaz.",
    "kadin":       "Sessiz ama kararlı. Adım adım.",
    "soytari":     "Gülüşü yankılanır, kimse duymaz.",
    "erkek":       "Sade ve dengeli. Fazla konuşmaz.",
    "ayi":         "Yavaş görünür, ama asla vazgeçmez.",
    "noel_baba":   "Hediyeleri bitmiş, ama yolu biliyor.",
    "tavuk":       "Korkak değil, sadece dikkatli.",
    "ninja":       "Gölge gibi. Sesi duyulmaz.",
    "robot":       "Hesaplar, ama düşüşü hesaplayamadı.",
    "sihirbaz":    "Bir zamanlar numaraları gerçek sanılırdı.",
    "iskelet":     "Çoktan düşmüş, ama hâlâ düşüyor.",
    "asker":       "Emir beklemiyor, sadece ilerliyor.",
    "korsan":      "Hazinesi yok, ama rotası var.",
    "balon":       "Hafif. Rüzgar nereye isterse.",
    "gotik_kiz":   "Karanlığı sever, karanlık onu sever.",
    "gotik_erkek": "Sessiz, gölgelerde rahat.",
}

MONSTER_LORE = "Onu kimse çağırmadı. Belki de zaten hep buradaydı. Yaklaştığında hava ağırlaşır."

REPEATING_SYMBOL = "◊"

# Hizli erisim helper'lar (world/particles/audio ortak kullanir)
def get_level_atmosphere(level_name):
    return LEVEL_ATMOSPHERES.get(level_name, LEVEL_ATMOSPHERES["HAVA"])

def get_music_key(level_name):
    atm = LEVEL_ATMOSPHERES.get(level_name)
    if atm:
        return atm.get("music_key", "ambient_air")
    return "ambient_air"
