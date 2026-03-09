"""SimRenderer - Handles all drawing and rendering for the simulation."""
import logging
from typing import Dict, List, TYPE_CHECKING

import numpy as np
import pygame

from utils.utilities import Color

if TYPE_CHECKING:
    from core.grid import Grid
    from core.simulation.simulation import Simulation

logger = logging.getLogger(__name__)

WHITE = Color.WHITE.value
CYAN = Color.CYAN.value


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

        # Agents on top
        for agent in sim.agents:
            if agent.alive and to_draw_floor.floor == agent.current_floor:
                if agent.spot:
                    agent.spot.width = cell_size
                agent.draw(grid_surface)

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

        # Title
        title_font = pygame.font.SysFont(None, 24)
        title = title_font.render("SIMULATION", True, (255, 255, 255))
        sim.win.blit(title, (sim.width + 100 - title.get_width() // 2, 20))

        # Compute outcome metrics
        y_offset = 60
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
                outcome = "Deceased"
            elif primary and primary.health < 100:
                outcome = "Injured"
            else:
                outcome = "Alive"

            outcome_metrics = [
                f"Agent Outcome: {outcome}",
                f"Health: {sim.building.metrics['agent_health']:.1f}",
                f"Evac Time: {avg_evac:.1f}s",
            ]
        else:
            outcome_metrics = [
                f"Escaped: {escaped}",
                f"Injured: {injured}",
                f"Deceased: {deceased}",
                f"Avg Evac Time: {avg_evac:.1f}s",
            ]

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
            f"Current Floor: {sim.building.current_floor + 1}",
            "Controls:",
            "P: Pause/Resume",
            "S: Step Mode",
            "N: Next Step",
            "+/-: Speed",
            "R: Reset",
            "E: Editor Mode",
            "M: Change Floor",
            "F5: Save Snapshot",
            "F6: Export CSV",
            "F7: Load Last Snapshot",
            "ESC: Quit"
        ]

        # Status indicator
        if sim.time_manager.is_paused():
            status = "PAUSED"
            status_color = (255, 200, 0)
        elif sim.time_manager.is_step_mode():
            status = "STEP MODE"
            status_color = (0, 200, 255)
        else:
            status = "RUNNING"
            status_color = (0, 255, 0)

        status_surface = sim.font.render(f"Status: {status}", True, status_color)
        sim.win.blit(status_surface, (sim.width + 15, y_offset))
        y_offset += 25

        for text in metrics:
            if text:
                text_surface = sim.font.render(text, True, (220, 220, 220))
                sim.win.blit(text_surface, (sim.width + 15, y_offset))
            y_offset += 25

        # Health bar pinned to bottom
        if sim.agents:
            health = float(sim.building.metrics.get('agent_health', 0)) / 100.0
            if not np.isfinite(health):
                health = 0.0
            health = max(0.0, min(1.0, health))
            alive = health > 0
            status_y = win_height - int(60 * sim.scale)
            status = "ALIVE" if alive else "DEAD"
            status_color = (0, 255, 0) if alive else (255, 0, 0)
            status_surface = sim.font.render(f"Agent: {status}", True, status_color)
            sim.win.blit(status_surface, (sim.width + int(15 * sim.scale), status_y - int(30 * sim.scale)))

            bar_width = int(180 * sim.scale)
            health_width = int(max(0.0, health) * bar_width)
            pygame.draw.rect(sim.win, (50, 50, 50),
                             (sim.width + int(10 * sim.scale), status_y + int(25 * sim.scale), bar_width, int(20 * sim.scale)))
            pygame.draw.rect(sim.win, status_color,
                             (sim.width + int(10 * sim.scale), status_y, health_width, int(20 * sim.scale)))

            health_text = sim.font.render(f"{health * 100:.0f}%", True, (255, 255, 255))
            text_x = sim.width + bar_width // 2 - health_text.get_width() // 2
            sim.win.blit(health_text, (text_x, status_y + int(2 * sim.scale)))


# --------------- Free functions (temperature overlay, matplotlib plots) ---------------

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
