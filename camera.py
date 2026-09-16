import config

class Camera:
    def __init__(self):
        self.y = 0.0  # world Y of top of screen
        self.target_y = 0.0

    def reset(self, player_y):
        self.y = player_y - config.SCREEN_HEIGHT * config.CAMERA_FOLLOW_Y_RATIO
        if self.y < 0:
            self.y = 0
        self.target_y = self.y

    def update(self, dt, player_y, player_alive=True):
        import math
        # --- WORLD/PHYSICS/RENDER ayrımı: kamera sadece ekran konumunu etkiler, fizikle karışmaz ---
        desired = player_y - config.SCREEN_HEIGHT * config.CAMERA_FOLLOW_Y_RATIO
        self.target_y = desired
        diff = self.target_y - self.y
        # 5.8M gibi büyük ışınlanmada anında snap — yoksa oyuncu kaybolur
        if abs(diff) > 2000:
            self.y = self.target_y
            diff = 0
        # Frame-rate bağımsız lerp: 1 - exp(-smooth*dt) → 30/60/144 FPS'te aynı his
        t = 1.0 - math.exp(-config.CAMERA_SMOOTH * dt)
        t = max(0.0, min(1.0, t))
        self.y += diff * t
        # Ekran içi güvenlik clamp'i — oyuncu kadrajdan taşmasın
        player_screen_y = player_y - self.y
        if player_screen_y > config.SCREEN_HEIGHT * 0.75:
            self.y += (player_screen_y - config.SCREEN_HEIGHT*0.6) * min(8*dt, 0.5)
        elif player_screen_y < 38:
            # üstte çok yakınsa yumuşak geri çek
            self.y -= (38 - player_screen_y) * min(8*dt, 0.5)

        if self.y < 0:
            self.y = 0
        # Sub-pixel jitter sönümleme: 0.015px altında diff'i yuvarla
        if abs(self.y - self.target_y) < 0.015:
            self.y = self.target_y

    def world_to_screen(self, wy):
        return wy - self.y

    def screen_to_world(self, sy):
        return sy + self.y
