import pygame
from utils.utilities import get_neighbors, smoke_constants

def spread_smoke(grid, dt = 1.0):
    """
    Enhanced smoke diffusion model using Gaussian diffusion.
    
    state_grid : 2D grid of cell types (EMPTY, WALL, FIRE, START, END)
    smoke_grid : 2D grid of smoke density [0..1]
    
    This model makes smoke spread much faster and further than fire,
    creating a realistic evacuation warning system.
    """
    # Create next smoke grid
    rows = len(grid) if grid else 0
    cols = len(grid[0]) if rows > 0 else 0 

    for r in range(rows):
        for c in range(cols):
            neighbor_smoke_data = []
            for nr, nc in get_neighbors(r, c, rows, cols):
                neighbor_smoke_data.append(grid[nr][nc].smoke)

            grid[r][c].update_smoke_level(neighbor_smoke_data, dt)
        
            
def draw_smoke(grid, surface):
    """
    Draw smoke on the given surface with improved visibility.
    Smoke is drawn under fire cells so fire remains visible.
    """
    # Use provided cell_size or grid's cell_size
    cell = grid[0][0].width if len(grid) > 0 and len(grid[0]) > 0 else 20
    rows = len(grid) if grid else 0
    
    for r in range(rows):
        for c in range(rows):
            s = grid[r][c].smoke
            if s > 0.01:  # Only draw if smoke is noticeable
                # Create smoke overlay with alpha
                smoke_surface = pygame.Surface((cell, cell), pygame.SRCALPHA)
                
                # Smoke visibility: higher density = more opaque and darker
                alpha = min(220, int(s * 280))  # s is between 0 and 1
                
                # Smoke color gets darker with density
                gray_level = max(40, 150 - int(s * 100))
                smoke_surface.fill((gray_level, gray_level, gray_level, alpha))
                surface.blit(smoke_surface, (c * cell, r * cell))

def visualize_smoke_density(grid, rows):
    """
    Debug function to visualize smoke density in console
    (Useful for testing smoke spread)
    
    :param grid: Grid object
    :param rows: Number of rows
    """
    print("\n=== Smoke Density Visualization ===")
    for r in range(min(10, rows)):  # Show first 10 rows
        row_str = ""
        for c in range(min(10, rows)):  # Show first 10 columns
            spot = grid.get_spot(r, c)
            if spot:
                smoke = spot.smoke
                if smoke > 0.7:
                    row_str += "▓"
                elif smoke > 0.4:
                    row_str += "▒"
                elif smoke > 0.1:
                    row_str += "░"
                elif spot.is_barrier():
                    row_str += "█"
                elif spot.is_fire():
                    row_str += "F"
                else:
                    row_str += " "
            else:
                row_str += " "
        print(row_str)

def clear_smoke(grid, rows):
    """
    Clear all smoke from the grid
    
    :param grid: Grid object
    :param rows: Number of rows
    """
    for r in range(rows):
        for c in range(rows):
            spot = grid.get_spot(r, c)
            if spot:
                spot.set_smoke(0.0)

def get_smoke_statistics(grid, rows):
    """
    Get statistics about smoke in the grid
    
    :param grid: Grid object
    :param rows: Number of rows
    :return: Dictionary with smoke statistics
    """
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
                if smoke > 0:
                    smoke_cells += 1
    
    return {
        'average_smoke': total_smoke / total_cells,
        'max_smoke': max_smoke,
        'smoke_cells': smoke_cells,
        'total_smoke': total_smoke
    }