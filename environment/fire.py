import random
from utils.utilities import rTemp
from environment.materials import MATERIALS, material_id

def update_fire_with_materials(grid, dt=1.0):
    """
    Optimized fire update:
    - Uses precomputed neighbor objects (grid.neighbor_map)
    - Avoids generator overhead by iterating lists directly
    """
    rows = grid.rows
    grid_grid = grid.grid
    neighbor_map = grid.neighbor_map # Access the precomputed map
    new_fires = []
    temp = rTemp()
    
    # 1. Check for ignition / spread
    for r in range(rows):
        row_spots = grid_grid[r]
        row_neighbors = neighbor_map[r]
        
        for c in range(rows):
            spot = row_spots[c]
            
            # Fast fail checks
            if spot.is_fire() or spot.is_barrier() or spot.fuel <= 0:
                continue

            # Build neighbor data directly from object references
            # Format expected by Spot: (is_fire, temperature)
            neighbor_data = []
            neighbors = row_neighbors[c]
            
            # Manual unrolling or list comp is faster than generator here
            for n in neighbors:
                neighbor_data.append((n.is_fire(), n.temperature))

            if spot.update_fire_state(neighbor_data, temp, dt):
                new_fires.append(spot)

    # 2. Consume fuel (Iterate grid once)
    for row in grid_grid:
        for spot in row:
            if spot.is_fire():
                spot.consume_fuel_update(dt)

    return new_fires

def update_temperature_with_materials(grid, dt=1.0):
    """
    Optimized temperature update
    """
    rows = grid.rows
    grid_grid = grid.grid
    neighbor_map = grid.neighbor_map
    tempConst = rTemp()

    for r in range(rows):
        row_spots = grid_grid[r]
        row_neighbors = neighbor_map[r]
        
        for c in range(rows):
            spot = row_spots[c]
            # optimization: Barrier/Empty/Air usually doesn't need complex calculation 
            # if we wanted to be aggressive, but we stick to strict logic here.
            
            mat_props = spot.get_material_properties()
            spot_heat_transfer = mat_props["heat_transfer"]
            
            # Build neighbor list from cached objects
            # Format: (temperature, transfer_coefficient)
            neighbor_data = []
            for n in row_neighbors[c]:
                # Inlined logic for efficiency
                n_props = n.get_material_properties()
                coeff = spot_heat_transfer if spot_heat_transfer < n_props["heat_transfer"] else n_props["heat_transfer"]
                neighbor_data.append((n.temperature, coeff))

            spot.update_temperature(neighbor_data, tempConst, dt)

# Helper functions remain largely the same, just keeping them here for completeness
def randomfirespot(grid, ROWS, max_dist=30):
    attempts = 0
    max_attempts = 500
    u, v = -1, -1
    max_weight = 0.0

    while attempts < max_attempts:
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        weight = 0.0

        cell = grid.grid[r][c]
        if cell.is_empty() and is_valid_fire_start(grid, r, c, max_dist):
            # We can use neighbor map here too for speed
            for n in grid.neighbor_map[r][c]:
                weight += n.fuel
            weight /= 8.0
            if weight > max_weight:
                max_weight = weight
                u, v = r, c
        attempts += 1

    if u == -1:
        for r in range(1, ROWS - 1):
            for c in range(1, ROWS - 1):
                if grid.grid[r][c].is_empty() and is_valid_fire_start(grid, r, c, max_dist):
                    u, v = r, c
                    break
            if u != -1:
                break

    if u != -1 and grid.grid[u][v].fuel > 0:
        mat_enum = material_id(grid.grid[u][v].material)
        print(f"Placing fire on material: {MATERIALS[mat_enum]['name']} at ({u}, {v})")
        grid.fire_sources.add((u, v))
        return True

    for _ in range(100):
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        if grid.grid[r][c].is_empty() or is_valid_fire_start(grid, r, c, max_dist):
            grid.fire_sources.add((r, c))
            return True

    return False

def direction_blocked(grid, r, c, dr, dc, max_dist):
    rows = len(grid.grid)
    cols = len(grid.grid[0])
    for d in range(1, max_dist + 1):
        nr = r + dr * d
        nc = c + dc * d
        if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
            return False
        cell = grid.grid[nr][nc]
        if cell.is_barrier() or cell.is_end():
            return True
    return False

def is_valid_fire_start(grid, r, c, max_dist=30):
    if grid.grid[r][c].is_barrier() or grid.grid[r][c].is_start() or grid.grid[r][c].is_end():
        return False
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    for dr, dc in directions:
        if not direction_blocked(grid, r, c, dr, dc, max_dist):
            return False  
    return True