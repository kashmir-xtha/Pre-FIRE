from utils.utilities import material_id, state_value    

MATERIALS = {
    material_id.AIR: {
        "name": "Air",
        "color": (255, 255, 255),
        "fuel": 1.0,
        "ignition_temp": float("inf"),
        "cooling_rate": 0.1,  # Increased cooling rate
        "heat_transfer": 0.9,  # Reduced heat transfer
        "default_state": state_value.EMPTY.value  # EMPTY
    },
    material_id.WOOD: {
        "name": "Wood",
        "color": (139, 69, 19),
        "fuel": 1.0,
        "ignition_temp": 250.0,  # Reduced ignition temperature
        "cooling_rate": 0.02,   # Slower cooling
        "heat_transfer": 0.08,   # Lower heat transfer
        "default_state": state_value.EMPTY.value  # EMPTY
    },
    material_id.CONCRETE: {
        "name": "Wall",
        "color": (0, 0, 0),
        "fuel": 0.0,
        "ignition_temp": float("inf"),  # Very high ignition temp
        "cooling_rate": 0,    # Very slow cooling
        "heat_transfer": 0,    # Better heat conductor than wood
        "default_state": state_value.WALL.value  # WALL
    },
    material_id.METAL: {
        "name": "Metal",
        "color": (120, 120, 150),
        "fuel": 0.0,
        "ignition_temp": 1500,  # Very high ignition temp
        "cooling_rate": 0.05,     # Fast cooling (metal dissipates heat well)
        "heat_transfer": 0.50,     # Excellent heat conductor
        "default_state": state_value.EMPTY.value  # EMPTY
    }
}