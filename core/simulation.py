import pygame
import sys
from environment.fire import randomfirespot, update_fire_with_materials, update_temperature_with_materials
from environment.smoke import spread_smoke, draw_smoke
from utils.utilities import Color, state_value, visualize_2d, fire_constants, material_id, SimulationState
from environment.materials import MATERIALS

class Simulation:
    def __init__(self, win, grid, agent, rows, width, bg_image=None):
        self.win = win
        self.grid = grid
        self.agent = agent
        self.rows = rows
        # Get current window size for proper initialization
        win_width, win_height = win.get_size()
        self.width = win_width - 200  # Grid width = window width - panel width

        self.bg_image = bg_image
        
        # Store original dimensions
        self.original_width = width
        self.tools_width = 200  # Width for simulation panel
        
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
    
    def _handle_window_resize(self, event):
        """Handle window resize events"""
        if event.type == pygame.VIDEORESIZE:
            win_width, win_height = event.size
            
            # Update window width for grid area
            # Grid area takes all space except 200px for panel
            self.width = win_width - self.tools_width if win_width > 200 else win_width
            
            return True
        return False
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return SimulationState.SIM_QUIT.value

            elif event.type == pygame.VIDEORESIZE:
                self._handle_window_resize(event)
                continue  # Continue processing other events

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return SimulationState.SIM_QUIT.value
                
                elif event.key == pygame.K_p:
                    self.paused = not self.paused

                elif event.key == pygame.K_r:
                    self.reset()

                elif event.key == pygame.K_e:
                    return SimulationState.SIM_EDITOR.value

        return SimulationState.SIM_CONTINUE.value

    def reset(self):
        self.grid.clear_simulation_visuals()
        self.frame_count = 0
        self.fire_set = False
        self.start_time = pygame.time.get_ticks()
        self.grid.temperature = [[fire_constants.AMBIENT_TEMP.value for _ in range(self.rows)] for _ in range(self.rows)]  # Default temp 20C
        self.grid.fuel = [[1.0 for _ in range(self.rows)] for _ in range(self.rows)]

        self.grid.smoke = [[0.0 for _ in range(self.rows)] for _ in range(self.rows)]

        if self.agent:
            self.agent.reset()

        if self.grid.start and bool(self.grid.exits):
            self.agent.path = self.agent.best_path()

    def update(self, dt):
        """Time-based update with delta time"""
        if self.paused:
            return

        self.frame_count += 1
        
        # Generate fire once
        if not self.fire_set:
            if self.grid.fire_sources:
                for r, c in self.grid.fire_sources:
                    self.grid.state[r][c] = state_value.FIRE.value
                self.fire_set = True
            else:
                self.fire_set = randomfirespot(self.grid, self.rows)

        update_temperature_with_materials(self.grid, dt)
        update_fire_with_materials(self.grid, dt)

        for r in range(self.rows):
            for c in range(self.rows):
                if self.grid.state[r][c] == state_value.FIRE.value and self.grid.fuel[r][c] <= 0:
                    self.grid.state[r][c] = state_value.EMPTY.value
                    if not self.grid.grid[r][c].is_barrier() and not self.grid.grid[r][c].is_start() and not self.grid.grid[r][c].is_end():
                        mat_id = material_id(self.grid.material[r][c])
                        self.grid.grid[r][c].color = MATERIALS[mat_id]["color"]

        # Smoke spread
        old_smoke_total = sum(sum(row) for row in self.grid.smoke)
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
        
        # Update metrics
        self.update_metrics()

    # ---------------- DRAW ----------------
    def draw(self):
        # Get current window size
        win_width, win_height = self.win.get_size()
        
        # Clear the entire window
        self.win.fill(Color.WHITE.value)

        # Calculate grid dimensions (fixed square based on original grid)
        grid_width = min(win_width - 200, self.original_width)
        grid_width = max(grid_width, 100)  # Minimum width
        
        # Grid should be square (rows x rows)
        grid_height = grid_width  # Force square aspect ratio
        cell_size = grid_width // self.rows
        
        # Center the grid in window
        grid_x = 0  # Align to left
        grid_y = (win_height - grid_height) // 2 if win_height > grid_height else 0
        
        # Create a temporary surface for the grid area with exact grid dimensions
        grid_surface = pygame.Surface((grid_width, grid_height))
        grid_surface.fill(Color.WHITE.value)
        
        # IMPORTANT: Update grid cell size for proper drawing
        self.grid.cell_size = cell_size
        
        # Update spot positions in the grid
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid.grid[r][c]
                spot.x = c * cell_size
                spot.y = r * cell_size
                spot.cell_size = cell_size
        
        # Update agent position if it exists
        if self.agent and self.agent.spot:
            self.agent.spot.cell_size = cell_size
            # Update agent's reference to cell size
            if hasattr(self.agent, 'cell_size'):
                self.agent.cell_size = cell_size
        
        # Drawing path - draw on grid surface
        if self.agent and self.agent.path and self.agent.path_show:
            for p in self.agent.path:
                if p != self.agent.spot and not p.is_start() and not p.is_end():
                    p.color = Color.PURPLE.value
                    # Ensure path spot has correct size
                    p.cell_size = cell_size
                    p.draw(grid_surface)
        
        # Draw Grid Lines + spots - on grid surface
        self.grid.draw(grid_surface, bg_image=self.bg_image)
        
        # Draw smoke using the imported function
        draw_smoke(self.grid, grid_surface, self.rows, cell_size)
        
        # Agent LAST (top layer) - on grid surface
        if self.agent and self.agent.spot:
            # Ensure agent's spot has correct size
            self.agent.spot.cell_size = cell_size
            self.agent.draw(grid_surface)
        
        # Blit the grid surface onto the main window at centered position
        self.win.blit(grid_surface, (grid_x, grid_y))
        
        # Draw the white separator bar between grid and panel
        panel_x = grid_width
        pygame.draw.rect(self.win, Color.WHITE.value, (panel_x, 0, 2, win_height))

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
            
            # Handle events
            action = self.handle_events()
            if action == SimulationState.SIM_EDITOR.value:
                self.running = False
                return SimulationState.SIM_EDITOR.value

            if action == SimulationState.SIM_QUIT.value:
                self.running = False
                return SimulationState.SIM_QUIT.value

            self.update(dt)  
            self.draw()

        return SimulationState.SIM_QUIT.value

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
        panel_x = self.width  # Right side of grid area
        for text in metrics:
            if text:
                text_surface = self.font.render(text, True, (220, 220, 220))
                self.win.blit(text_surface, (panel_x + 15, y_offset))
            y_offset += 25

    def draw_sim_panel(self):
        # Get current window size
        win_width, win_height = self.win.get_size()
        
        # Fixed panel width
        panel_width = 200
        panel_x = win_width - panel_width
        
        # Calculate actual grid width used in draw()
        grid_width = min(win_width - panel_width, self.original_width)
        grid_width = max(grid_width, 100)
        
        # Draw panel background
        panel_rect = pygame.Rect(panel_x, 0, panel_width, win_height)
        pygame.draw.rect(self.win, (40, 40, 50), panel_rect)
        pygame.draw.rect(self.win, (60, 60, 70), panel_rect, width=2)

        # Draw title - center in panel
        title_font = pygame.font.SysFont(None, 24)
        title = title_font.render("SIMULATION", True, (255, 255, 255))
        self.win.blit(title, (panel_x + panel_width//2 - title.get_width()//2, 20))
        
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
                # **FIX: Use panel_x instead of self.width**
                self.win.blit(text_surface, (panel_x + 15, y_offset))
            y_offset += 25
        
        # Draw agent status
        if self.agent:
            status_y = win_height - 100
            status = "ALIVE" if self.agent.alive else "DEAD"
            status_color = (0, 255, 0) if self.agent.alive else (255, 0, 0)
            status_surface = self.font.render(f"Agent: {status}", True, status_color)
            self.win.blit(status_surface, (panel_x + 15, status_y))
            
            # Draw health bar
            health_width = int((panel_width - 20) * (self.agent.health / 100))
            pygame.draw.rect(self.win, (50, 50, 50), 
                        (panel_x + 10, status_y + 25, panel_width - 20, 20))
            pygame.draw.rect(self.win, status_color, 
                        (panel_x + 10, status_y + 25, health_width, 20))
            
            # Draw health text
            health_text = self.font.render(f"{self.agent.health:.0f}%", True, (255, 255, 255))
            self.win.blit(health_text, (panel_x + panel_width//2 - health_text.get_width()//2, status_y + 27))
    

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
