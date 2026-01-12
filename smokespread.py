# smokespread.py
# Use the same constants as firespread.py
import pygame
from firespread import EMPTY, WALL, FIRE, START, END

# Smoke parameters (tweakable)
SMOKE_DIFFUSION = 0.20    # how much smoke spreads
SMOKE_DECAY = 0.02       # smoke loss per step
MAX_SMOKE = 1.0

def spread_smoke(state_grid, smoke_grid, rows, cols):
    """
    state_grid : 2D grid of cell types (EMPTY, WALL, FIRE, START, END)
    smoke_grid : 2D grid of smoke density [0..1]
    """
    # Create next smoke grid
    next_smoke = [[smoke_grid[r][c] for c in range(cols)] for r in range(rows)]

    for r in range(rows):
        for c in range(cols):
            if state_grid[r][c] == WALL:
                next_smoke[r][c] = 0
                continue

            # Fire produces smoke
            if state_grid[r][c] == FIRE:
                next_smoke[r][c] = MAX_SMOKE
                continue

            # Diffusion from neighbors
            total = 0
            count = 0

            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if state_grid[nr][nc] != WALL:
                        total += smoke_grid[nr][nc]
                        count += 1

            if count > 0:
                diffusion = SMOKE_DIFFUSION * (total / count - smoke_grid[r][c])
                next_smoke[r][c] += diffusion

            # Natural decay
            next_smoke[r][c] *= (1 - SMOKE_DECAY)

            # Clamp
            next_smoke[r][c] = max(0, min(MAX_SMOKE, next_smoke[r][c]))

    return next_smoke

def draw_smoke(grid, WIN, ROWS):
    cell = grid.cell_size
    for r in range(ROWS):
        for c in range(ROWS):
            s = grid.smoke[r][c]
            if s > 0:
                shade = int(255 * (1 - s))
                pygame.draw.rect(
                    WIN,
                    (shade, shade, shade),
                    (c * cell, r * cell, cell, cell)
                )