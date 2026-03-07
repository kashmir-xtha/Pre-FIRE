from utils.utilities import material_id, state_value    

EMPTY = state_value.EMPTY.value
WALL = state_value.WALL.value

MATERIALS = {
    material_id.AIR: {
        "name": "Air",
        "color": (255, 255, 255),
        "fuel": 1.0,
        "ignition_temp": float("inf"),
        "cooling_rate": 10.0,           # W/(m²·K) — convective loss coefficient for air 10-25 W/(m²·K)
        "heat_transfer": 0.026,        # W/(m·K) — real air conductivity 
        "density": 1.2,                # kg/m³
        "specific_heat": 1005.0,       # J/(kg·K)
        "default_state": EMPTY
    },
    material_id.WOOD: {
        "name": "Wood",
        "color": (139, 69, 19),
        "fuel": 5.0,
        "ignition_temp": 250.0,
        "cooling_rate": 10.0,          # W/(m²·K) — convective loss coefficient for wood surface
        "heat_transfer": 0.17,         # W/(m·K) — real wood conductivity
        "density": 600.0,              # kg/m³
        "specific_heat": 1700.0,       # J/(kg·K)
        "default_state": EMPTY
    },
    material_id.CONCRETE: {
        "name": "Wall",
        "color": (0, 0, 0),
        "fuel": 0.0,
        "ignition_temp": 1500.0,
        "cooling_rate": 8.0,         # W/(m²·K) — convective loss coefficient for concrete surface (lower than wood due to lower emissivity)    
        "heat_transfer": 0.0,          # Walls are taken as perfect insulators
        "density": 2300.0,
        "specific_heat": 880.0,
        "default_state": WALL
    },
    material_id.METAL: {
        "name": "Metal",
        "color": (120, 120, 150),
        "fuel": 0.0,
        "ignition_temp": 1500.0,
        "cooling_rate": 10.0,          # Metal dissipates heat quickly
        "heat_transfer": 50.0,         # W/(m·K) — real steel conductivity
        "density": 7800.0,
        "specific_heat": 500.0,
        "default_state": EMPTY
    }
}