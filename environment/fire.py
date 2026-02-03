import random
from utils.utilities import get_neighbors, rTemp
from environment.materials import MATERIALS, material_id

def update_fire_with_materials(grid, dt=1.0):
    """Update fire spread using Spot's update methods (optimized)

    - Use local variable lookups to reduce attribute access cost
    - Avoid building temporary neighbor lists by passing a generator
    """
    rows = grid.rows
    grid_grid = grid.grid
    new_fires = []
    temp = rTemp()
    get_n = get_neighbors

    # First pass: check for new fires
    for r in range(rows):
        row_grid = grid_grid[r]
        for c in range(rows):
            spot = row_grid[c]
            if not spot or spot.is_fire():
                continue

            # Pass a generator instead of building a list (saves allocations)
            neighbor_iter = ((grid_grid[nr][nc].is_fire(), grid_grid[nr][nc].temperature)
                             for nr, nc in get_n(r, c, rows, rows))

            if spot.update_fire_state(neighbor_iter, temp, dt):
                new_fires.append(spot)

    # Second pass: update fuel consumption for existing fires
    for row in grid_grid:
        for spot in row:
            if spot.is_fire():
                spot.consume_fuel_update(dt)

    return new_fires

def update_temperature_with_materials(grid, dt=1.0):
    """Update temperature using Spot's update methods (optimized)

    - Use local lookups
    - Avoid redundant bounds checks
    - Pass generator to Spot.update_temperature to avoid list allocation
    """
    rows = grid.rows
    grid_grid = grid.grid
    tempConst = rTemp()
    get_n = get_neighbors

    for r in range(rows):
        row_grid = grid_grid[r]
        for c in range(rows):
            spot = row_grid[c]
            if not spot:
                continue

            mat_props = spot.get_material_properties()

            # Build a generator to avoid allocating a list for neighbors
            neighbor_iter = ((grid_grid[nr][nc].temperature,
                              min(mat_props["heat_transfer"], grid_grid[nr][nc].get_material_properties()["heat_transfer"]))
                             for nr, nc in get_n(r, c, rows, rows))

            spot.update_temperature(neighbor_iter, tempConst, dt)

def randomfirespot(grid, ROWS, max_dist=30):
    """Place fire on a flammable material - try multiple times if needed (with small bugfix)

    - Keep the random sampling strategy but ensure we report the chosen location correctly
    - Fallback to a single pass to find any flammable empty spot if sampling found nothing
    """
    attempts = 0
    max_attempts = 500

    u, v = -1, -1
    max_weight = 0.0

    while attempts < max_attempts:
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        weight = 0.0

        # Check if cell is empty and has fuel
        cell = grid.grid[r][c]
        if cell.is_empty() and is_valid_fire_start(grid, r, c, max_dist):
            for nr, nc in get_neighbors(r, c, ROWS, ROWS):
                weight += grid.grid[nr][nc].fuel
            weight /= 8.0
            if weight > max_weight:
                max_weight = weight
                u, v = r, c
        attempts += 1

    # If sampling didn't find a weighted location, do one quick pass for any empty flammable spot
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

    # If no flammable material found, try to set fire on any empty or valid cell
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