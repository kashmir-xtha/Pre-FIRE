import logging
from typing import Dict, Sequence, Union, TYPE_CHECKING
import numpy as np
import pygame

from utils.utilities import smoke_constants, rTemp

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot

logger = logging.getLogger(__name__)

def spread_smoke(
    grid_data: Union["Grid", Sequence[Sequence["Spot"]]],
    dt: float = 1.0,
) -> None:
    """
    Optimized smoke spread using numpy diffusion on the Grid's smoke array.
    Barriers block diffusion; fire cells only produce smoke.
    """

    # Handle both Grid object and list inputs for compatibility
    if hasattr(grid_data, 'neighbor_map'):
        grid = grid_data.grid
        rows = grid_data.rows
        cols = grid_data.rows
        smoke = grid_data.smoke_np
        
        temp_constants = rTemp()
        diffusion = temp_constants.SMOKE_DIFFUSION
        decay = temp_constants.SMOKE_DECAY
        max_smoke = temp_constants.MAX_SMOKE
        production = temp_constants.SMOKE_PRODUCTION

        # Vectorized extraction of is_barrier and is_fire using state lookups
        is_barrier = grid_data.is_barrier_np
        is_fire = grid_data.fire_np

        coeff = np.full((rows, cols), diffusion, dtype=np.float32)
        coeff[is_barrier] = 0.0

        smoke_pad = np.pad(smoke, 1, mode="edge")
        coeff_pad = np.pad(coeff, 1, mode="edge")

        center = smoke

        n = smoke_pad[0:rows, 1:cols + 1]
        s = smoke_pad[2:rows + 2, 1:cols + 1]
        w = smoke_pad[1:rows + 1, 0:cols]
        e = smoke_pad[1:rows + 1, 2:cols + 2]
        nw = smoke_pad[0:rows, 0:cols]
        ne = smoke_pad[0:rows, 2:cols + 2]
        sw = smoke_pad[2:rows + 2, 0:cols]
        se = smoke_pad[2:rows + 2, 2:cols + 2]

        n_c = coeff_pad[0:rows, 1:cols + 1]
        s_c = coeff_pad[2:rows + 2, 1:cols + 1]
        w_c = coeff_pad[1:rows + 1, 0:cols]
        e_c = coeff_pad[1:rows + 1, 2:cols + 2]
        nw_c = coeff_pad[0:rows, 0:cols]
        ne_c = coeff_pad[0:rows, 2:cols + 2]
        sw_c = coeff_pad[2:rows + 2, 0:cols]
        se_c = coeff_pad[2:rows + 2, 2:cols + 2]

        coeff_n = np.minimum(coeff, n_c)
        coeff_s = np.minimum(coeff, s_c)
        coeff_w = np.minimum(coeff, w_c)
        coeff_e = np.minimum(coeff, e_c)
        coeff_nw = np.minimum(coeff, nw_c)
        coeff_ne = np.minimum(coeff, ne_c)
        coeff_sw = np.minimum(coeff, sw_c)
        coeff_se = np.minimum(coeff, se_c)

        def positive_diff(neighbor, current, edge_coeff):
            return np.maximum(neighbor - current, 0.0) * edge_coeff

        diffusion_sum = (
            positive_diff(n, center, coeff_n) +
            positive_diff(s, center, coeff_s) +
            positive_diff(w, center, coeff_w) +
            positive_diff(e, center, coeff_e) +
            positive_diff(nw, center, coeff_nw) +
            positive_diff(ne, center, coeff_ne) +
            positive_diff(sw, center, coeff_sw) +
            positive_diff(se, center, coeff_se)
        )

        new_smoke = center + diffusion_sum

        decay_factor = 1.0 - (decay * dt)
        new_smoke *= decay_factor

        new_smoke[is_fire] = np.minimum(max_smoke, center[is_fire] + (3 * production * dt))
        new_smoke[is_barrier] = 0.0
        new_smoke = np.clip(new_smoke, 0.0, max_smoke)

        grid_data.smoke_np = new_smoke

        # Vectorized update of spot objects with direct array access
        for r in range(rows):
            row_spots = grid[r]
            row_smoke = new_smoke[r]
            for c in range(cols):
                row_spots[c]._smoke = float(row_smoke[c])
    else:
        # Legacy slow path - fallback
        from utils.utilities import get_neighbors
        grid = grid_data
        rows = len(grid)
        cols = len(grid[0])

        for r in range(rows):
            row_spots = grid[r]
            for c in range(cols):
                spot = row_spots[c]
                neighbor_smoke = [grid[nr][nc].smoke for nr, nc in get_neighbors(r, c, rows, cols)]
                spot.update_smoke_level(neighbor_smoke, dt)
            
