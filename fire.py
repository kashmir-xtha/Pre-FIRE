# In fire.py - replace with proper material-aware fire system
import random
from utilities import material_id, state_value, fire_constants, get_neighbors
from materials import MATERIALS

def update_fire_with_materials(grid, dt=1.0):
    """Update fire spread considering material properties"""
    rows = grid.rows
    new_state = [row[:] for row in grid.state]
    
    for r in range(rows):
        for c in range(rows):
            # Get current cell properties
            current_state = grid.state[r][c]
            material = material_id(grid.material[r][c])
            fuel = grid.fuel[r][c]
            temp = grid.temperature[r][c]
            
            # If cell is already on fire
            if current_state == state_value.FIRE.value:
                if fuel > 0:
                    # Consume fuel faster
                    fuel_consumption = 0.1 * dt  # Increased from 0.02
                    grid.fuel[r][c] = max(0, fuel - fuel_consumption)
                    
                    # Generate heat - fire should keep temperature high
                    grid.temperature[r][c] = max(grid.temperature[r][c], 400.0)  # Fire maintains at least 400°C
                    grid.temperature[r][c] = min(1000.0, grid.temperature[r][c] + 100 * dt)
                    
                    # Spread fire to neighbors
                    for nr, nc in get_neighbors(r, c, rows, rows):
                        neighbor_state = grid.state[nr][nc]
                        neighbor_material = material_id(grid.material[nr][nc])
                        neighbor_fuel = grid.fuel[nr][nc]
                        
                        # Skip if neighbor is wall, start, end, or already on fire
                        if (neighbor_state in [state_value.WALL.value, state_value.START.value, 
                                                state_value.END.value, state_value.FIRE.value]):
                            continue
                        
                        # Check if neighbor can catch fire
                        if neighbor_fuel > 0:
                            # Calculate ignition probability based on material
                            mat_props = MATERIALS[neighbor_material]
                            ignition_temp = mat_props["ignition_temp"]
                            
                            # Temperature-based ignition
                            if grid.temperature[nr][nc] >= ignition_temp:
                                new_state[nr][nc] = state_value.FIRE.value
                                print("Temperature based change in state")
                                # Initialize temperature for new fire
                                grid.temperature[nr][nc] = 400.0
                            # Direct flame contact - increased probability
                            elif random.random() < fire_constants.FIRE_SPREAD_PROBABILITY.value * dt:  # 50% chance per second from direct contact
                                new_state[nr][nc] = state_value.FIRE.value
                                grid.temperature[nr][nc] = 400.0
                                #print("Chance based direct contact")
                
                # If fuel runs out, extinguish fire
                if fuel <= 0:
                    new_state[r][c] = state_value.EMPTY.value
                    # Don't reset temperature immediately - let it cool down naturally
            
            # If cell is not on fire but has fuel and is hot enough
            elif current_state == state_value.EMPTY.value and fuel > 0:
                # Check for auto-ignition from high temperature
                mat_props = MATERIALS[material]
                ignition_temp = mat_props["ignition_temp"]
                
                if temp >= ignition_temp and random.random() < 0.3 * dt:
                    new_state[r][c] = state_value.FIRE.value
                    grid.temperature[r][c] = 400.0  # Initialize fire temperature
                    print("Auto-ignition due to high temperature")
    
    grid.state = new_state
    return new_state

def update_temperature_with_materials(grid, dt=1.0):
    """Update temperature considering material heat transfer properties"""
    rows = grid.rows
    new_temp = [row[:] for row in grid.temperature]
    
    for r in range(rows):
        for c in range(rows):
            current_temp = grid.temperature[r][c]
            material = material_id(grid.material[r][c])
            mat_props = MATERIALS[material]
            current_state = grid.state[r][c]
            
            # Skip walls, start, end (they don't transfer heat much)
            if current_state in [state_value.WALL.value, state_value.START.value, state_value.END.value]:
                # These materials slowly cool to ambient
                cooling = mat_props["cooling_rate"] * (current_temp - fire_constants.AMBIENT_TEMP.value) * dt
                new_temp[r][c] = current_temp - cooling
                continue
            
            # Heat diffusion from neighbors - use Von Neumann neighborhood (4-directional)
            heat_sum = 0
            neighbor_count = 0
            
            # Only check 4 directions for more realistic heat transfer
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < rows:
                    # Don't transfer heat through walls
                    if grid.state[nr][nc] == state_value.WALL.value:
                        continue
                    
                    # Neighbor's material affects heat transfer
                    neighbor_material = material_id(grid.material[nr][nc])
                    neighbor_props = MATERIALS[neighbor_material]
                    
                    # Heat transfer coefficient - use the lower of the two materials
                    transfer_coeff = min(mat_props["heat_transfer"], neighbor_props["heat_transfer"])
                    
                    # Temperature difference drives heat flow
                    temp_diff = grid.temperature[nr][nc] - current_temp
                    heat_flow = temp_diff * transfer_coeff * dt
                    heat_sum += heat_flow
                    neighbor_count += 1
            
            # Calculate temperature change
            if neighbor_count > 0:
                heat_transfer = heat_sum
            else:
                heat_transfer = 0
            
            # Cooling toward ambient - faster for hotter objects
            cooling = mat_props["cooling_rate"] * (current_temp - fire_constants.AMBIENT_TEMP.value) * dt
            
            # If cell is on fire, add significant heat
            heating = 0
            if current_state == state_value.FIRE.value:
                heating = 150 * dt  # Increased heating from fire
            
            new_temp[r][c] = current_temp + heat_transfer - cooling + heating
            
            # Clamp temperature to realistic ranges
            new_temp[r][c] = max(fire_constants.AMBIENT_TEMP.value, min(1200.0, new_temp[r][c]))
    
    grid.temperature = new_temp
    return new_temp

def randomfirespot(grid, ROWS, max_dist=30):
    """Place fire on a flammable material - try multiple times if needed"""
    attempts = 0
    max_attempts = 500  # Increased attempts
    
    while attempts < max_attempts:
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        
        # Check if cell is empty and has fuel
        if grid.state[r][c] == state_value.EMPTY.value:
            material = material_id(grid.material[r][c])
            if MATERIALS[material]["fuel"] > 0:
                grid.state[r][c] = state_value.FIRE.value
                # Set initial fire temperature
                grid.temperature[r][c] = 600.0
                # Ensure fuel is initialized
                grid.fuel[r][c] = MATERIALS[material]["fuel"]
                return True
        
        attempts += 1
    
    # If no flammable material found, try to set fire on any empty cell
    for _ in range(100):
        r = random.randint(1, ROWS - 2)
        c = random.randint(1, ROWS - 2)
        
        if grid.state[r][c] == state_value.EMPTY.value:
            grid.state[r][c] = state_value.FIRE.value
            grid.temperature[r][c] = 600.0
            # Set it to wood so it has fuel
            grid.material[r][c] = material_id.WOOD.value
            grid.fuel[r][c] = MATERIALS[material_id.WOOD]["fuel"]
            return True
    
    return False

def direction_blocked(grid, r, c, dr, dc, max_dist):
    rows = len(grid.state)
    cols = len(grid.state[0])

    for d in range(1, max_dist + 1):
        nr = r + dr * d
        nc = c + dc * d

        # Escaped the building
        if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
            return False

        cell = grid.state[nr][nc]

        if cell == state_value.WALL.value:
            return True

        if cell == state_value.END.value:
            return True

        # EMPTY → keep looking

    # Nothing stopped us within max_dist
    return False

def is_valid_fire_start(grid, r, c, max_dist=30):
    if grid.state[r][c] != state_value.EMPTY.value:
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