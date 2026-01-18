import pygame
from utilities import get_neighbors, state_value, smoke_constants

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
                #next_smoke[r][c] = smoke_constants.MAX_SMOKE.value
                if(next_smoke[r][c]>1.0):
                    next_smoke[r][c]=1.0
                else:
                    next_smoke[r][c] += 0.15
                continue

            # Diffusion from neighbors
            total = 0
            count = 0

            for nr, nc in get_neighbors(r, c, rows, cols):
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
                #visually appealing
                surface = pygame.Surface((cell, cell), pygame.SRCALPHA)
                alpha = min(200, int(s * 255))
                surface.fill((25, 25, 25, alpha))
                WIN.blit(surface, (c * cell, r * cell))
                #below is more computationally efficient but less visually appealing
                #shade = int(255 * (1 - s))  # Denser smoke is darker
                # pygame.draw.rect(
                #     WIN,
                #     (shade, shade, shade),
                #     (c * cell, r * cell, cell, cell)
                # )