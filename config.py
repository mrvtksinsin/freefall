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

# Karakterler - seviye ile açılma (18 karakter)
CHARACTERS = [
    {"id": "cop_adam",    "name": "Cop Adam",   "level": 1, "color": (80,80,80),   "accent": (200,200,200)},
    {"id": "soylu",       "name": "Soylu",      "level": 2, "color": (180,30,30),  "accent": (255,215,0)},
    {"id": "madame",      "name": "Madame",     "level": 3, "color": (200,50,120), "accent": (255,180,220)},
    {"id": "kadin",       "name": "Kadin",      "level": 4, "color": (255,120,150),"accent": (255,200,210)},
    {"id": "erkek",       "name": "Erkek",      "level": 5, "color": (30,100,200), "accent": (180,210,255)},
    {"id": "noel_baba",   "name": "Noel Baba",  "level": 6, "color": (200,20,20),  "accent": (255,255,255)},
    {"id": "ninja",       "name": "Ninja",      "level": 7, "color": (20,20,20),   "accent": (255,50,50)},
    {"id": "sihirbaz",    "name": "Sihirbaz",   "level": 8, "color": (90,30,150),  "accent": (180,100,255)},
    {"id": "asker",       "name": "Asker",      "level": 9, "color": (60,100,40),  "accent": (120,180,90)},
    {"id": "balon",       "name": "Balon",      "level": 10,"color": (255,200,50), "accent": (255,100,100)},
    {"id": "soytari",     "name": "Soytari",    "level": 4, "color": (200,40,120), "accent": (255,220,40)},
    {"id": "ayi",         "name": "Ayi",        "level": 5, "color": (120,80,50),  "accent": (230,200,160)},
    {"id": "tavuk",       "name": "Tavuk",      "level": 6, "color": (255,240,180),"accent": (255,80,40)},
    {"id": "robot",       "name": "Robot",      "level": 7, "color": (160,170,180),"accent": (80,220,255)},
    {"id": "iskelet",     "name": "Iskelet",    "level": 8, "color": (230,230,220),"accent": (60,60,60)},
    {"id": "korsan",      "name": "Korsan",     "level": 9, "color": (40,40,90),   "accent": (200,40,40)},
    {"id": "gotik_kiz",   "name": "Gotik Kiz",  "level": 10,"color": (120,20,60),  "accent": (180,80,160)},
    {"id": "gotik_erkek", "name": "Gotik Erkek","level": 10,"color": (30,30,50),   "accent": (140,80,180)},
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

# Temalar - 10 tema (max)
THEMES = [
    {"id": "beyaz",       "name": "BEYAZ",        "bg": (245,245,245), "ui_bg": (255,255,255), "ui_text": (30,30,30),   "button": (220,220,220), "button_hover": (200,200,200), "hud": (30,30,30)},
    {"id": "siyah",       "name": "SIYAH",        "bg": (18,18,18),   "ui_bg": (35,35,35),   "ui_text": (240,240,240), "button": (60,60,60),   "button_hover": (80,80,80),   "hud": (240,240,240)},
    {"id": "sari_kirmizi", "name": "SARI-KIRMIZI", "bg": (255,240,180), "ui_bg": (255,220,100), "ui_text": (120,20,20),  "button": (255,80,80),   "button_hover": (255,60,60),   "hud": (120,20,20)},
    {"id": "kirmizi_siyah","name":"KIRMIZI-SIYAH", "bg": (60,10,10),   "ui_bg": (30,10,10),   "ui_text": (255,200,200), "button": (180,30,30),   "button_hover": (200,40,40),   "hud": (255,220,220)},
    {"id": "siyah_mavi",  "name": "SIYAH-MAVI",   "bg": (10,20,40),    "ui_bg": (20,35,70),   "ui_text": (180,220,255), "button": (30,80,150),   "button_hover": (40,100,180),  "hud": (180,220,255)},
    {"id": "mor_mavi",    "name": "MOR-MAVI",     "bg": (40,20,60),    "ui_bg": (60,30,90),   "ui_text": (220,200,255), "button": (120,60,180),  "button_hover": (140,80,200),  "hud": (220,200,255)},
    {"id": "pembe_sari",  "name": "PEMBE-SARI",   "bg": (255,210,230), "ui_bg": (255,230,160), "ui_text": (120,30,80),  "button": (255,150,200), "button_hover": (255,130,180), "hud": (120,30,80)},
    {"id": "yesil_gri",   "name": "YESIL-GRI",    "bg": (200,220,200), "ui_bg": (180,200,180), "ui_text": (30,60,30),   "button": (100,150,100), "button_hover": (80,130,80),   "hud": (30,60,30)},
    {"id": "turuncu_siyah","name":"TURUNCU-SIYAH","bg": (32,18,8),    "ui_bg": (58,32,14),    "ui_text": (255,200,120), "button": (220,110,30),  "button_hover": (240,130,40),  "hud": (255,220,160)},
    {"id": "kahve_krem",  "name": "KAHVE-KREM",   "bg": (242,228,210), "ui_bg": (255,242,220), "ui_text": (90,50,20),    "button": (180,130,90),  "button_hover": (200,150,110), "hud": (90,50,20)},
]
