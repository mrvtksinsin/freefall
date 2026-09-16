import pygame
import sys

# Renkler
BLACK = (10, 10, 10)
WHITE = (255, 255, 255)
GREEN = (50, 205, 50)
RED = (220, 20, 60)
BLUE = (30, 144, 255)
YELLOW = (255, 215, 0)
PURPLE = (138, 43, 226)

# Pencere Ayarları
WIDTH, HEIGHT = 800, 600
GRID_SIZE = 20

class Lemming:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.direction = 1  # 1: Sağ, -1: Sol
        self.role = "Walker" # Roller: Walker, Blocker, Digger, Builder
        self.is_alive = True
        self.saved = False
        self.build_steps = 0

    def update(self, grid):
        if not self.is_alive or self.saved:
            return

        # 1. Yerçekimi Kontrolü (Düşme)
        grid_x = int(self.x // GRID_SIZE)
        grid_y = int((self.y + 1) // GRID_SIZE)

        # Harita dışı kontrolü
        if grid_y >= len(grid) or grid_x < 0 or grid_x >= len(grid[0]):
            self.is_alive = False
            return

        # Altı boşsa düşer
        if grid[grid_y][grid_x] == 0:
            self.y += 2
            # Eğer düşüyorsa roller askıya alınır
            if self.role in ["Digger", "Builder"]:
                self.role = "Walker"
            return

        # 2. Rol Davranışları
        if self.role == "Blocker":
            return

        elif self.role == "Digger":
            if grid_y < len(grid) and grid[grid_y][grid_x] == 1:
                grid[grid_y][grid_x] = 0
                self.y += GRID_SIZE
                self.role = "Walker"
            return

        elif self.role == "Builder":
            next_grid_x = int((self.x + self.direction * GRID_SIZE) // GRID_SIZE)
            current_grid_y = int(self.y // GRID_SIZE)
            
            if 0 <= next_grid_x < len(grid[0]) and current_grid_y > 0:
                if grid[current_grid_y][next_grid_x] == 0:
                    grid[current_grid_y][next_grid_x] = 2 # 2: Köprü Bloğu
                    self.x += self.direction * GRID_SIZE
                    self.y -= GRID_SIZE
                    self.build_steps += 1
                    if self.build_steps >= 5:
                        self.role = "Walker"
                        self.build_steps = 0
                else:
                    self.role = "Walker"
            return

        elif self.role == "Walker":
            self.x += self.direction * 1.5

            front_x = int((self.x + self.direction * 5) // GRID_SIZE)
            front_y = int(self.y // GRID_SIZE)

            if 0 <= front_x < len(grid[0]) and 0 <= front_y < len(grid):
                if grid[front_y][front_x] == 1:
                    self.direction *= -1
            else:
                self.direction *= -1

    def draw(self, screen):
        if not self.is_alive or self.saved:
            return
        
        color = GREEN
        if self.role == "Blocker": color = RED
        elif self.role == "Digger": color = PURPLE
        elif self.role == "Builder": color = BLUE

        pygame.draw.rect(screen, color, (self.x - 6, self.y - 12, 12, 12))

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Python Lemmings Prototip")
        self.clock = pygame.time.Clock()
        
        self.rows = HEIGHT // GRID_SIZE
        self.cols = WIDTH // GRID_SIZE
        self.grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        
        # Harita Tasarımı (Platformlar)
        for y in range(12, 15):
            for x in range(5, 25): self.grid[y][x] = 1
        for y in range(18, 21):
            for x in range(15, 35): self.grid[y][x] = 1
        for y in range(24, 27):
            for x in range(2, 18): self.grid[y][x] = 1
        
        self.spawn_pos = (150, 150)
        self.exit_rect = pygame.Rect(100, 440, 40, 40)
        
        self.lemmings = []
        self.spawn_timer = 0
        self.max_lemmings = 10
        self.saved_count = 0
        self.selected_tool = "Digger"

    def run(self):
        running = True
        while running:
            self.screen.fill(BLACK)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    
                    if my > HEIGHT - 60:
                        if 50 <= mx <= 150: self.selected_tool = "Digger"
                        elif 170 <= mx <= 270: self.selected_tool = "Builder"
                        elif 290 <= mx <= 390: self.selected_tool = "Blocker"
                    else:
                        for lem in self.lemmings:
                            if abs(lem.x - mx) < 15 and abs(lem.y - my) < 15:
                                lem.role = self.selected_tool
                                if lem.role == "Builder":
                                    lem.build_steps = 0
                                break

            self.spawn_timer += 1
            if self.spawn_timer > 90 and len(self.lemmings) < self.max_lemmings:
                self.spawn_timer = 0
                self.lemmings.append(Lemming(self.spawn_pos[0], self.spawn_pos[1]))

            for y in range(self.rows):
                for x in range(self.cols):
                    if self.grid[y][x] == 1:
                        pygame.draw.rect(self.screen, YELLOW, (x*GRID_SIZE, y*GRID_SIZE, GRID_SIZE-1, GRID_SIZE-1))
                    elif self.grid[y][x] == 2:
                        pygame.draw.rect(self.screen, BLUE, (x*GRID_SIZE, y*GRID_SIZE, GRID_SIZE-1, GRID_SIZE-1))

            pygame.draw.circle(self.screen, GREEN, self.spawn_pos, 10)
            pygame.draw.rect(self.screen, WHITE, self.exit_rect, 3)
            
            for lem in self.lemmings:
                if lem.role == "Walker":
                    for other in self.lemmings:
                        if other.role == "Blocker" and other.is_alive:
                            if abs(lem.y - other.y) < 10 and abs((lem.x + lem.direction*5) - other.x) < 12:
                                lem.direction *= -1

                lem.update(self.grid)
                lem.draw(self.screen)
                
                if self.exit_rect.collidepoint(lem.x, lem.y) and not lem.saved and lem.is_alive:
                    lem.saved = True
                    self.saved_count += 1

            pygame.draw.rect(self.screen, (30, 30, 30), (0, HEIGHT - 60, WIDTH, 60))
            
            tools = [("DIGGER (Mor)", "Digger", 50), ("BUILDER (Mavi)", "Builder", 170), ("BLOCKER (Kırmızı)", "Blocker", 290)]
            font = pygame.font.Font(None, 20)
            
            for text, tool_type, x_pos in tools:
                btn_color = (80, 80, 80) if self.selected_tool != tool_type else (100, 149, 237)
                pygame.draw.rect(self.screen, btn_color, (x_pos, HEIGHT - 50, 110, 40))
                txt_surf = font.render(text, True, WHITE)
                self.screen.blit(txt_surf, (x_pos + 5, HEIGHT - 38))

            status_font = pygame.font.Font(None, 26)
            status_txt = status_font.render(f"Kurtarılan: {self.saved_count} / {self.max_lemmings}", True, WHITE)
            self.screen.blit(status_txt, (550, HEIGHT - 40))

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    Game().run()
