import logging
import random
from typing import List, Tuple, TYPE_CHECKING

import numpy as np
from environment.materials import MATERIALS, material_id
from utils.utilities import rTemp

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot

logger = logging.getLogger(__name__)

# Harmonic mean for edge conductivity (avoids overestimating flux)
def harmonic_mean(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    denom = a + b
    return np.where(denom > 0.0, 2.0 * a * b / denom, 0.0)

def do_temperature_update(grid: "Grid", dt: float = 1.0) -> None:
    rows = grid.rows
    temp = grid.temp_np

    grid.ensure_material_cache()
    # Treat heat_transfer as thermal conductivity k for Fourier's law
    heat_transfer = np.where(grid.is_barrier_np, 0.0, grid.heat_transfer_np)
    cooling_rate = grid.cooling_rate_np
    heat_capacity = grid.heat_capacity_np
    emmisivity = grid.emissivity_np
    is_barrier = grid.is_barrier_np

    temp_constants = rTemp()
    # Spatial step per cell (meters)
    dx = max(temp_constants.CELL_SIZE_M, 1e-6)

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

    k_n = harmonic_mean(heat_transfer, north_ht)
    k_s = harmonic_mean(heat_transfer, south_ht)
    k_w = harmonic_mean(heat_transfer, west_ht)
    k_e = harmonic_mean(heat_transfer, east_ht)

    # Fourier's law discretization: div(k grad T)
    conduction_flux = (
        (north - temp) * k_n +
        (south - temp) * k_s +
        (west - temp) * k_w +
        (east - temp) * k_e
    ) / (dx * dx)

    # In real fires, 40-60% of heat transfer is radiative.
    # q_rad = epsilon * sigma * (T_hot^4 - T_cold^4)
    # We linearize for stability: approximate as rad_coeff * (T_neighbor - T)
    # for high-temperature cells only (above 200°C), with coefficient scaling
    # as T^3 (from derivative of T^4).
    STEFAN_BOLTZMANN = 5.67e-8  # W/(m²·K⁴)
    # Effective radiative coefficient: ε·σ·T³ (linearized)
    # Convert °C to K for radiation calculation
    temp_K = temp + 273.15
    rad_coeff = emmisivity * STEFAN_BOLTZMANN * temp_K**3  # W/(m²·K)
    # Only apply radiation above ~200°C to avoid unnecessary computation on cool cells
    rad_mask = temp > 200.0
    rad_coeff = np.where(rad_mask, rad_coeff, 0.0)

    # Radiative flux from 4 cardinal neighbors (same stencil as conduction)
    radiation_flux = rad_coeff * (
        (north - temp) + (south - temp) + (west - temp) + (east - temp)
    ) / (dx * dx)

    # Cooling sink term (Newton cooling)
    ambient = temp_constants.AMBIENT_TEMP
    cooling_flux = -cooling_rate * (temp - ambient)

    # Net flux normalized by heat capacity
    net_flux = (conduction_flux + radiation_flux + cooling_flux) / heat_capacity
    net_flux[is_barrier] = 0.0

    for r in range(rows):
        for c in range(rows):
            grid.grid[r][c].update_temperature_from_flux(
                heat_flux=net_flux[r, c],
                tempConstant=temp_constants,
                dt=dt
            )


def update_fire_with_materials(grid: "Grid", dt: float = 1.0) -> List["Spot"]:
    """
    Collects neighbor data and updates fire state for each cell, then consumes fuel for burning cells.
    Optimized version with combined fuel consumption/extinguishment loop.
    """
    rows = grid.rows
    grid_grid = grid.grid
    new_fires = []
    temp_constants = rTemp()

    # Cache current state into arrays
    temp = np.empty((rows, rows), dtype=np.float32)
    fuel = np.empty((rows, rows), dtype=np.float32)
    is_fire = np.zeros((rows, rows), dtype=np.bool_)
    burned = np.zeros((rows, rows), dtype=np.bool_)

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
            burned[r, c] = spot.burned

    # Cell-size scaling: sliders were tuned at REFERENCE_CELL_SIZE_M.
    # Larger cells represent more physical material between grid centres, so fire takes longer to cross each cell — both spread probability and burn
    # rate scale linearly with (reference / dx) i.e Time for fire to cross cell ∝ distance
    REFERENCE_CELL_SIZE_M = 0.5
    dx = max(temp_constants.CELL_SIZE_M, 1e-6)
    cell_scale = REFERENCE_CELL_SIZE_M / dx   # <1 for large cells, >1 for small

    # Candidate cells that can ignite
    candidate = (
        (~is_fire) &
        (~is_barrier) &
        (~is_start) &
        (~is_end) &
        (fuel > 0) &
        (~burned)
    )

    # Auto‑ignition (temperature + random chance)
    # Also scaled: a larger cell takes proportionally longer to auto-ignite
    auto_ignite = candidate & (temp >= ignition_temp)
    auto_rand = np.random.random((rows, rows)) < (0.3 * cell_scale * dt)
    auto_ignite &= auto_rand

    # Spread from burning neighbors
    # Probability scales with the FIRE CELL's temperature (source intensity).
    # A hotter fire radiates more energy → higher chance of igniting neighbors.
    # P = base_prob * clamp(T_fire / 600, 0.2, 1.0)
    spread_mask = np.zeros_like(candidate, dtype=bool)
    base_prob = temp_constants.FIRE_SPREAD_PROBABILITY * cell_scale * dt
    
    # Get fire cell coordinates
    fire_cells = np.argwhere(is_fire)
    for r, c in fire_cells:
        # Source fire intensity factor
        fire_intensity = min(max(temp[r, c] / 600.0, 0.2), 1.0)
        prob = base_prob * fire_intensity
 
        # Check all 8 neighbors.
        # Diagonal neighbours are √2 further away than cardinal neighbours,
        # so their spread probability is scaled by 1/√2 to keep fire
        # propagation speed isotropic across all directions.
        # This mirrors the diag_factor already applied in smoke diffusion.
        DIAG_FACTOR = 0.7071067811865476  # 1 / sqrt(2)
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue  # Skip self
 
                nr, nc = r + dr, c + dc
 
                # Check bounds
                if not (0 <= nr < rows and 0 <= nc < rows):
                    continue
 
                # Reduce probability for diagonal neighbours
                effective_prob = prob * DIAG_FACTOR if (dr != 0 and dc != 0) else prob
 
                if candidate[nr, nc] and np.random.random() < effective_prob:
                    spread_mask[nr, nc] = True
    
    spread = spread_mask

    new_fire_mask = auto_ignite | spread

    # Apply new fires (must loop to call set_on_fire)
    if np.any(new_fire_mask):
        for r, c in np.argwhere(new_fire_mask):
            spot = grid_grid[r][c]
            spot.set_on_fire()
            new_fires.append(spot)

    # Update is_fire array
    is_fire = is_fire | new_fire_mask

    # Burn rate scales with cell size: a larger cell holds proportionally more fuel so it burns for longer before extinguishing.
    #  Combined fuel consumption and extinguishment loop 
    fuel_after = fuel.copy()
    dirty = False

    # Burn rate now comes from each cell's material properties instead of a single hardcoded constant.  Fall back to 0.02 for materials that don't define fuel_burn_rate.
    fire_indices = np.argwhere(is_fire)
    for r, c in fire_indices:
        spot = grid_grid[r][c]
        props = spot.get_material_properties()
        mat_burn_rate = props.get("fuel_burn_rate", 0.02) * cell_scale * dt

        new_fuel = max(fuel_after[r, c] - mat_burn_rate, 0.0)
        fuel_after[r, c] = new_fuel

        spot = grid_grid[r][c]
        # Only call consume_fuel if fuel actually decreased
        if new_fuel < spot.fuel:
            spot.consume_fuel(spot.fuel - new_fuel)

        # Check for extinguishment
        if new_fuel <= 0.0:
            props = spot.get_material_properties()
            if props.get("ash_on_burnout", False): #false is the default
                spot._material = material_id.ASH #set to ash if valid material else returns false and sets to air like before
            else:
                spot._material = material_id.AIR # Convert burned-out cell to inert AIR without refueling
            spot._fuel = 0.0
            spot.material_props = None  # invalidate cached props
            spot.extinguish_fire()
            dirty = True
            is_fire[r, c] = False # Mark this cell as not fire in the array (for grid.fire_np later)

    if dirty:
        grid.mark_material_cache_dirty()

    # Update grid‑level arrays
    grid.fuel_np = fuel_after
    grid.fire_np = is_fire

    return new_fires

def update_temperature_with_materials(grid: "Grid", dt: float = 1.0) -> None:
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

def collect_neighbor_data(grid: "Grid", r: int, c: int) -> List[Tuple[bool, float]]:
    """
    Collects neighbor data for a given cell (r, c) using the precomputed neighbor map.
    Returns a list of tuples: (is_fire, temperature)
    """
    neighbor_data = []
    neighbors = grid.neighbor_map[r][c]
    
    for n in neighbors:
        neighbor_data.append((n.is_fire(), n.temperature))
    
    return neighbor_data

def randomfirespot(grid: "Grid", ROWS: int, max_dist: int = 30) -> bool:
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
        logger.debug(
            "Placing fire on material: %s at (%s, %s)",
            MATERIALS[mat_enum]["name"],
            u,
            v,
        )
        grid.fire_sources.add((u, v))
        return True

    for _ in range(100):
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        if grid.grid[r][c].is_empty() or is_valid_fire_start(grid, r, c, max_dist):
            grid.fire_sources.add((r, c))
            return True

    return False

def direction_blocked(
    grid: "Grid",
    r: int,
    c: int,
    dr: int,
    dc: int,
    max_dist: int,
) -> bool:
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

def is_valid_fire_start(grid: "Grid", r: int, c: int, max_dist: int = 30) -> bool:
    if grid.grid[r][c].is_barrier() or grid.grid[r][c].is_start() or grid.grid[r][c].is_end():
        return False
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    for dr, dc in directions:
        if not direction_blocked(grid, r, c, dr, dc, max_dist):
            return False  
    return True

ACTIVATION_TEMP  = 68.0   # °C — standard commercial glass-bulb sprinkler
EFFECT_RADIUS   = 2.3     # m suppressed in each direction (approx NFPA 13 standard for 12m² coverage per sprinkler)
COOLING_RATE_SPRINKLER  = 80.0   # °C removed per second from each cell in radius
SMOKE_CLEAR_RATE = 0.3    # smoke units cleared per second in radius

def update_sprinklers(grid: "Grid", dt: float) -> None:
    """Activate sprinklers and apply suppression effects each timestep."""
    cfg = rTemp()
    cell_size_m = max(cfg.CELL_SIZE_M, 1e-6)
    effect_radius = max(1, round(EFFECT_RADIUS / cell_size_m))  # ← now resolves correctly
    rows = grid.rows

    for r in range(rows):
        for c in range(rows):
            spot = grid.grid[r][c]
            if not spot.is_sprinkler():
                continue

            if spot.temperature >= ACTIVATION_TEMP:
                spot.activate_sprinkler()

            if not spot.is_sprinkler_active():
                continue

            # Use effect_radius (int) not EFFECT_RADIUS_M (float)
            r_min = max(0, r - effect_radius)
            r_max = min(rows, r + effect_radius + 1)
            c_min = max(0, c - effect_radius)
            c_max = min(rows, c + effect_radius + 1)

            for nr in range(r_min, r_max):
                for nc in range(c_min, c_max):
                    # Circular boundary check
                    dist_m = ((nr - r)**2 + (nc - c)**2) ** 0.5 * cell_size_m
                    if dist_m > EFFECT_RADIUS:
                        continue
                    if not _has_line_of_sight(grid, r, c, nr, nc):
                        continue
                    target = grid.grid[nr][nc]
                    if target.is_barrier():
                        continue

                    if target.is_fire():
                        target.extinguish_fire()
                        grid.fire_np[nr, nc] = False

                    cooling = COOLING_RATE_SPRINKLER * dt
                    new_temp = max(25.0, target.temperature - cooling)
                    target._temperature = new_temp
                    grid.temp_np[nr, nc] = new_temp

                    clearing = SMOKE_CLEAR_RATE * dt
                    new_smoke = max(0.0, target.smoke - clearing)
                    target._smoke = new_smoke
                    grid.smoke_np[nr, nc] = new_smoke
    
def _has_line_of_sight(grid: "Grid", r1: int, c1: int, r2: int, c2: int) -> bool:
    """Bresenham line walk — returns False if any barrier lies between (r1,c1) and (r2,c2)."""
    dr = abs(r2 - r1)
    dc = abs(c2 - c1)
    r, c = r1, c1
    sr = 1 if r2 > r1 else -1
    sc = 1 if c2 > c1 else -1
    err = dr - dc

    while True:
        if r == r2 and c == c2:
            return True
        # Don't check the own cell or the target cell
        if (r != r1 or c != c1) and (r != r2 or c != c2):
            if grid.is_barrier_np[r, c]:
                return False
        e2 = 2 * err
        if e2 > -dc:
            err -= dc
            r += sr
        if e2 < dr:
            err += dr
            c += sc