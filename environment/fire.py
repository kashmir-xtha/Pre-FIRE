import random
from utils.utilities import get_neighbors, rTemp
from environment.materials import MATERIALS, material_id

def update_fire_with_materials(grid, dt=1.0):
    """Update fire spread using Spot's update methods"""
    rows = grid.rows
    new_fires = []
    
    # First pass: check for new fires
    for r in range(rows):
        for c in range(rows):
            spot = grid.get_spot(r, c)
            if not spot or spot.is_fire():
                continue
            
            # Collect neighbor fire information
            neighbor_fire_states = []
            for nr, nc in get_neighbors(r, c, rows, rows):
                neighbor = grid.get_spot(nr, nc)
                if neighbor:
                    neighbor_fire_states.append((neighbor.is_fire(), neighbor.temperature))
            
            # Let spot decide if it catches fire
            temp = rTemp()
            if spot.update_fire_state(neighbor_fire_states, temp, dt):
                new_fires.append(spot)
    
    # Second pass: update fuel consumption for existing fires
    for r in range(rows):
        for c in range(rows):
            spot = grid.get_spot(r, c)
            if spot and spot.is_fire():
                spot.consume_fuel_update(dt)
    
    return new_fires

def update_temperature_with_materials(grid, dt=1.0):
    """Update temperature using Spot's update methods"""
    rows = grid.rows
    
    for r in range(rows):
        for c in range(rows):
            spot = grid.get_spot(r, c)
            if not spot:
                continue
            
            # Collect neighbor temperature data
            neighbor_data = []
            for nr, nc in get_neighbors(r, c, rows, rows):
                if 0 <= nr < rows and 0 <= nc < rows:
                    neighbor = grid.get_spot(nr, nc)
                    if neighbor:
                        # Calculate heat transfer coefficient
                        mat_props = spot.get_material_properties()
                        neighbor_props = neighbor.get_material_properties()
                        transfer_coeff = min(mat_props["heat_transfer"], 
                                           neighbor_props["heat_transfer"])
                        neighbor_data.append((neighbor.temperature, transfer_coeff))
            
            # Update temperature
            tempConst = rTemp()
            spot.update_temperature(neighbor_data, tempConst, dt)

def randomfirespot(grid, ROWS, max_dist=30):
    """Place fire on a flammable material - try multiple times if needed"""
    attempts = 0
    max_attempts = 500  # Increased attempts
    
    u, v = 0, 0
    max_weight = 0

    while attempts < max_attempts:
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        weight = 0
        # Check if cell is empty and has fuel
        if grid.grid[r][c].is_empty() and is_valid_fire_start(grid, r, c, max_dist):
            for nr, nc in get_neighbors(r, c, ROWS, ROWS):
                weight += grid.grid[nr][nc].fuel
            weight /= 8
            if weight > max_weight:
                max_weight = weight
                u, v = r, c
            
        attempts += 1
    material = material_id(grid.grid[r][c].material)
    if grid.grid[u][v].fuel > 0:
        print(f"Placing fire on material: {MATERIALS[material]['name']} at ({r}, {c})")
        grid.fire_sources.add((u, v))
        return True
    
    # If no flammable material found, try to set fire on any empty cell
    for _ in range(100):
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        if is_valid_fire_start(grid, r, c, max_dist):
            print("No flammable material found, forcing fire on non-flammable material")

        if grid.grid[r][c].is_empty() or is_valid_fire_start(grid, r, c, max_dist):
            grid.fire_sources.add((r, c))
            print("Forced fire on non-flammable material")
            return True
    
    return False

def direction_blocked(grid, r, c, dr, dc, max_dist):
    rows = len(grid.grid)
    cols = len(grid.grid[0])

    for d in range(1, max_dist + 1):
        nr = r + dr * d
        nc = c + dc * d

        # Escaped the building
        if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
            return False

        cell = grid.grid[nr][nc]

        if cell.is_barrier():
            return True

        if cell.is_end():
            return True

        # EMPTY → keep looking

    # Nothing stopped us within max_dist
    return False

def is_valid_fire_start(grid, r, c, max_dist=30):
    if grid.grid[r][c].is_barrier() or grid.grid[r][c].is_start() or grid.grid[r][c].is_end():
        return False

    directions = [
        (1, 0),   # down
        (-1, 0),  # up
        (0, 1),   # right
        (0, -1)   # left
    ]

    for dr, dc in directions:
        if not direction_blocked(grid, r, c, dr, dc, max_dist):
            return False  # one open direction ruins it
        
    return True