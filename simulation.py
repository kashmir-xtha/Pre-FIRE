import pygame
import sys
from fire import randomfirespot, update_fire_with_materials, update_temperature_with_materials
from smoke import spread_smoke, draw_smoke
import tools
from utilities import Color, state_value, visualize_2d, fire_constants, Dimensions, material_id
from materials import MATERIALS
from agent import a_star

class Simulation:
    def __init__(self, win, grid, agent, rows, width, bg_image=None):
        self.win = win
        self.grid = grid
        self.agent = agent
        self.rows = rows
        self.width = width
        self.bg_image = bg_image

        # Create simulation tools panel (for metrics/controls)
        self.sim_panel = tools.ToolsPanel(width, 0, Dimensions.TOOLS_WIDTH.value, width)
        # Change title of sim panel
        self.sim_panel.rect = pygame.Rect(width, 0, Dimensions.TOOLS_WIDTH.value, width)

        self.clock = pygame.time.Clock()
        self.running = True
        self.paused = False
        self.frame_count = 0
        self.fire_set = False

        self.font = pygame.font.Font(None, 24)
        self.start_time = pygame.time.get_ticks()
        self.metrics = {
            'elapsed_time': 0,
            'agent_health': self.agent.health if self.agent else 0,
            'fire_cells': 0,
            'avg_smoke': 0,
            'avg_temp': 20,
            'path_length': 0
        }

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
        self.start_time = pygame.time.get_ticks()
        self.grid.temperature = [[fire_constants.AMBIENT_TEMP.value for _ in range(self.rows)] for _ in range(self.rows)]  # Default temp 20C
        self.grid.fuel = [
                            [
                                MATERIALS[material_id(self.grid.material[r][c])]["fuel"]
                                for c in range(self.rows)
                            ]
                            for r in range(self.rows)
                        ]

        self.grid.smoke = [[0.0 for _ in range(self.rows)] for _ in range(self.rows)]

        if self.agent:
            self.agent.reset()

        if self.grid.start and self.grid.end:
            self.agent.path = a_star(self.grid, self.grid.start, self.grid.end, self.rows)
            self.grid.clear_path_visualization()

    # ---------------- UPDATE ----------------
    # In simulation.py - modify update method
    def update(self, dt):
        """Time-based update with delta time"""
        if self.paused:
            return

        self.frame_count += 1
        
        # Generate fire once
        if not self.fire_set:
            self.fire_set = randomfirespot(self.grid, self.rows)

        update_temperature_with_materials(self.grid, dt)
        update_fire_with_materials(self.grid, dt)

        for r in range(self.rows):
            for c in range(self.rows):
                if self.grid.state[r][c] == state_value.FIRE.value and self.grid.fuel[r][c] <= 0:
                    self.grid.state[r][c] = state_value.EMPTY.value
                    self.grid.temperature[r][c] *= 0.5  # Cool down when fire goes out
                    # Update visual to material color
                    if not self.grid.grid[r][c].is_barrier() and not self.grid.grid[r][c].is_start() and not self.grid.grid[r][c].is_end():
                        mat_id = material_id(self.grid.material[r][c])
                        self.grid.grid[r][c].color = MATERIALS[mat_id]["color"]

        # Smoke spread
        self.grid.smoke = spread_smoke(
            self.grid.state,
            self.grid.smoke,
            self.rows,
            self.rows
        )

        # Apply fire visuals
        self.grid.apply_fire_to_spots()

        # Update agent with delta time
        if self.agent:
            self.agent.update(dt)

        #update metrics
        self.update_metrics()


    # ---------------- DRAW ----------------
    def draw(self):
        # Clear only the grid area
        grid_area = pygame.Rect(0, 0, self.width, self.width)
        pygame.draw.rect(self.win, Color.WHITE.value, grid_area)
        
        # Smoke FIRST (background effect)
        draw_smoke(self.grid, self.win, self.rows)
        
        # Grid + walls + path
        # Note: We need to modify the draw function to not draw outside grid area
        for row in self.grid.grid:
            for spot in row:
                spot.draw(self.win)
        
        # Draw grid lines
        gap = self.width // self.rows
        for i in range(self.rows):
            pygame.draw.line(self.win, Color.GREY.value, (0, i * gap), (self.width, i * gap))
            pygame.draw.line(self.win, Color.GREY.value, (i * gap, 0), (i * gap, self.width))
        
        # Agent LAST (top layer)
        if self.agent:
            self.agent.draw(self.win)
        
        # Draw simulation panel
        self.draw_sim_panel()
        
        pygame.display.update()

    # ---------------- MAIN LOOP ----------------
    def run(self):
        last_time = pygame.time.get_ticks()
        
        while self.running:
            current_time = pygame.time.get_ticks()
            dt = (current_time - last_time) / 1000.0  # Convert to seconds
            last_time = current_time
            
            self.clock.tick(120)
            # if not self.agent.alive:
            #     visualize_2d(self.grid.fuel)
            self.handle_events()
            self.update(dt)  # Pass delta time
            self.draw()
        
        pygame.quit()
        sys.exit()

    def update_metrics(self):
        # Time
        self.metrics['elapsed_time'] = (pygame.time.get_ticks() - self.start_time) / 1000
        
        # Agent
        if self.agent:
            self.metrics['agent_health'] = self.agent.health
            self.metrics['path_length'] = len(self.agent.path) if self.agent.path else 0
        
        # Count fire cells and average temperature
        fire_count = 0
        total_temp = 0
        cells = self.rows * self.rows
        
        for r in range(self.rows):
            for c in range(self.rows):
                if self.grid.state[r][c] == state_value.FIRE.value:
                    fire_count += 1
                total_temp += self.grid.temperature[r][c]
        
        self.metrics['fire_cells'] = fire_count
        self.metrics['avg_temp'] = total_temp / cells
    
    def draw_metrics(self):
        """Display metrics on screen"""
        metrics = [
            f"Time: {self.metrics['elapsed_time']:.1f}s",
            f"Health: {self.metrics['agent_health']:.0f}%",
            f"Fire Cells: {self.metrics['fire_cells']}",
            f"Avg Temp: {self.metrics['avg_temp']:.1f}°C",
            f"Path Length: {self.metrics['path_length']}"
        ]
        
        y_offset = 10
        for text in metrics:
            # Draw background for readability
            text_surface = self.font.render(text, True, (255, 255, 255))
            pygame.draw.rect(self.win, (0, 0, 0, 180), 
                           (10, y_offset - 2, text_surface.get_width() + 4, text_surface.get_height() + 4))
            self.win.blit(text_surface, (12, y_offset))
            y_offset += 25

    def draw_sim_panel(self):
        # Draw panel background
        panel_rect = pygame.Rect(self.width, 0, 200, self.width)
        pygame.draw.rect(self.win, (40, 40, 50), panel_rect)
        pygame.draw.rect(self.win, (60, 60, 70), panel_rect, width=2)
        
        # Draw title
        title_font = pygame.font.SysFont(None, 24)
        title = title_font.render("SIMULATION", True, (255, 255, 255))
        self.win.blit(title, (self.width + 100 - title.get_width() // 2, 20))
        
        # Draw metrics
        y_offset = 60
        metrics = [
            f"Time: {self.metrics['elapsed_time']:.1f}s",
            f"Health: {self.metrics['agent_health']:.0f}",
            f"Fire Cells: {self.metrics['fire_cells']}",
            f"Avg Temp: {self.metrics['avg_temp']:.1f}°C",
            f"Path Length: {self.metrics['path_length']}",
            "",
            "Controls:",
            "P: Pause/Resume",
            "R: Reset",
            "ESC: Quit"
        ]
        
        for text in metrics:
            if text:
                text_surface = self.font.render(text, True, (220, 220, 220))
                self.win.blit(text_surface, (self.width + 15, y_offset))
            y_offset += 25
        
        # Draw agent status
        if self.agent:
            status_y = self.width - 100
            status = "ALIVE" if self.agent.alive else "DEAD"
            status_color = (0, 255, 0) if self.agent.alive else (255, 0, 0)
            status_surface = self.font.render(f"Agent: {status}", True, status_color)
            self.win.blit(status_surface, (self.width + 15, status_y))
            
            # Draw health bar
            health_width = int(180 * (self.agent.health / 100))
            pygame.draw.rect(self.win, (50, 50, 50), 
                           (self.width + 10, status_y + 25, 180, 20))
            pygame.draw.rect(self.win, status_color, 
                           (self.width + 10, status_y + 25, health_width, 20))
            
            # Draw health text
            health_text = self.font.render(f"{self.agent.health:.0f}%", True, (255, 255, 255))
            self.win.blit(health_text, (self.width + 100 - health_text.get_width() // 2, status_y + 27))

def draw_temperature(grid, win, rows):
    """Draw temperature as color overlay"""
    cell = grid.cell_size
    
    for r in range(rows):
        for c in range(rows):
            temp = grid.temperature[r][c]
            if temp > 30:  # Only draw above ambient
                # Color gradient from yellow to red
                intensity = min(1.0, (temp - 30) / 300)  # Scale to 0-1
                alpha = int(100 * intensity)
                
                surface = pygame.Surface((cell, cell), pygame.SRCALPHA)
                color = (255, int(255 * (1 - intensity)), 0, alpha)
                surface.fill(color)
                win.blit(surface, (c * cell, r * cell))
