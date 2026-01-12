# firespread.py - Fixed to match smokespread constants
import random

# Cell values - MUST MATCH smokespread.py
EMPTY = 0
WALL = 1
FIRE = 2
START = 8    # Different from FIRE
END = 9      # Different from FIRE

def get_neighbors(r, c, rows, cols):
    for dr, dc in [(1,0), (-1,0), (0,1), (0,-1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            yield nr, nc

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
            if grid[r][c] == EMPTY:
                for nr, nc in get_neighbors(r, c, rows, cols):
                    if grid[nr][nc] == FIRE:
                        if random.random() < fire_prob:
                            new_grid[r][c] = FIRE
                            break

    return new_grid

def randomfirespot(grid, ROWS):
    for _ in range(100):  # Try 100 times to find empty spot
        r = random.randint(0, ROWS-1)
        c = random.randint(0, ROWS-1)
        if grid.state[r][c] == EMPTY:
            grid.state[r][c] = FIRE
            return True
            break
    return False