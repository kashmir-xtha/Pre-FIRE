import logging
from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np
import pygame
import pygame_gui
from environment.fire import randomfirespot, update_fire_with_materials, update_temperature_with_materials, do_temperature_update
from environment.smoke import spread_smoke, draw_smoke
from utils.utilities import Color, Dimensions, state_value, SimulationState, rTemp, load_layout, get_dpi_scale
from ui.slider import create_control_panel
from utils.time_manager import TimeManager

if TYPE_CHECKING:
    from core.agent import Agent
    from core.grid import Grid

logger = logging.getLogger(__name__)

# Global constants for colors - accessed once at import time
WHITE = Color.WHITE.value
CYAN = Color.CYAN.value

SIM_QUIT = SimulationState.SIM_QUIT.value
SIM_EDITOR = SimulationState.SIM_EDITOR.value
SIM_CONTINUE = SimulationState.SIM_CONTINUE.value

WALL = state_value.WALL.value
EMPTY = state_value.EMPTY.value
START = state_value.START.value
END = state_value.END.value

class Simulation:
    def __init__(
        self,
        win: pygame.Surface,
        grid: "Grid",
        agents: Optional["Agent"],
        rows: int,
        width: int,
        bg_image: Optional[pygame.Surface] = None,
    ) -> None:
        self.win = win
        self.grid = grid
        self.agents = agents
        self.rows = rows
        self.orignal_width = width
        # when the display scale changes we keep track of a factor used to convert our hard‑coded dimensions into physically‑sized pixels
        from utils.utilities import get_dpi_scale
        self.scale = get_dpi_scale(pygame.display.get_wm_info()['window'])

        self.tools_width = int(200 * self.scale)  # scaled panel width
        self.width = self.win.get_size()[0] - self.tools_width  # initial grid width
        self.bg_image = bg_image

        # snapshot layout right away so RESET has something to restore from;
        # do this before any updates or fire is set
        self.grid.backup_layout()
        # remember layout_filename so later resets can reload from the CSV file
        self.layout_file = getattr(self.grid, "layout_filename", None)

        self.time_manager = TimeManager(fps=120, step_size=1)  # Keep your 120 FPS

        self.running = True
       
        self.fire_set = False  
        self.restart_timer = False

        # choose a font size that scales with DPI so text remains readable
        self.font = pygame.font.Font(None, int(24 * self.scale))
        self.history = {
            "time": [],
            "fire_cells": [],
            "avg_temp": [],
            "avg_smoke": [],
            "agent_health": [],
            "path_length": []
        }
        self.metrics = {
            'elapsed_time': 0,
            'agent_health': self.agents[0].health if self.agents else 0,
            'fire_cells': 0,
            'avg_smoke': 0,
            'avg_temp': 20,
            'path_length': 0
        }

        self.manager = pygame_gui.UIManager(self.win.get_size())
        self.temp = rTemp()
        self.create_sliders()

    def create_sliders(self) -> None:
        # place slider panel just above the agent health bar... to hold a dropdown + slider + labels plus a small gap
        win_width, win_height = self.win.get_size()
        health_top = win_height - int(60 * self.scale)
        # estimated height of the control panel contents (dropdown + slider, including padding)
        
        panel_h = int(120 * self.scale) +50 #to displace the slider from health bars
        margin = int(10 * self.scale)
        start_y = health_top - panel_h - margin
        # ensure sliders never float over the metrics area
        if start_y < 60:
            start_y = 60

        self.slider_group = create_control_panel(
            manager=self.manager,
            x=self.width + int(10 * self.scale),
            y=start_y,
            temp_obj=self.temp,
            scale=self.scale,
        )

    def _handle_window_resize(self, event: pygame.event.Event) -> bool:
        """Handle window resize events"""
        if event.type == pygame.VIDEORESIZE:
            win_width, win_height = event.size

            # recompute scale: DPI may have changed when moving between monitors or when the user alters the display scaling
            self.scale = get_dpi_scale(pygame.display.get_wm_info()['window'])

            # Update window width for grid area (panel width also needs recalculation with the new scale factor).
            self.tools_width = int(200 * self.scale)
            self.width = win_width - self.tools_width if win_width > self.tools_width else win_width

            # Update GUI manager resolution (don't recreate it!)
            self.manager.set_window_resolution(event.size)
            
            # Recreate sliders at new positions (clearing first)
            if hasattr(self, "slider_group"):
                self.slider_group.clear()
            self.create_sliders()
            return True
        return False
    
    def _handle_grid_click(self, event: pygame.event.Event) -> None:
        """Handle mouse clicks in the grid area"""
        row, col = self.grid.get_clicked_pos(event.pos)
        
        if row is not None and col is not None and self.grid.in_bounds(row, col):
            spot = self.grid.get_spot(row, col)
            
            if event.button == 1:  # Left click - place
                print("Spot info: ", spot.to_dict())

    def handle_events(self) -> int:
        for event in pygame.event.get():
            self.manager.process_events(event)
            if hasattr(self, "slider_group"):
                self.slider_group.handle_event(event)
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_grid_click(event)
                
            if event.type == pygame.QUIT:
                return SIM_QUIT

            elif event.type == pygame.VIDEORESIZE:
                self._handle_window_resize(event)
                continue

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return SIM_QUIT
                
                elif event.key == pygame.K_p or event.key == pygame.K_SPACE:
                    # Replace old pause logic
                    self.time_manager.toggle_pause()
                    logger.info(
                        "Simulation %s",
                        "paused" if self.time_manager.is_paused() else "resumed",
                    )

                elif event.key == pygame.K_s:
                    # Toggle step-by-step mode
                    if self.time_manager.toggle_step_mode():
                        logger.info("Step-by-step mode ON (press 'n' for next step)")
                    else:
                        logger.info("Step-by-step mode OFF")

                elif event.key == pygame.K_n:
                    # Next step in step mode
                    if self.time_manager.request_next_step():
                        logger.info("Advancing one step")

                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    # Increase speed
                    new_speed = self.time_manager.set_speed(self.time_manager.get_step_size() + 1)
                    logger.info("Speed: %sx", new_speed)

                elif event.key == pygame.K_MINUS:
                    # Decrease speed
                    new_speed = self.time_manager.set_speed(self.time_manager.get_step_size() - 1)
                    logger.info("Speed: %sx", new_speed)

                elif event.key == pygame.K_r:
                    self.reset()

                elif event.key == pygame.K_e:
                    return SIM_EDITOR

        return SIM_CONTINUE

    def reset(self) -> None:
        print(self.grid.start[0].to_dict(), self.grid.start[1].to_dict(), self.grid.start[2].to_dict())
        self.grid.clear_simulation_visuals()
        self.fire_set = False
        
        # Reset the time manager timer
        self.time_manager.reset_timer()
        
        # Prefer reloading the CSV that we remembered when the simulation was created 
        if getattr(self, "layout_file", None):
            start, exits = load_layout(self.grid.grid, self.layout_file)
            self.grid.start = start
            if exits:
                self.grid.exits = exits
            # refresh our backup to match the file (so subsequent resets use it)
            self.grid.backup_layout()
        else:
            layout = self.grid.initial_layout
            for r, row in enumerate(self.grid.grid):
                for c, spot in enumerate(row):
                    if layout is not None:
                        disc = layout[r][c]
                    else:
                        disc = spot.to_dict()

                    spot.reset()
                    if disc.get('state') == WALL:
                        spot.make_barrier()
                    elif disc.get('state') == START:
                        spot.make_start()
                    elif disc.get('state') == END:
                        spot.make_end()
                    elif disc.get('is_fire_source'):
                        spot.set_as_fire_source(disc.get('temperature') if disc.get('temperature') else 1200.0)
                    else:
                        spot.set_material(disc.get('material'))

        # after restoring layout we need to clear any burned flags (spot.reset
        # already did this) and rebuild the material cache
        self.grid.mark_material_cache_dirty()
        self.grid.ensure_material_cache()
        # Sync numpy arrays so smoke/temp don't carry over into the next update
        self.grid.update_np_arrays()

        # 2. Reset every agent in the list
        for i, agent in enumerate(self.agents):
            agent.reset()
            if i < len(self.grid.start):
                agent.spot = self.grid.start[i] 
            else:
                # Fallback if there are more agents than start spots
                agent.spot = self.grid.start[0] if self.grid.start else None

            if agent.spot and bool(self.grid.exits):
                agent.path = agent.best_path()

    def update(self, dt: float) -> None:
        """Time-based update with delta time"""
        update_count = self.time_manager.get_update_count()
        
        for _ in range(update_count):
            update_dt = self.time_manager.get_delta_time()
            if self.time_manager.step_size > 1:
                self.time_manager.total_time += update_dt
            # Pass scaled dt for physics consistency
            #update_dt = scaled_dt
		
            #update_temperature_with_materials(self.grid, update_dt)
            do_temperature_update(self.grid, update_dt)
            update_fire_with_materials(self.grid, update_dt)
            
            # Generate fire once
            if not self.fire_set:
                if self.grid.fire_sources:
                    for r, c in self.grid.fire_sources:
                        self.grid.grid[r][c].set_as_fire_source()
                    self.fire_set = True
                else:
                    randomfirespot(self.grid, self.rows)
                        
            # Smoke spread
            spread_smoke(self.grid, update_dt)
            
            # Update numpy arrays for rendering after all state changes
            self.grid.update_np_arrays()  

            # Update all agent with delta time
            for agent in self.agents:
                agent.update(update_dt)
            
            # Update metrics
            self.update_metrics()

    # DRAW FUNCTION
    def draw(self) -> None:
        # Clear only the grid area
        # grid_area = pygame.Rect(0, 0, self.width, self.width)
        # pygame.draw.rect(self.win, Color.WHITE.value, grid_area)
        
        # Get current window size
        win_width, win_height = self.win.get_size()
        
        # Clear the entire window
        self.win.fill(WHITE)

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
        grid_surface.fill(WHITE)
        
        # IMPORTANT: Update grid cell size for proper drawing
        self.grid.cell_size = cell_size
        
        # Update spot positions in the grid
        self.grid.update_geometry(cell_size)

        # Update agent position if it exists
        for agent in self.agents:
            if agent.path and agent.path_show:
                for p in agent.path:
                    if p != agent.spot and not p.is_start() and not p.is_end():
                        rect = pygame.Rect(p.x, p.y, p.width, p.width)
                        pygame.draw.rect(grid_surface, CYAN, rect)
        
        # Draw Grid Lines + spots
        self.grid.draw(grid_surface, bg_image=self.bg_image)
        
        # Smoke FIRST (background effect)
        draw_smoke(self.grid, grid_surface)
        
        # Agent LAST (top layer)
        for agent in self.agents:
            if agent.alive: # Only draw if they haven't perished
                # Ensure the agent's current spot width is updated for scaling
                if agent.spot:
                    agent.spot.width = cell_size
                agent.draw(grid_surface)
        
        # Blit the grid surface onto the main window at centered position
        self.win.blit(grid_surface, (grid_x, grid_y))

        # Draw the white separator bar between grid and panel
        panel_x = self.width
        pygame.draw.rect(self.win, WHITE, (panel_x, 0, 2, win_height))

        # Draw simulation panel
        self.draw_sim_panel()
        self.manager.draw_ui(self.win)

        pygame.display.update()

    # ---------------- MAIN LOOP ----------------
    def run(self) -> int:
        while self.running:
            # Handle events first so step-by-step requests ("n") are registered
            action = self.handle_events()
            if action == SIM_EDITOR:
                self.running = False
                return SIM_EDITOR

            if action == SIM_QUIT:
                # plot_fire_environment(self.history)
                # plot_path_length(self.history)
                self.running = False
                return SIM_QUIT

            # Now update time manager (which will consume next-step requests)
            should_update = self.time_manager.update()

            # Update GUI manager with proper dt (after time update)
            self.manager.update(self.time_manager.get_delta_time())

            # Update simulation if time_manager says so
            if should_update:
                self.update(self.time_manager.get_delta_time())

            self.draw()

        return SIM_QUIT

    def update_metrics(self) -> None:
        # Use time_manager for elapsed time
        self.metrics['elapsed_time'] = self.time_manager.get_total_time()
        
        # Agent
        if self.agents:
        # Track the average health or just the first agent's health
            self.metrics['agent_health'] = sum(a.health for a in self.agents) / len(self.agents)
            self.metrics['path_length'] = len(self.agents[0].path) if self.agents[0].path else 0
        
        # Count fire cells and average temperature
        if hasattr(self.grid, "temp_np") and hasattr(self.grid, "smoke_np") and hasattr(self.grid, "fire_np"):
            self.metrics['fire_cells'] = int(np.count_nonzero(self.grid.fire_np))
            self.metrics['avg_temp'] = float(np.mean(self.grid.temp_np))
            self.metrics['avg_smoke'] = float(np.mean(self.grid.smoke_np))
        else:
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

            self.metrics['avg_smoke'] = total_smoke / cells
            self.metrics['fire_cells'] = fire_count
            self.metrics['avg_temp'] = total_temp / cells

        self.history["time"].append(self.metrics["elapsed_time"])
        self.history["fire_cells"].append(self.metrics["fire_cells"])
        self.history["avg_temp"].append(self.metrics["avg_temp"])
        self.history["avg_smoke"].append(self.metrics["avg_smoke"] * 500)
        self.history["agent_health"].append(self.metrics["agent_health"])
        self.history["path_length"].append(self.metrics["path_length"])
    
    def draw_sim_panel(self) -> None:
        # Draw panel background at full window height.  
        win_width, win_height = self.win.get_size()
        panel_rect = pygame.Rect(self.width, 0, self.tools_width, win_height)
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

        
        # Draw agent status pinned to the bottom of the panel
        if self.agents:
            # leave a small margin above the bottom of the window
            main_agent = self.agents[0]
            status_y = win_height - int(60 * self.scale)
            status = "ALIVE" if main_agent.alive else "DEAD"
            status_color = (0, 255, 0) if main_agent.alive else (255, 0, 0)
            status_surface = self.font.render(f"Agent: {status}", True, status_color)
            self.win.blit(status_surface, (self.width + int(15 * self.scale), status_y - int(30 * self.scale)))
            
            # Draw health bar immediately below the status text
            bar_width = int(180 * self.scale)
            health_width = int(bar_width * (main_agent.health / 100))
            pygame.draw.rect(self.win, (50, 50, 50), 
                           (self.width + int(10 * self.scale), status_y + int(25 * self.scale), bar_width, int(20 * self.scale)))
            pygame.draw.rect(self.win, status_color, 
                           (self.width + int(10 * self.scale), status_y, health_width, int(20 * self.scale)))
            
            # Draw health text
            health_text = self.font.render(f"{main_agent.health:.0f}%", True, (255, 255, 255))
            text_x = self.width + bar_width // 2 - health_text.get_width() // 2
            self.win.blit(health_text, (text_x, status_y + int(2 * self.scale)))

