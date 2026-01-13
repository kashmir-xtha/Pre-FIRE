from enum import Enum

class Color(Enum):
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GREY = (200, 200, 200)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)
    ORANGE = (255, 165, 0)
    TURQUOISE = (64, 224, 208)
    PURPLE = (128, 0, 128)
    BLUE = (0, 0, 255)
    FIRE_COLOR = (255, 80, 0)

class state_value(Enum):
    EMPTY = 0
    WALL = 1
    FIRE = 2
    START = 8
    END = 9

class smoke_constants(Enum):
    SMOKE_DIFFUSION = 1    # how much smoke spreads
    SMOKE_DECAY = 0.001       # smoke loss per step
    MAX_SMOKE = 1.0

class fire_constants(Enum):
    AMBIENT_TEMP = 20.0        # °C
    FIRE_TEMP = 600.0          # °C at fire source
    DIFFUSION_RATE = 0.2       # heat spreading
    COOLING_RATE = 0.02        # loss to environment

def get_neighbors(r, c, rows, cols):
    # Moore neighborhood
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0: # Skip the current cell
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                yield nr, nc