def draw_smoke(
    grid_data: Union["Grid", Sequence[Sequence["Spot"]]],
    surface: pygame.Surface,
) -> None:
    """
    Draw smoke using a vectorized overlay when a Grid object is provided.
    Falls back to per-cell rendering for legacy list input.
    """
    if not grid_data:
        return

    if hasattr(grid_data, "smoke_np"):
        rows = grid_data.rows
        cols = grid_data.rows
        cell_width = grid_data.grid[0][0].width
        smoke = grid_data.smoke_np

        mask = smoke > 0.05
        if not np.any(mask):
            return

        gray = np.clip(150 - (smoke * 100.0), 40, 150)
        alpha = np.clip(smoke * 280.0, 0, 220)

        gray = np.where(mask, gray, 0).astype(np.uint8)
        alpha = np.where(mask, alpha, 0).astype(np.uint8)

        smoke_surface = pygame.Surface((cols, rows), pygame.SRCALPHA)
        rgb = np.stack([gray.T, gray.T, gray.T], axis=2)
        alpha_t = alpha.T

        pixels = pygame.surfarray.pixels3d(smoke_surface)
        pixels_alpha = pygame.surfarray.pixels_alpha(smoke_surface)
        pixels[:] = rgb
        pixels_alpha[:] = alpha_t
        del pixels
        del pixels_alpha

        scaled = pygame.transform.scale(
            smoke_surface,
            (cols * cell_width, rows * cell_width)
        )
        surface.blit(scaled, (0, 0))
        return

    grid = grid_data
    rows = len(grid)
    cols = len(grid[0])
    cell_width = grid[0][0].width

    smoke_surface = pygame.Surface((cell_width, cell_width), pygame.SRCALPHA)
    fill_rect = smoke_surface.fill
    blit = surface.blit

    for r in range(rows):
        y_pos = r * cell_width
        row = grid[r]

        for c in range(cols):
            s = row[c].smoke
            if s > 0.05:
                alpha = min(220, int(s * 280))
                gray = max(40, 150 - int(s * 100))
                fill_rect((gray, gray, gray, alpha))
                blit(smoke_surface, (c * cell_width, y_pos))

# Remaining debug functions kept as is
def visualize_smoke_density(grid: "Grid", rows: int) -> None:
    logger.info("=== Smoke Density Visualization ===")
    for r in range(min(10, rows)):
        row_str = ""
        for c in range(min(10, rows)):
            spot = grid.get_spot(r, c)
            if spot:
                smoke = spot.smoke
                if smoke > 0.7: row_str += "▓"
                elif smoke > 0.4: row_str += "▒"
                elif smoke > 0.1: row_str += "░"
                elif spot.is_barrier(): row_str += "█"
                elif spot.is_fire(): row_str += "F"
                else: row_str += " "
            else: row_str += " "
        logger.debug(row_str)

def clear_smoke(grid: "Grid", rows: int) -> None:
    for r in range(rows):
        for c in range(rows):
            spot = grid.get_spot(r, c)
            if spot: spot.set_smoke(0.0)

def get_smoke_statistics(grid: "Grid", rows: int) -> Dict[str, float]:
    total_smoke = 0.0
    max_smoke = 0.0
    smoke_cells = 0
    total_cells = rows * rows
    for r in range(rows):
        for c in range(rows):
            spot = grid.get_spot(r, c)
            if spot:
                smoke = spot.smoke
                total_smoke += smoke
                max_smoke = max(max_smoke, smoke)
                if smoke > 0: smoke_cells += 1
    return {
        'average_smoke': total_smoke / total_cells,
        'max_smoke': max_smoke,
        'smoke_cells': smoke_cells,
        'total_smoke': total_smoke
    }