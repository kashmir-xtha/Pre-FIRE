import random
from core import grid
from utils.utilities import rTemp
from environment.materials import MATERIALS, material_id
import numpy as np

def do_temperature_update(grid, dt=1.0):
    rows = grid.rows
    temp = grid.temp_np

    grid.ensure_material_cache()
    heat_transfer = np.where(grid.is_barrier_np, 0.0, grid.heat_transfer_np)
    cooling_rate = grid.cooling_rate_np
    heat_capacity = grid.heat_capacity_np
    is_barrier = grid.is_barrier_np

    temp_pad = np.pad(temp, 1, mode="edge")
    ht_pad = np.pad(heat_transfer, 1, mode="edge")

    north = temp_pad[0:rows, 1:rows + 1]
    south = temp_pad[2:rows + 2, 1:rows + 1]
    west  = temp_pad[1:rows + 1, 0:rows]
    east  = temp_pad[1:rows + 1, 2:rows + 2]

    north_ht = ht_pad[0:rows, 1:rows + 1]
    south_ht = ht_pad[2:rows + 2, 1:rows + 1]
    west_ht  = ht_pad[1:rows + 1, 0:rows]
    east_ht  = ht_pad[1:rows + 1, 2:rows + 2]

    coeff_n = np.minimum(heat_transfer, north_ht)
    coeff_s = np.minimum(heat_transfer, south_ht)
    coeff_w = np.minimum(heat_transfer, west_ht)
    coeff_e = np.minimum(heat_transfer, east_ht)

    conduction_flux = (
        (north - temp) * coeff_n +
        (south - temp) * coeff_s +
        (west  - temp) * coeff_w +
        (east  - temp) * coeff_e
    )

    # Cooling sink term (Newton cooling)
    temp_constants = rTemp()
    ambient = temp_constants.AMBIENT_TEMP
    cooling_flux = -cooling_rate * (temp - ambient)

    # Net flux normalized by heat capacity
    net_flux = (conduction_flux + cooling_flux) / heat_capacity
    net_flux[is_barrier] = 0.0

    for r in range(rows):
        for c in range(rows):
            grid.grid[r][c].update_temperature_from_flux(
                heat_flux=net_flux[r, c],
                tempConstant=temp_constants,
                dt=dt
            )


def update_fire_with_materials(grid, dt=1.0):
    """
        Collects neighbor data and updates fire state for each cell, then consumes fuel for burning cells.
    """
    rows = grid.rows
    grid_grid = grid.grid
    new_fires = []
    temp_constants = rTemp()

    temp = np.empty((rows, rows), dtype=np.float32)
    fuel = np.empty((rows, rows), dtype=np.float32)
    is_fire = np.zeros((rows, rows), dtype=np.bool_)

    grid.ensure_material_cache()
    ignition_temp = grid.ignition_temp_np
    is_barrier = grid.is_barrier_np
    is_start = grid.is_start_np
    is_end = grid.is_end_np

    for r in range(rows):
        row_spots = grid_grid[r]
        for c in range(rows):
            spot = row_spots[c]
            temp[r, c] = spot.temperature
            fuel[r, c] = spot.fuel
            is_fire[r, c] = spot.is_fire()

    candidate = (~is_fire) & (~is_barrier) & (~is_start) & (~is_end) & (fuel > 0)

    fire_pad = np.pad(is_fire.astype(np.int8), 1, mode="constant")
    neighbor_fire = (
        fire_pad[0:rows, 0:rows] +
        fire_pad[0:rows, 1:rows + 1] +
        fire_pad[0:rows, 2:rows + 2] +
        fire_pad[1:rows + 1, 0:rows] +
        fire_pad[1:rows + 1, 2:rows + 2] +
        fire_pad[2:rows + 2, 0:rows] +
        fire_pad[2:rows + 2, 1:rows + 1] +
        fire_pad[2:rows + 2, 2:rows + 2]
    ) > 0

    auto_ignite = candidate & (temp >= ignition_temp)
    auto_rand = np.random.random((rows, rows)) < (0.3 * dt)
    auto_ignite &= auto_rand

    spread_prob = temp_constants.FIRE_SPREAD_PROBABILITY * dt
    spread_rand = np.random.random((rows, rows)) < spread_prob
    spread = candidate & neighbor_fire & spread_rand

    new_fire = auto_ignite | spread

    if np.any(new_fire):
        for r, c in np.argwhere(new_fire):
            spot = grid_grid[r][c]
            spot.set_on_fire()
            new_fires.append(spot)

    is_fire = is_fire | new_fire

    burn_rate = 0.1 * dt
    fuel_after = fuel.copy()
    fuel_after[is_fire] = np.maximum(fuel_after[is_fire] - burn_rate, 0.0)
    extinguish = is_fire & (fuel_after <= 0.0)

    if np.any(is_fire):
        for r, c in np.argwhere(is_fire):
            spot = grid_grid[r][c]
            new_fuel = float(fuel_after[r, c])
            if new_fuel < spot.fuel:
                spot.consume_fuel(spot.fuel - new_fuel)

    if np.any(extinguish):
        for r, c in np.argwhere(extinguish):
            grid_grid[r][c].extinguish_fire()
        is_fire[extinguish] = False

    grid.fuel_np = fuel_after
    grid.fire_np = is_fire

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

            mat_props = spot.get_material_properties()
            spot_heat_transfer = mat_props["heat_transfer"]
            
            # Format: (temperature, transfer_coefficient)
            neighbor_data = []
            for n in row_neighbors[c]:
                # Inlined logic for efficiency
                n_props = n.get_material_properties()
                coeff = spot_heat_transfer if spot_heat_transfer < n_props["heat_transfer"] else n_props["heat_transfer"]
                neighbor_data.append((n.temperature, coeff))

            spot.update_temperature(neighbor_data, tempConst, dt)

def collect_neighbor_data(grid, r, c):
    """
    Collects neighbor data for a given cell (r, c) using the precomputed neighbor map.
    Returns a list of tuples: (is_fire, temperature)
    """
    neighbor_data = []
    neighbors = grid.neighbor_map[r][c]
    
    for n in neighbors:
        neighbor_data.append((n.is_fire(), n.temperature))
    
    return neighbor_data

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