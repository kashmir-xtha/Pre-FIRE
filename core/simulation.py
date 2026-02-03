import pygame
import pygame_gui
from environment.fire import randomfirespot, update_fire_with_materials, update_temperature_with_materials
from environment.smoke import spread_smoke, draw_smoke
from utils.utilities import Color, Dimensions, state_value, SimulationState, rTemp
from ui.slider import create_control_panel
from utils.time_manager import TimeManager

class Simulation:
    def __init__(self, win, grid, agent, rows, width, bg_image=None):
        self.win = win
        self.grid = grid
        self.agent = agent
        self.rows = rows
        self.orignal_width = width
        self.tools_width = 200  # Fixed panel width
        self.width = self.win.get_size()[0] - self.tools_width  # Initial grid width (window width - panel width)
        self.bg_image = bg_image

        self.time_manager = TimeManager(fps=120, step_size=1)  # Keep your 120 FPS

        self.running = True
       
        self.fire_set = False  
        self.restart_timer = False

        self.font = pygame.font.Font(None, 24)
        
        self.metrics = {
            'elapsed_time': 0,
            'agent_health': self.agent.health if self.agent else 0,
            'fire_cells': 0,
            'avg_smoke': 0,
            'avg_temp': 20,
            'path_length': 0
        }

        self.manager = pygame_gui.UIManager(self.win.get_size())
        self.temp = rTemp()
        self.create_sliders()

    def create_sliders(self):
        start_y = self.win.get_size()[1] - 250

        self.slider_group = create_control_panel(
            manager=self.manager,
            x=self.width + 10,
            y=start_y,
            temp_obj=self.temp
        )

    def _handle_window_resize(self, event):
        """Handle window resize events"""
        if event.type == pygame.VIDEORESIZE:
            win_width, win_height = event.size
            # Update window width for grid area
            # Grid area takes all space except 200px for panel
            self.width = win_width - self.tools_width if win_width > 200 else win_width

            # Update GUI manager resolution (don't recreate it!)
            self.manager.set_window_resolution(event.size)
            
            # Recreate sliders at new positions
            # First, kill existing sliders
            if hasattr(self, "slider_group"):
                self.slider_group.clear()
            
            # Recreate them
            self.create_sliders()
            return True
        return False

    def handle_events(self):
        for event in pygame.event.get():
            self.manager.process_events(event)
            if hasattr(self, "slider_group"):
                self.slider_group.handle_event(event)
            
            if event.type == pygame.QUIT:
                return SimulationState.SIM_QUIT.value

            elif event.type == pygame.VIDEORESIZE:
                self._handle_window_resize(event)
                continue

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return SimulationState.SIM_QUIT.value
                
                elif event.key == pygame.K_p or event.key == pygame.K_SPACE:
                    # Replace old pause logic
                    self.time_manager.toggle_pause()
                    print(f"Simulation {'paused' if self.time_manager.is_paused() else 'resumed'}")

                elif event.key == pygame.K_s:
                    # Toggle step-by-step mode
                    if self.time_manager.toggle_step_mode():
                        print("Step-by-step mode ON (press 'n' for next step)")
                    else:
                        print("Step-by-step mode OFF")

                elif event.key == pygame.K_n:
                    # Next step in step mode
                    if self.time_manager.request_next_step():
                        print("Advancing one step")

                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    # Increase speed
                    new_speed = self.time_manager.set_speed(self.time_manager.get_step_size() + 1)
                    print(f"Speed: {new_speed}x")

                elif event.key == pygame.K_MINUS:
                    # Decrease speed
                    new_speed = self.time_manager.set_speed(self.time_manager.get_step_size() - 1)
                    print(f"Speed: {new_speed}x")

                elif event.key == pygame.K_r:
                    self.reset()

                elif event.key == pygame.K_e:
                    return SimulationState.SIM_EDITOR.value

        return SimulationState.SIM_CONTINUE.value

    def reset(self):
        self.grid.clear_simulation_visuals()
        self.fire_set = False
        
        # Reset the time manager timer
        self.time_manager.reset_timer()
        
        # Reset all spots using proper methods
        for row in self.grid.grid:
            for spot in row:
                disc = spot.to_dict()
                spot.reset()
                if disc.get('state') == state_value.WALL.value:
                    spot.make_barrier()
                elif disc.get('state') == state_value.START.value:
                    spot.make_start()
                elif disc.get('state') == state_value.END.value:
                    spot.make_end()
                elif disc.get('is_fire_source'):
                    spot.set_as_fire_source(disc.get('temperature') if disc.get('temperature') else 1200.0)
                else:
                    spot.set_material(disc.get('material'))

        if self.agent:
            self.agent.reset()

        if self.grid.start and bool(self.grid.exits):
            self.agent.path = self.agent.best_path()

    def update(self, dt):
        """Time-based update with delta time"""

        update_count = self.time_manager.get_update_count()
        scaled_dt = self.time_manager.get_delta_time() / update_count
        
        for _ in range(update_count):
            update_dt = self.time_manager.get_delta_time()
            if self.time_manager.step_size > 1:
                self.time_manager.total_time += update_dt
            # Pass scaled dt for physics consistency
            update_dt = scaled_dt
		
            update_temperature_with_materials(self.grid, update_dt)
            update_fire_with_materials(self.grid, update_dt)

            # Generate fire once
            if not self.fire_set:
                if self.grid.fire_sources:
                    for r, c in self.grid.fire_sources:
                        self.grid.grid[r][c].set_as_fire_source()
                    self.fire_set = True
                else:
                    randomfirespot(self.grid, self.rows)
                    
            for r in range(self.rows):
                for c in range(self.rows):
                    if self.grid.grid[r][c].is_fire() and self.grid.grid[r][c].fuel <= 0:
                        self.grid.grid[r][c].extinguish_fire()
                        
            # Smoke spread
            spread_smoke(self.grid.grid)

            # Update agent with delta time
            if self.agent:
                self.agent.update(update_dt)
            
            # Update metrics
            self.update_metrics()

    # DRAW FUNCTION
    def draw(self):
        # Clear only the grid area
        # grid_area = pygame.Rect(0, 0, self.width, self.width)
        # pygame.draw.rect(self.win, Color.WHITE.value, grid_area)
        
        # Get current window size
        win_width, win_height = self.win.get_size()
        
        # Clear the entire window
        self.win.fill(Color.WHITE.value)

        # Calculate grid dimensions (fixed square based on original grid)
        grid_width = self.width
        grid_height = min(grid_width, win_height)
        cell_size = grid_height // self.rows
        grid_pixel_width = cell_size * self.rows

        # Center the grid in window
        grid_x = 0  # Align to left
        grid_y = (win_height - grid_height) // 2 if win_height > grid_height else 0
        
        # Create a temporary surface for the grid area with exact grid dimensions
        grid_surface = pygame.Surface((grid_pixel_width, grid_height))
        grid_surface.fill(Color.WHITE.value)
        
        # IMPORTANT: Update grid cell size for proper drawing
        self.grid.cell_size = cell_size
        
        # Update spot positions in the grid
        self.grid.update_geometry(cell_size)

        # Update agent position if it exists
        if self.agent and self.agent.spot:
            self.agent.spot.width = cell_size
    
        # Drawing path
        if self.agent.path and self.agent.path_show:
            for p in self.agent.path:
                if p != self.agent.spot and not p.is_start() and not p.is_end():
                    rect = pygame.Rect(p.x, p.y, p.width, p.width)
                    pygame.draw.rect(
                        grid_surface,
                        Color.PURPLE.value,
                        rect
                    )
        
        # Draw Grid Lines + spots
        self.grid.draw(grid_surface, bg_image=self.bg_image)
        
        # Smoke FIRST (background effect)
        draw_smoke(self.grid.grid, grid_surface)
        # Agent LAST (top layer)
        if self.agent:
            self.agent.draw(grid_surface)
        
        # Blit the grid surface onto the main window at centered position
        self.win.blit(grid_surface, (grid_x, grid_y))

        # Draw the white separator bar between grid and panel
        panel_x = self.width
        pygame.draw.rect(self.win, Color.WHITE.value, (panel_x, 0, 2, win_height))

        # Draw simulation panel
        self.draw_sim_panel()
        self.manager.draw_ui(self.win)

        pygame.display.update()

    # ---------------- MAIN LOOP ----------------
    def run(self):
        while self.running:
            # Handle events first so step-by-step requests ("n") are registered
            action = self.handle_events()
            if action == SimulationState.SIM_EDITOR.value:
                self.running = False
                return SimulationState.SIM_EDITOR.value

            if action == SimulationState.SIM_QUIT.value:
                self.running = False
                return SimulationState.SIM_QUIT.value

            # Now update time manager (which will consume next-step requests)
            should_update = self.time_manager.update()

            # Update GUI manager with proper dt (after time update)
            self.manager.update(self.time_manager.get_delta_time())

            # Update simulation if time_manager says so
            if should_update:
                self.update(self.time_manager.get_delta_time())

            self.draw()

        return SimulationState.SIM_QUIT.value

    def update_metrics(self):
        # Use time_manager for elapsed time
        self.metrics['elapsed_time'] = self.time_manager.get_total_time()
        
        # Agent
        if self.agent:
            self.metrics['agent_health'] = self.agent.health
            self.metrics['path_length'] = len(self.agent.path) if self.agent.path else 0
        
        # Count fire cells and average temperature
        fire_count = 0
        total_temp = 0
        total_smoke = 0
        cells = self.rows * self.rows
        
        for r in range(self.rows):
            for c in range(self.rows):
                if self.grid.grid[r][c].is_fire():
                    fire_count += 1
                total_temp += self.grid.grid[r][c].temperature
                total_smoke += self.grid.grid[r][c].smoke
        
        self.metrics['avg_smoke'] = total_smoke/cells
        self.metrics['fire_cells'] = fire_count
        self.metrics['avg_temp'] = total_temp / cells
    
    def draw_sim_panel(self):
        # Draw panel background
        clamped_height = max(self.win.get_size()[1], self.width)
        clamped_height = min(clamped_height, Dimensions.WIDTH.value+20)  # Max height for panel
        panel_rect = pygame.Rect(self.width, 0, self.tools_width, clamped_height)
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
            f"Step: {self.time_manager.get_simulation_step()}",
            f"FPS: {self.time_manager.get_fps():.1f}",
            f"Speed: {self.time_manager.get_step_size()}x",
            f"Health: {self.metrics['agent_health']:.0f}",
            f"Fire Cells: {self.metrics['fire_cells']}",
            f"Avg Smoke: {self.metrics['avg_smoke']:.3f}",
            f"Avg Temp: {self.metrics['avg_temp']:.1f}°C",
            f"Path Length: {self.metrics['path_length']}",
            "Controls:",
            "P: Pause/Resume",
            "S: Step Mode",
            "N: Next Step",
            "+/-: Speed",
            "R: Reset",
            "E: Editor Mode",
            "ESC: Quit"
        ]
        
        # Add status indicator
        if self.time_manager.is_paused():
            status = "PAUSED"
            status_color = (255, 200, 0)  # Yellow
        elif self.time_manager.is_step_mode():
            status = "STEP MODE"
            status_color = (0, 200, 255)  # Cyan
        else:
            status = "RUNNING"
            status_color = (0, 255, 0)  # Green
        
        status_surface = self.font.render(f"Status: {status}", True, status_color)
        self.win.blit(status_surface, (self.width + 15, y_offset))
        y_offset += 25
        
        for text in metrics:
            if text:
                text_surface = self.font.render(text, True, (220, 220, 220))
                self.win.blit(text_surface, (self.width + 15, y_offset))
            y_offset += 25

        
        # Draw agent status
        if self.agent:
            status_y = clamped_height - 50
            status = "ALIVE" if self.agent.alive else "DEAD"
            status_color = (0, 255, 0) if self.agent.alive else (255, 0, 0)
            status_surface = self.font.render(f"Agent: {status}", True, status_color)
            self.win.blit(status_surface, (self.width + 15, clamped_height - 80))
            
            # Draw health bar
            health_width = int(180 * (self.agent.health / 100))
            pygame.draw.rect(self.win, (50, 50, 50), 
                           (self.width + 10, status_y + 25, 180, 20))
            pygame.draw.rect(self.win, status_color, 
                           (self.width + 10, status_y, health_width, 20))
            
            # Draw health text
            health_text = self.font.render(f"{self.agent.health:.0f}%", True, (255, 255, 255))
            self.win.blit(health_text, (self.width + 100 - health_text.get_width() // 2, status_y + 2))

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
