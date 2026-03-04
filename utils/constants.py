from enum import Enum


class Dimensions(Enum):
    WIDTH = 780
    ROWS = 60
    TOOLS_WIDTH = 200


class Color(Enum):
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GREY = (200, 200, 200)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)
    ORANGE = (255, 165, 0)
    TURQUOISE = (64, 224, 208)
    CYAN = (150, 150, 255)
    BLUE = (0, 0, 255)
    FIRE_COLOR = (255, 80, 0)


class state_value(Enum):
    EMPTY = 0
    WALL = 1
    FIRE = 2
    START = 8
    END = 9


class smoke_constants(Enum):
    SMOKE_DIFFUSION = 0.03    # how much smoke spreads
    SMOKE_DECAY = 0.01       # smoke loss per step
    MAX_SMOKE = 1.0
    SMOKE_PRODUCTION = 0.25  # units per second


class fire_constants(Enum):
    AMBIENT_TEMP = 39.0       # °C
    DIFFUSION_RATE = 0.2       # heat spreading
    COOLING_RATE = 0.02        # loss to environment
    IGNITION_TEMP = 200.0
    BURN_TEMP = 600.0
    HEAT_TRANSFER = 0.15
    FIRE_SPREAD_PROBABILITY = 0.5 #10%


class material_id(Enum):
    AIR = 0
    WOOD = 1
    CONCRETE = 2
    METAL = 3
    FIRE = 4


class ToolType(Enum):
    MATERIAL = 1
    START = 8
    END = 9
    FIRE_SOURCE = 10
    STAIR = 11
    

class SimulationState(Enum):
    SIM_CONTINUE = 0
    SIM_EDITOR = 1
    SIM_QUIT = 2


class TempConstants:
    def __init__(self) -> None:
        self.AMBIENT_TEMP = fire_constants.AMBIENT_TEMP.value       # °C
        self.FIRE_SPREAD_PROBABILITY = fire_constants.FIRE_SPREAD_PROBABILITY.value #10%
        self.SMOKE_DIFFUSION = smoke_constants.SMOKE_DIFFUSION.value    # how much smoke spreads
        self.SMOKE_DECAY = smoke_constants.SMOKE_DECAY.value
        self.MAX_SMOKE = smoke_constants.MAX_SMOKE.value
        self.SMOKE_PRODUCTION = smoke_constants.SMOKE_PRODUCTION.value
        # Physical size of one grid cell (meters)
        self.CELL_SIZE_M = 0.5
        # Agent base walking speed multiplier (1.0 = research-paper speeds)
        self.BASE_SPEED_M_S = 1.0

        self.PARAMS = {
            "CELL_SIZE_M": {
                "label": "Cell Size (m)",
                "min": 0.05,
                "max": 2.0
            },
            "BASE_SPEED_M_S": {
                "label": "Agent Speed Multiplier",
                "min": 0.1,
                "max": 3.0
            },
            "FIRE_SPREAD_PROBABILITY": {
                "label": "Fire Spread Probability",
                "min": 0.0,
                "max": 1.0
            },
            "SMOKE_DIFFUSION": {
                "label": "Smoke Diffusion",
                "min": 0.0,
                "max": 0.5
            },
            "SMOKE_DECAY": {
                "label": "Smoke Decay",
                "min": 0.0,
                "max": 1.0
            },
            "SMOKE_PRODUCTION": {
                "label": "Smoke Production",
                "min": 0.0,
                "max": 1.0
            },
        }


temp = TempConstants()


def rTemp() -> TempConstants:
    """Get the global TempConstants instance."""
    return temp
