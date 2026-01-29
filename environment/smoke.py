import pygame
import math
from utils.utilities import get_neighbors, state_value, smoke_constants

def spread_smoke(state_grid, smoke_grid, rows, cols):
    """
    Enhanced smoke diffusion model using Gaussian diffusion.
    
    state_grid : 2D grid of cell types (EMPTY, WALL, FIRE, START, END)
    smoke_grid : 2D grid of smoke density [0..1]
    
    This model makes smoke spread much faster and further than fire,
    creating a realistic evacuation warning system.
    """
    # Create next smoke grid
    next_smoke = [[0.0 for c in range(cols)] for r in range(rows)]

    for r in range(rows):
        for c in range(cols):
            if state_grid[r][c] == state_value.WALL.value:
                next_smoke[r][c] = 0
                continue

            # Fire produces smoke - significant production rate
            if state_grid[r][c] == state_value.FIRE.value:
                smoke_production = smoke_constants.SMOKE_PRODUCTION.value
                next_smoke[r][c] = min(1.0, smoke_grid[r][c] + smoke_production)
                continue

            # Initialize with current smoke value minus decay
            next_smoke[r][c] = smoke_grid[r][c] * (1 - smoke_constants.SMOKE_DECAY.value)

            # Diffusion from neighbors - Gaussian kernel approximation
            # Smoke spreads to all neighbors, with closer neighbors having more influence
            diffusion_rate = smoke_constants.SMOKE_DIFFUSION.value
            
            # Get all neighbors and apply weighted diffusion
            neighbor_data = []
            for nr, nc in get_neighbors(r, c, rows, cols):
                if state_grid[nr][nc] != state_value.WALL.value:
                    neighbor_data.append((nr, nc, smoke_grid[nr][nc]))
            
            # Calculate diffusion from all neighbors
            for nr, nc, neighbor_smoke in neighbor_data:
                # Smoke concentration gradient drives diffusion
                smoke_diff = neighbor_smoke - smoke_grid[r][c]
                
                # Only flow from higher to lower concentration
                if smoke_diff > 0:
                    # Weight diffusion by concentration difference (stronger for steep gradients)
                    diffusion = diffusion_rate * smoke_diff
                    next_smoke[r][c] += diffusion
                    
            # Clamp to valid range
            next_smoke[r][c] = max(0, min(smoke_constants.MAX_SMOKE.value, next_smoke[r][c]))

    return next_smoke

def draw_smoke(grid, surface, rows, cell_size=None):
    """
    Draw smoke on the given surface with improved visibility.
    Smoke is drawn under fire cells so fire remains visible.
    """
    # Use provided cell_size or grid's cell_size
    cell = cell_size if cell_size is not None else grid.cell_size
    
    for r in range(rows):
        for c in range(rows):
            s = grid.smoke[r][c]
            if s > 0.01:  # Only draw if smoke is noticeable
                # Create smoke overlay with alpha
                smoke_surface = pygame.Surface((cell, cell), pygame.SRCALPHA)
                
                # Smoke visibility: higher density = more opaque and darker
                alpha = min(220, int(s * 280))  # s is between 0 and 1
                
                # Smoke color gets darker with density
                gray_level = max(40, 150 - int(s * 100))
                smoke_surface.fill((gray_level, gray_level, gray_level, alpha))
                
                surface.blit(smoke_surface, (c * cell, r * cell))