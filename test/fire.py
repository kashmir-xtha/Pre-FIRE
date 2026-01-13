import random
from utilities import state_value, get_neighbors, fire_constants

def update_fire(grid, fire_prob=0.3):
    """
    grid: 2D list or numpy array of cell values
    fire_prob: probability of fire spread
    """
    rows = len(grid)
    cols = len(grid[0])

    new_grid = [row[:] for row in grid]

    for r in range(rows):
        for c in range(cols):
            # Fire can only spread to EMPTY cells
            if grid[r][c] == state_value.EMPTY.value:
                for nr, nc in get_neighbors(r, c, rows, cols):
                    if grid[nr][nc] == state_value.FIRE.value:
                        if random.random() < fire_prob:
                            new_grid[r][c] = state_value.FIRE.value
                            break

    return new_grid

def randomfirespot(grid, ROWS):
    for _ in range(100):  # Try 100 times to find empty spot
        r = random.randint(0, ROWS-1)
        c = random.randint(0, ROWS-1)
        if grid.state[r][c] == state_value.EMPTY.value:
            grid.state[r][c] = state_value.FIRE.value
            return True
    return False

def update_temperature(state, temperature, rows, cols):
    new_temp = [[temperature[r][c] for c in range(cols)] for r in range(rows)]

    for r in range(rows):
        for c in range(cols):

            # Fire cell = constant heat source
            if state[r][c] == state_value.FIRE.value:
                new_temp[r][c] = fire_constants.FIRE_TEMP.value
                continue

            # Neighbor diffusion
            total = 0
            count = 0
            for nr, nc in get_neighbors(r, c, rows, cols):
                total += temperature[nr][nc]
                count += 1

            if count > 0:
                avg = total / count
                new_temp[r][c] += fire_constants.DIFFUSION_RATE.value * (avg - temperature[r][c])

            # Cooling to ambient
            new_temp[r][c] += fire_constants.COOLING_RATE.value * (fire_constants.AMBIENT_TEMP.value - new_temp[r][c])

    return new_temp