def draw_temperature(grid: "Grid", win: pygame.Surface, rows: int) -> None:
    """Draw temperature as color overlay"""
    if not hasattr(grid, "temp_np"):
        return

    cell = grid.cell_size
    temp = grid.temp_np

    intensity = np.clip((temp - 30.0) / 300.0, 0.0, 1.0)
    alpha = (100.0 * intensity).astype(np.uint8)
    mask = intensity > 0

    if not np.any(mask):
        return

    red = np.full_like(alpha, 255, dtype=np.uint8)
    green = (255.0 * (1.0 - intensity)).astype(np.uint8)
    blue = np.zeros_like(alpha, dtype=np.uint8)

    red = np.where(mask, red, 0)
    green = np.where(mask, green, 0)
    blue = np.where(mask, blue, 0)
    alpha = np.where(mask, alpha, 0)

    rows, cols = temp.shape
    overlay = pygame.Surface((cols, rows), pygame.SRCALPHA)
    rgb = np.stack([red.T, green.T, blue.T], axis=2)
    alpha_t = alpha.T

    pixels = pygame.surfarray.pixels3d(overlay)
    pixels_alpha = pygame.surfarray.pixels_alpha(overlay)
    pixels[:] = rgb
    pixels_alpha[:] = alpha_t
    del pixels
    del pixels_alpha

    scaled = pygame.transform.scale(
        overlay,
        (cols * cell, rows * cell)
    )
    win.blit(scaled, (0, 0))

def plot_fire_environment(history: Dict[str, List[float]]) -> None:
    import matplotlib.pyplot as plt
    time = history["time"]

    plt.figure(figsize=(10, 6))

    plt.plot(time, history["fire_cells"], label="Fire Cells")
    plt.plot(time, history["avg_temp"], label="Average Temperature (°C)")
    plt.plot(time, history["avg_smoke"], label="Average Smoke Density")

    plt.xlabel("Time (seconds)")
    plt.ylabel("Magnitude")
    plt.title("Fire, Temperature, and Smoke Evolution Over Time")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()
def plot_path_length(history: Dict[str, List[float]]) -> None:
    import matplotlib.pyplot as plt
    time = history["time"]
    path_length = history["path_length"]

    plt.figure(figsize=(10, 5))

    plt.plot(time, path_length)
    plt.xlabel("Time (seconds)")
    plt.ylabel("Path Length (cells)")
    plt.title("Path Length Variation Due to Dynamic Replanning")
    plt.grid(True)

    plt.tight_layout()
    plt.show()