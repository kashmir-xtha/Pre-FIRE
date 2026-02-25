from utils.utilities import material_id, state_value    

EMPTY = state_value.EMPTY.value
WALL = state_value.WALL.value

MATERIALS = {
    material_id.AIR: {
        "name": "Air",
        "color": (255, 255, 255),
        "fuel": 1.0,
        "ignition_temp": float("inf"),
        "cooling_rate": 0.01,  # Increased cooling rate
        "heat_transfer": 0.5,  # Reduced heat transfer (treated as k)
        "density": 1.2,        # kg/m^3
        "specific_heat": 1005.0,  # J/(kg*K)
        "default_state": EMPTY  # EMPTY
    },
    material_id.WOOD: {
        "name": "Wood",
        "color": (139, 69, 19),
        "fuel": 5.0,
        "ignition_temp": 250.0,  # Reduced ignition temperature
        "cooling_rate": 0.02,   # Slower cooling
        "heat_transfer": 0.9,   # Lower heat transfer (treated as k)
        "density": 600.0,       # kg/m^3
        "specific_heat": 1700.0,  # J/(kg*K)
        "default_state": EMPTY  # EMPTY
    },
    material_id.CONCRETE: {
        "name": "Wall",
        "color": (0, 0, 0),
        "fuel": 0.0,
        "ignition_temp": float("1500"),  # Very high ignition temp
        "cooling_rate": 0,    # Very slow cooling
        "heat_transfer": 0,    # Better heat conductor than wood
        "density": 2300.0,     # kg/m^3
        "specific_heat": 880.0,  # J/(kg*K)
        "default_state": WALL  # WALL
    },
    material_id.METAL: {
        "name": "Metal",
        "color": (120, 120, 150),
        "fuel": 0.0,
        "ignition_temp": 1500,  # Very high ignition temp
        "cooling_rate": 0.05,     # Fast cooling (metal dissipates heat well)
        "heat_transfer": 0.50,     # Excellent heat conductor
        "density": 7800.0,         # kg/m^3
        "specific_heat": 500.0,    # J/(kg*K)
        "default_state": EMPTY  # EMPTY
    }
}