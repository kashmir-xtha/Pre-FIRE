"""SimRenderer - Handles all drawing and rendering for the simulation."""
import logging
from typing import Dict, List, TYPE_CHECKING

import numpy as np
import pygame

from utils.utilities import Color
from environment.fire import EFFECT_RADIUS, _has_line_of_sight
if TYPE_CHECKING:
    from core.grid import Grid
    from core.simulation.simulation import Simulation

logger = logging.getLogger(__name__)

WHITE = Color.WHITE.value
CYAN = Color.CYAN.value
AGENT_COLORS = [
    (0, 191, 255),   # Deep Sky Blue (Agent 1)
    (0, 255, 0),   # Green (Agent 2)
    (255, 0, 0)    # Red (Agent 3)
]

class SimRenderer:
    """
    Handles all rendering for the Simulation.

    Delegates drawing of the grid, agents, panel, and overlays.
    """

    def __init__(self, sim: "Simulation") -> None:
        self.sim = sim

    def draw(self, floor_num: int) -> None:
        """Draw the full simulation frame: grid, agents, smoke, panel."""
        sim = self.sim
        to_draw_floor = sim.building.get_floor(floor_num)
        win_width, win_height = sim.win.get_size()

        sim.win.fill(WHITE)

        grid_width = sim.width
        grid_height = min(grid_width, win_height)
        cell_size = grid_height // sim.rows
        grid_pixel_width = cell_size * sim.rows

        grid_x = 0
        grid_y = (win_height - grid_height) // 2 if win_height > grid_height else 0

        grid_surface = pygame.Surface((grid_pixel_width, grid_height))
        grid_surface.fill(WHITE)

        to_draw_floor.cell_size = cell_size
        to_draw_floor.update_geometry(cell_size)

        # Draw agent paths
        for agent in sim.agents:
            if agent.path and agent.path_show and to_draw_floor.floor == agent.current_floor:
                for p in agent.path:
                    if p != agent.spot and not p.is_start() and not p.is_end():
                        rect = pygame.Rect(p.x, p.y, p.width, p.width)
                        pygame.draw.rect(grid_surface, CYAN, rect)

        # Draw grid + spots
        to_draw_floor.draw(grid_surface, bg_image=sim.bg_image)

        # Smoke overlay
        from environment.smoke import draw_smoke
        draw_smoke(to_draw_floor, grid_surface)
        # Draw sprinkler indicators
        for r in range(sim.rows):
            for c in range(sim.rows):
                spot = to_draw_floor.grid[r][c]
                if not spot.is_sprinkler():
                    continue

                cx = spot.x + cell_size // 2
                cy = spot.y + cell_size // 2

                cfg = sim.temp
                cell_size_m = max(cfg.CELL_SIZE_M, 1e-6)
                effect_radius = max(1, round(EFFECT_RADIUS / cell_size_m))

                # Draw radius cell by cell, skipping walled-off cells
                fill_color = (0, 120, 255, 18) if spot.is_sprinkler_active() else (0, 180, 255, 10)
                ring_color  = (0, 120, 255, 60) if spot.is_sprinkler_active() else (0, 180, 255, 35)

                for nr in range(max(0, r - effect_radius), min(sim.rows, r + effect_radius + 1)):
                    for nc in range(max(0, c - effect_radius), min(sim.rows, c + effect_radius + 1)):
                        dist_m = ((nr - r)**2 + (nc - c)**2) ** 0.5 * cell_size_m
                        if dist_m > EFFECT_RADIUS:
                            continue
                        if not _has_line_of_sight(to_draw_floor, r, c, nr, nc):
                            continue

                        cell_surf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                        target = to_draw_floor.grid[nr][nc]
                        nx = target.x
                        ny = target.y

                        # Fill reachable cell
                        pygame.draw.rect(cell_surf, fill_color, (0, 0, cell_size, cell_size))
                        grid_surface.blit(cell_surf, (nx, ny))

                # Outline the reachable boundary — only cells on the edge of the reachable zone
                for nr in range(max(0, r - effect_radius), min(sim.rows, r + effect_radius + 1)):
                    for nc in range(max(0, c - effect_radius), min(sim.rows, c + effect_radius + 1)):
                        dist_m = ((nr - r)**2 + (nc - c)**2) ** 0.5 * cell_size_m
                        if dist_m > EFFECT_RADIUS:
                            continue
                        if not _has_line_of_sight(to_draw_floor, r, c, nr, nc):
                            continue

                        # Check if any neighbour is outside the reachable zone (makes it a boundary cell)
                        is_edge = False
                        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nnr, nnc = nr + dr, nc + dc
                            if not (0 <= nnr < sim.rows and 0 <= nnc < sim.rows):
                                is_edge = True
                                break
                            n_dist = ((nnr - r)**2 + (nnc - c)**2) ** 0.5 * cell_size_m
                            n_blocked = not _has_line_of_sight(to_draw_floor, r, c, nnr, nnc)
                            if n_dist > EFFECT_RADIUS or n_blocked:
                                is_edge = True
                                break

                        if is_edge:
                            target = to_draw_floor.grid[nr][nc]
                            edge_surf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                            pygame.draw.rect(edge_surf, ring_color, (0, 0, cell_size, cell_size), 2)
                            grid_surface.blit(edge_surf, (target.x, target.y))

                # Sprinkler head dot on top
                dot_color = (0, 120, 255) if spot.is_sprinkler_active() else (0, 180, 255)
                pygame.draw.circle(grid_surface, dot_color, (cx, cy), max(2, cell_size // 3))


        # Agents on top
        for i, agent in enumerate(sim.agents):
            if agent.alive and to_draw_floor.floor == agent.current_floor: 
                indicator_color = AGENT_COLORS[i % len(AGENT_COLORS)]
                if agent.spot:
                    agent.spot.width = cell_size
                agent.draw(grid_surface, tint_color=indicator_color)
        
        sim.win.blit(grid_surface, (grid_x, grid_y))

        # Separator
        panel_x = sim.width
        pygame.draw.rect(sim.win, WHITE, (panel_x, 0, 2, win_height))

        # Side panel
        self.draw_sim_panel()
        sim.manager.draw_ui(sim.win)

        pygame.display.update()

    def draw_sim_panel(self) -> None:
        """Draw the side panel with metrics, controls, and health bar."""
        sim = self.sim
        win_width, win_height = sim.win.get_size()
        panel_rect = pygame.Rect(sim.width, 0, sim.tools_width, win_height)
        pygame.draw.rect(sim.win, (40, 40, 50), panel_rect)
        pygame.draw.rect(sim.win, (60, 60, 70), panel_rect, width=2)

        # Title — always visible
        title_font = pygame.font.SysFont(None, 24)
        title = title_font.render("SIMULATION", True, (255, 255, 255))
        sim.win.blit(title, (sim.width + 100 - title.get_width() // 2, 20))

        y_offset = 60

        if sim.show_controls:
            # Controls view
            controls = [
                "Controls:",
                "P: Pause/Resume",
                "S: Step Mode",
                "N: Next Step",
                "+/-: Speed",
                "R: Reset",
                "E: Editor Mode",
                "M: Change Floor",
                "H: Show Metrics",
                "F5: Save Snapshot",
                "F6: Export CSV",
                "F7: Load Last Snapshot",
                "F8: Generate Heatmap",
                "F9: Congestion Map",
                "ESC: Quit",
            ]
            for text in controls:
                text_surface = sim.font.render(text, True, (220, 220, 220))
                sim.win.blit(text_surface, (sim.width + 15, y_offset))
                y_offset += 25

        else:
            # Metrics view
            escaped = sum(1 for a in sim.agents if a.spot and a.spot.is_end())
            deceased = sum(1 for a in sim.agents if a.health <= 0)
            injured = sum(1 for a in sim.agents if 0 < a.health < 100 and not (a.spot and a.spot.is_end()))
            avg_evac = float(np.mean(list(sim.agent_exit_times.values()))) if sim.agent_exit_times else 0.0
            max_fire = max(sim.history["fire_cells"]) if sim.history["fire_cells"] else 0
            max_smoke = max(sim.history["avg_smoke"]) if sim.history["avg_smoke"] else 0.0

            is_single_agent = len(sim.agents) == 1
            if is_single_agent:
                primary = sim.agents[0] if sim.agents else None
                if primary and primary.spot and primary.spot.is_end():
                    outcome = "Escaped"
                elif primary and primary.health <= 0:
                    outcome = "Dead"
                elif primary and primary.health < 90:
                    outcome = "Injured"
                else:
                    outcome = "Alive"
                outcome_metrics = [
                    f"Agent Outcome: {outcome}",
                    f"Health: {np.mean(sim.building.metrics['agent_health']):.1f}",
                    f"Evac Time: {avg_evac:.1f}s",
                ]
            else:
                outcome_metrics = [
                    f"Escaped: {escaped}",
                    f"Injured: {injured}",
                    f"Deceased: {deceased}",
                    f"Avg Evac Time: {avg_evac:.1f}s",
                ]

            # Status indicator
            if sim.time_manager.is_paused():
                status, status_color = "PAUSED", (255, 200, 0)
            elif sim.time_manager.is_step_mode():
                status, status_color = "STEP MODE", (0, 200, 255)
            else:
                status, status_color = "RUNNING", (0, 255, 0)

            status_surface = sim.font.render(f"Status: {status}", True, status_color)
            sim.win.blit(status_surface, (sim.width + 15, y_offset))
            y_offset += 25

            metrics = [
                f"Time: {sim.building.metrics['elapsed_time']:.1f}s",
                f"Step: {sim.time_manager.get_simulation_step()}",
                f"FPS: {sim.time_manager.get_fps():.1f}",
                f"Speed: {sim.time_manager.get_step_size()}x",
                f"Fire Cells: {sim.building.metrics['fire_cells']}",
                f"Avg Smoke: {sim.building.metrics['avg_smoke']:.3f}",
                f"Avg Temp: {sim.building.metrics['avg_temp']:.1f}°C",
                f"Path Length: {sim.building.metrics['path_length']}",
                *outcome_metrics,
                f"Peak Fire Cells: {max_fire}",
                f"Peak Smoke: {max_smoke:.3f}",
                f"Current Floor:{'Ground' if sim.building.current_floor == 0 else sim.building.current_floor}",
                "",
                "H: Show Controls",
            ]

            for text in metrics:
                if text:
                    text_surface = sim.font.render(text, True, (220, 220, 220))
                    sim.win.blit(text_surface, (sim.width + 15, y_offset))
                y_offset += 25

        # Health bar — always visible
        if sim.agents:
            start_y = win_height - int(200 * sim.scale) 
            floor_index = 0
            for i, agent in enumerate(sim.agents):
                if agent.current_floor != sim.building.current_floor:
                    continue  
                
                agent_offset = floor_index * (int(65 * sim.scale))
                status_y = start_y + agent_offset
                floor_index += 1
                
                status_text = "ALIVE" if agent.alive else "DEAD"
                
                # Health Bar Dimensions
                bar_width = int(180 * sim.scale)
                bar_height = int(22 * sim.scale)
                bar_x = sim.width + int(10 * sim.scale)
                # Position bar slightly below the label
                bar_y = status_y + int(25 * sim.scale)
                
                # Draw Background
                pygame.draw.rect(sim.win, (30, 30, 30), (bar_x, bar_y, bar_width, bar_height))
                
                # Draw Health Fill
                health_ratio = max(0, min(1, agent.health / 100))
                fill_width = int(bar_width * health_ratio)
                
                fill_color = (100, 100, 100) if not agent.alive else \
                             (34, 197, 94) if health_ratio > 0.6 else \
                             (234, 179, 8) if health_ratio > 0.3 else (239, 68, 68)
                
                if fill_width > 0:
                    pygame.draw.rect(sim.win, fill_color, (bar_x, bar_y, fill_width, bar_height))
                
                # Draw Percentage centered
                health_text = sim.font.render(f"{agent.health:.0f}%", True, (255, 255, 255))
                text_x = bar_x + (bar_width // 2) - (health_text.get_width() // 2)
                text_y = bar_y + (bar_height // 2) - (health_text.get_height() // 2)
                sim.win.blit(health_text, (text_x, text_y))

                # Differentiate agents based on color
                indicator_color = AGENT_COLORS[i % len(AGENT_COLORS)]        
                # Agent Label
                label_surface = sim.font.render(f"Agent {i+1}: {status_text}", True, indicator_color)
                sim.win.blit(label_surface, (sim.width + int(15 * sim.scale), status_y))

                # Draw a thin border around the bar for better definition
                pygame.draw.rect(sim.win, indicator_color, (bar_x, bar_y, bar_width, bar_height), 2)

# Free functions (temperature overlay, matplotlib plots)
def draw_temperature(grid: "Grid", win: pygame.Surface, rows: int) -> None:
    """Draw temperature as color overlay."""
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

    rows_t, cols = temp.shape
    overlay = pygame.Surface((cols, rows_t), pygame.SRCALPHA)
    rgb = np.stack([red.T, green.T, blue.T], axis=2)
    alpha_t = alpha.T

    pixels = pygame.surfarray.pixels3d(overlay)
    pixels_alpha = pygame.surfarray.pixels_alpha(overlay)
    pixels[:] = rgb
    pixels_alpha[:] = alpha_t
    del pixels
    del pixels_alpha

    scaled = pygame.transform.scale(overlay, (cols * cell, rows_t * cell))
    win.blit(scaled, (0, 0))


def plot_fire_environment(history: Dict[str, List[float]]) -> None:
    import matplotlib.pyplot as plt

    t = history["time"]
    plt.figure(figsize=(10, 6))
    plt.plot(t, history["fire_cells"], label="Fire Cells")
    plt.plot(t, history["avg_temp"], label="Average Temperature (°C)")
    plt.plot(t, [s * 500 for s in history["avg_smoke"]], label="Average Smoke Density (×500)")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Magnitude")
    plt.title("Fire, Temperature, and Smoke Evolution Over Time")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_path_length(history: Dict[str, List[float]]) -> None:
    import matplotlib.pyplot as plt

    t = history["time"]
    plt.figure(figsize=(10, 5))
    plt.plot(t, history["path_length"])
    plt.xlabel("Time (seconds)")
    plt.ylabel("Path Length (cells)")
    plt.title("Path Length Variation Due to Dynamic Replanning")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
