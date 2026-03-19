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
    PINK = (255, 51, 255)


class state_value(Enum):
    EMPTY = 0
    WALL = 1
    FIRE = 2
    START = 8
    END = 9
    SPRINKLER = 12


class smoke_constants(Enum):
    SMOKE_DIFFUSION = 0.02    # how much smoke spreads
    SMOKE_DECAY = 0.1       # smoke loss per step
    MAX_SMOKE = 1.0
    SMOKE_PRODUCTION = 0.25  # units per second


class fire_constants(Enum):
    AMBIENT_TEMP = 25.0       # °C room temperature
    DIFFUSION_RATE = 0.2       # heat spreading
    COOLING_RATE = 0.02        # loss to environment
    IGNITION_TEMP = 200.0
    BURN_TEMP = 600.0
    HEAT_TRANSFER = 0.15
    FIRE_SPREAD_PROBABILITY = 0.3 #10%


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
    SPRINKLER = 12
    

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
        self.NUM_FLOORS = 1

        self.PARAMS = {
            "NUM_FLOORS": {
                "label": "Floor Count",
                "min": 1,
                "max": 10
            },
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

class VulnerabilityProfile(Enum):
    # Physical constants
    # FED toxic: agent is incapacitated when fed_toxic >= 1.0
    # Fractional dose per second at smoke = 1.0 (calibrated so heavy continuous
    # smoke incapacitates in ~3 minutes, matching empirical corridor evacuation data).
    FED_TOXIC_RATE_PER_SMOKE    = 1.0 / 180.0   # dose/s at smoke = 1.0

    # FED thermal: agent is incapacitated when fed_thermal >= 1.0
    # Above 60 °C convective heat causes pain in ~4 min; above 120 °C in < 30 s.
    # We model this as an exponential: rate = exp((T - T_thresh) / T_scale) / T_ref
    FED_THERMAL_THRESH_C        = 60.0           # °C — onset of thermal stress
    FED_THERMAL_SCALE_C         = 30.0           # °C — e-folding scale
    FED_THERMAL_REF_S           = 240.0          # s — time to incapacitate at threshold

    # Non-monotonic temperature–speed curve
    # Speed peaks at TEMP_BOOST_THRESHOLD, then falls.
    TEMP_BOOST_THRESHOLD_C      = 60.0           # °C — speed maximum
    TEMP_SPEED_DROP_SCALE_C     = 40.0           # °C — e-folding for drop above threshold
    SPEED_BOOST_FACTOR          = 1.35           # peak multiplier vs normal (panic effect)
    SPEED_FLOOR_FACTOR          = 0.20           # minimum fraction of normal speed

    # Stress accumulation
    STRESS_SMOKE_WEIGHT         = 0.6            # contribution per unit smoke
    STRESS_HEAT_WEIGHT          = 0.004          # contribution per °C above threshold
    STRESS_FIRE_PROXIMITY_WEIGHT= 0.25           # contribution per nearby fire cell
    STRESS_DECAY_RATE           = 0.05           # stress lost per second in safe area
    STRESS_IMPAIR_THRESHOLD     = 0.70           # above this, cognition is impaired
    STRESS_MAX                  = 1.0

    # Fire proximity avoidance
    FIRE_AVOIDANCE_RADIUS_CELLS = 3              # cells at which repulsion begins
    FIRE_AVOIDANCE_PEAK_FORCE   = 2.0            # extra path cost per adjacent fire cell

    # Vulnerability profiles  {name: (fed_scale, speed_scale)}
    # fed_scale  > 1 → accumulates dose faster (more vulnerable)
    # speed_scale < 1 → slower base walking speed
    VULNERABILITY_PROFILES = {
        "adult_fit":     (1.0,  1.0),
        "adult_average": (1.15, 0.90),
        "elderly":       (1.50, 0.65),
        "child":         (1.30, 0.75),
        "injured":       (1.80, 0.50),
    }
