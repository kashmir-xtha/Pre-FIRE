# smokespread.py
# Use the same constants as firespread.py
import pygame
from utilities import state_value, smoke_constants

def spread_smoke(state_grid, smoke_grid, rows, cols):
    """
    state_grid : 2D grid of cell types (EMPTY, WALL, FIRE, START, END)
    smoke_grid : 2D grid of smoke density [0..1]
    """
    # Create next smoke grid
    next_smoke = [[smoke_grid[r][c] for c in range(cols)] for r in range(rows)]

    for r in range(rows):
        for c in range(cols):
            if state_grid[r][c] == state_value.WALL.value:
                next_smoke[r][c] = 0
                continue

            # Fire produces smoke
            if state_grid[r][c] == state_value.FIRE.value:
                next_smoke[r][c] = smoke_constants.MAX_SMOKE.value
                continue

            # Diffusion from neighbors
            total = 0
            count = 0

            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if state_grid[nr][nc] != state_value.WALL.value:
                        total += smoke_grid[nr][nc]
                        count += 1

            if count > 0:
                diffusion = smoke_constants.SMOKE_DIFFUSION.value * (total / count - smoke_grid[r][c])
                next_smoke[r][c] += diffusion

            # Natural decay
            next_smoke[r][c] *= (1 - smoke_constants.SMOKE_DECAY.value)
            # Clamp
            next_smoke[r][c] = max(0, min(smoke_constants.MAX_SMOKE.value, next_smoke[r][c]))

    return next_smoke

def draw_smoke(grid, WIN, ROWS):
    cell = grid.cell_size
    for r in range(ROWS):
        for c in range(ROWS):
            s = grid.smoke[r][c]
            if s > 0:
                shade = int(255 * (1 - min(0.7, s * 5)))  # Denser smoke is darker
                pygame.draw.rect(
                    WIN,
                    (shade, shade, shade),
                    (c * cell, r * cell, cell, cell)
                )