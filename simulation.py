import pygame
import sys
from fire import randomfirespot, update_fire
from smoke import spread_smoke, draw_smoke
from buildinglayout import draw
from utilities import Color
from agent import a_star

class Simulation:
    def __init__(self, win, grid, agent, rows, width, bg_image=None):
        self.win = win
        self.grid = grid
        self.agent = agent
        self.rows = rows
        self.width = width
        self.bg_image = bg_image

        self.clock = pygame.time.Clock()
        self.running = True
        self.paused = False
        self.frame_count = 0

        self.fire_set = False

    # ---------------- EVENTS ----------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

                elif event.key == pygame.K_p:
                    self.paused = not self.paused

                elif event.key == pygame.K_r:
                    self.reset()

    # ---------------- RESET ----------------
    def reset(self):
        self.grid.clear_simulation_visuals()
        self.frame_count = 0
        self.fire_set = False

        if self.agent:
            self.agent.reset()
        if self.grid.start and self.grid.end:
            self.agent.path = a_star(self.grid.grid, self.grid.start, self.grid.end, self.rows)
            self.grid.clear_path_visualization()  # Clear any previous path visualization
                

    # ---------------- UPDATE ----------------
    def update(self):
        if self.paused:
            return

        self.frame_count += 1

        # Generate fire once
        if not self.fire_set:
            self.fire_set = randomfirespot(self.grid, self.rows)

        # Fire spread
        if self.frame_count % 5 == 0:
            self.grid.state = update_fire(self.grid.state, fire_prob=0.3)

        # Smoke spread
        self.grid.smoke = spread_smoke(
            self.grid.state,
            self.grid.smoke,
            self.rows,
            self.rows
        )

        # Apply fire visuals
        self.grid.apply_fire_to_spots()

        # Update agent
        if self.agent.path and self.frame_count % 10 == 0 and self.agent.spot != self.grid.end:
            self.agent.update()

    # ---------------- DRAW ----------------
    def draw(self):
        self.win.fill(Color.WHITE.value)

        # Smoke FIRST (background effect)
        draw_smoke(self.grid, self.win, self.rows)

        # Grid + walls + path
        draw(self.win, self.grid.grid, self.rows, self.width)

        # Agent LAST (top layer)
        if self.agent:
            self.agent.draw(self.win)

        pygame.display.update()

    # ---------------- MAIN LOOP ----------------
    def run(self):
        while self.running:
            self.clock.tick(120)

            self.handle_events()
            self.update()
            self.draw()

        pygame.quit()
        sys.exit()
