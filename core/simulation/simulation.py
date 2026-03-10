import logging
import time
from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np
import pygame
import pygame_gui
from core.building import Building
from core.simulation.sim_renderer import SimRenderer
from core.simulation.sim_analytics import SimAnalytics
from environment.fire import randomfirespot
from utils.utilities import Color, Dimensions, state_value, SimulationState, rTemp, load_layout, get_dpi_scale
from ui.slider import create_control_panel
from utils.save_manager import SaveManager, SimulationSnapshot
from utils.time_manager import TimeManager

if TYPE_CHECKING:
    from core.agent.agent import Agent
    from core.grid import Grid

logger = logging.getLogger(__name__)

SIM_QUIT = SimulationState.SIM_QUIT.value
SIM_EDITOR = SimulationState.SIM_EDITOR.value
SIM_CONTINUE = SimulationState.SIM_CONTINUE.value

WALL = state_value.WALL.value
EMPTY = state_value.EMPTY.value
START = state_value.START.value
END = state_value.END.value

class Simulation:
    """Top-level simulation controller.

    Owns the Building, agents, time manager, and history buffers.
    Delegates rendering to SimRenderer and analytics to SimAnalytics
    via composition (mixed in through multiple inheritance).
    """

    def __init__(
        self,
        win: pygame.Surface,
        building: "Building",
        agents: Optional["Agent"],
        rows: int,
        width: int,
        bg_image: Optional[pygame.Surface] = None,
    ) -> None:
        self.win = win
        self.building = building
        self.grid = building.get_floor(0)
        self.agents = agents
        self.rows = rows
        self.orignal_width = width
        # when the display scale changes we keep track of a factor used to convert our hard‑coded dimensions into physically‑sized pixels
        self.scale = get_dpi_scale(pygame.display.get_wm_info()['window'])

        self.tools_width = int(200 * self.scale)  # scaled panel width
        self.width = self.win.get_size()[0] - self.tools_width  # initial grid width
        self.bg_image = bg_image

        # snapshot layout right away so RESET has something to restore from;
        # do this before any updates or fire is set
        for floor in self.building.floors:
            floor.backup_layout()
        # remember layout_filename so later resets can reload from the CSV file
        self.layout_file = getattr(self.grid, "layout_filename", None)

        self.time_manager = TimeManager(fps=120, step_size=1)  # Keep your 120 FPS

        self.running = True
        self.show_controls = False
        self.fire_set = False  
        self.restart_timer = False

        # choose a font size that scales with DPI so text remains readable
        self.font = pygame.font.Font(None, int(24 * self.scale))
        self.history = {
            "time": [],
            "fire_cells": [],              # building-wide total
            "fire_cells_per_floor": [],    # [floor_0, floor_1, ...]
            "avg_temp": [],                # building-wide average
            "avg_temp_per_floor": [],      # [floor_0, floor_1, ...]
            "avg_smoke": [],               # building-wide average
            "avg_smoke_per_floor": [],     # [floor_0, floor_1, ...]
            "agent_health": [],
            "path_length": []
        }

        # Persistence/analytics state
        self.session_seed = int(time.time())
        self.fire_timeline: List[tuple[float, int, int, int]] = []
        self._last_fire_masks = [
            np.zeros((self.rows, self.rows), dtype=np.bool_) for _ in range(self.building.num_floors)
        ]
        self.agent_exit_times: Dict[int, float] = {}

        self.manager = pygame_gui.UIManager(self.win.get_size())
        self.temp = rTemp()
        self.create_sliders()

        # Submodules (composition like Agent's agent_modules)
        self.renderer = SimRenderer(self)
        self.analytics = SimAnalytics(self)

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

                elif event.key == pygame.K_m:
                    self.building.current_floor = (self.building.current_floor + 1) % self.building.num_floors

                elif event.key == pygame.K_e:
                    return SIM_EDITOR

                elif event.key == pygame.K_h:
                    self.show_controls = not self.show_controls

                elif event.key == pygame.K_F5:
                    path = self.analytics.save_snapshot()
                    logger.info("Simulation snapshot saved: %s", path)

                elif event.key == pygame.K_F6:
                    path = self.analytics.export_history_csv()
                    logger.info("Simulation history CSV exported: %s", path)

                # Currently this does nothing except log the snapshot metadata, 
                # but in the future we could extend it to actually restore 
                # the simulation state from the snapshot 
                # (e.g. for debugging or to implement a "rewind" feature)
                elif event.key == pygame.K_F7:
                    snapshot = self.analytics.load_latest_snapshot()
                    if snapshot is None:
                        logger.info("No saved simulation snapshot found")
                    else:
                        logger.info(
                            "Loaded snapshot metadata: time=%ss survival=%s",
                            snapshot.evacuation_time,
                            snapshot.survival_count,
                        )

        return SIM_CONTINUE

    def reset(self) -> None:
        # Clear analytics state so previous-run data doesn't bleed into the next run
        self.fire_timeline.clear()
        self.agent_exit_times.clear()
        self._last_fire_masks = [
            np.zeros((self.rows, self.rows), dtype=np.bool_) for _ in range(self.building.num_floors)
        ]
        for key in self.history:
            self.history[key].clear()
        self.session_seed = int(time.time())

        # Reset simulation-level flags (once, not per-floor)
        self.fire_set = False
        self.time_manager.reset_timer()

        # 1. Restore every floor from its initial_layout snapshot
        for floor in self.building.floors:
            floor.clear_simulation_visuals()

            layout = floor.initial_layout
            for r, row in enumerate(floor.grid):
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

            floor.backup_layout()
            floor.mark_material_cache_dirty()
            floor.ensure_material_cache()
            floor.update_np_arrays()

        # 2. Reset every agent (once, after all floors are restored)
        active_floor = self.building.get_floor(0)
        for i, agent in enumerate(self.agents):
            agent.reset()
            if i < len(active_floor.start):
                agent.spot = active_floor.start[i]
            else:
                agent.spot = active_floor.start[0] if active_floor.start else None

            if agent.spot and bool(active_floor.exits):
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
            
            # Generate fire once
            if not self.fire_set:
                has_sources = any(floor.fire_sources for floor in self.building.floors)
                if has_sources:
                    for floor in self.building.floors:
                        for r, c in floor.fire_sources:
                            floor.grid[r][c].set_as_fire_source()
                    self.fire_set = True
                else:
                    for floor in self.building.floors:
                        randomfirespot(floor, floor.rows)
                        
            # Udate fire and smoke spread
            self.building.update_all_floor(update_dt)
            
            # Update all agent with delta time
            for idx, agent in enumerate(self.agents):
                agent.update(update_dt)
                if agent.spot and agent.spot.is_end() and idx not in self.agent_exit_times:
                    self.agent_exit_times[idx] = self.time_manager.get_total_time()

            # Track new ignitions for timeline export
            self.analytics.record_new_fire_events()
            
            # Update metrics
            self.analytics.update_metrics()

    def run(self) -> int: # Main simulation loop
        pygame.event.clear() 
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

            self.renderer.draw(self.building.current_floor)

        return SIM_QUIT
