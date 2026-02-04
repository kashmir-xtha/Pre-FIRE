import pygame
from utils.utilities import smoke_constants

def spread_smoke(grid_data, dt=1.0):
    """
    Optimized smoke spread. 
    Note: 'grid_data' here is the raw 2D list of spots (grid.grid), 
    but we need the 'grid object' to access the neighbor_map.
    
    Since the original signature passed 'grid.grid', we will detect if 
    we are getting the raw list or the object.
    
    BEST PRACTICE: Update your simulation.py to pass the 'grid object' to spread_smoke
    instead of 'grid.grid'. However, to be safe, we will implement a fallback 
    or rely on the fact that we can't get neighbor_map from a list.
    
    CRITICAL: You must update `simulation.py` line 125:
    OLD: spread_smoke(self.grid.grid, update_dt)
    NEW: spread_smoke(self.grid, update_dt)
    """
    
    # Handle both Grid object and list inputs for compatibility
    if hasattr(grid_data, 'neighbor_map'):
        # It's the Grid object (Optimized path)
        neighbor_map = grid_data.neighbor_map
        grid = grid_data.grid
        rows = grid_data.rows
        cols = grid_data.rows # assuming square
    else:
        # It's a list (Legacy slow path - fallback)
        from utils.utilities import get_neighbors
        grid = grid_data
        rows = len(grid)
        cols = len(grid[0])
        neighbor_map = None

    for r in range(rows):
        row_spots = grid[r]
        if neighbor_map:
            row_neighbors = neighbor_map[r]
            
        for c in range(cols):
            spot = row_spots[c]
            
            if neighbor_map:
                # Optimized: Use precomputed objects
                neighbor_smoke = [n.smoke for n in row_neighbors[c]]
            else:
                # Slow fallback
                neighbor_smoke = [grid[nr][nc].smoke for nr, nc in get_neighbors(r, c, rows, cols)]
            
            spot.update_smoke_level(neighbor_smoke, dt)
            
def draw_smoke(grid, surface):
    """
    Draw smoke. Optimized to minimize surface creation.
    """
    if not grid: return
    
    rows = len(grid)
    cols = len(grid[0])
    cell_width = grid[0][0].width
    
    # Pre-allocate one reusable surface
    smoke_surface = pygame.Surface((cell_width, cell_width), pygame.SRCALPHA)
    
    # Optimization: Cache method lookups
    fill_rect = smoke_surface.fill
    blit = surface.blit
    
    for r in range(rows):
        # Calculate Y once per row
        y_pos = r * cell_width
        row = grid[r]
        
        for c in range(cols):
            s = row[c].smoke
            if s > 0.05: # threshold slightly raised to skip invisible updates
                # Calculate color
                alpha = min(220, int(s * 280))
                gray = max(40, 150 - int(s * 100))
                
                # Fill and blit
                fill_rect((gray, gray, gray, alpha))
                blit(smoke_surface, (c * cell_width, y_pos))

# Remaining debug functions kept as is
def visualize_smoke_density(grid, rows):
    print("\n=== Smoke Density Visualization ===")
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
        print(row_str)

def clear_smoke(grid, rows):
    for r in range(rows):
        for c in range(rows):
            spot = grid.get_spot(r, c)
            if spot: spot.set_smoke(0.0)

def get_smoke_statistics(grid, rows):
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