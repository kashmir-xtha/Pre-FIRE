from utils.utilities import material_id, state_value    

EMPTY = state_value.EMPTY.value
WALL = state_value.WALL.value

MATERIALS = {
    material_id.AIR: {
        "name": "Air",
        "color": (255, 255, 255),
        "fuel": 0.3,                    # ambient combustible load (carpet, furniture, papers)
        "ignition_temp": 300.0,         # °C — furnishings ignite more easily than raw wood
        "cooling_rate": 10.0,           # W/(m²·K) — convective loss coefficient 10-25 W/(m²·K)
        "heat_transfer": 0.026,         # W/(m·K) — thermal conductivity of air
        "density": 1.2,                 # kg/m³
        "specific_heat": 1005.0,        # J/(kg·K)
        "heat_release_rate": 200.0,     # °C/s — room contents burn less intensely
        "fuel_burn_rate": 0.05,         # fuel units/s — furnishings burn out in ~6s
        "smoke_yield": 0.5,             # dimensionless — moderate smoke
        "emissivity": 0.0,              # dimensionless — air is transparent to radiation
        "default_state": EMPTY
    },
    material_id.WOOD: {
        "name": "Wood",
        "color": (139, 69, 19),
        "fuel": 5.0,                    # ~17 MJ/kg calorific value (relative scale)
        "ignition_temp": 250.0,         # °C — piloted ignition of wood
        "cooling_rate": 10.0,           # W/(m²·K) — convective loss coefficient
        "heat_transfer": 0.17,          # W/(m·K) — thermal conductivity of wood
        "density": 600.0,               # kg/m³
        "specific_heat": 1700.0,        # J/(kg·K)
        "heat_release_rate": 500.0,     # °C/s — vigorous combustion
        "fuel_burn_rate": 0.15,         # fuel units/s — wood burns out in ~33s
        "smoke_yield": 1.0,             # dimensionless — baseline smoke producer
        "emissivity": 0.90,             # dimensionless — wood has high thermal emissivity
        "default_state": EMPTY,
        "ash_on_burnout": True
    },
    material_id.CONCRETE: {
        "name": "Wall",
        "color": (0, 0, 0),
        "fuel": 0.0,
        "ignition_temp": 1500.0,        # °C — effectively non-combustible
        "cooling_rate": 8.0,            # W/(m²·K) — lower emissivity than wood
        "heat_transfer": 1.4,           # W/(m·K) — real concrete conductivity
        "density": 2300.0,              # kg/m³
        "specific_heat": 880.0,         # J/(kg·K)
        "heat_release_rate": 0.0,       # non-combustible
        "fuel_burn_rate": 0.0,
        "smoke_yield": 0.0,
        "emissivity": 0.90,             # dimensionless — concrete has high thermal emissivity
        "default_state": WALL
    },
    material_id.METAL: {
        "name": "Metal",
        "color": (120, 120, 150),
        "fuel": 0.0,
        "ignition_temp": 1500.0,        # °C — structural steel
        "cooling_rate": 25.0,           # W/(m²·K) — metal dissipates heat quickly
        "heat_transfer": 50.0,          # W/(m·K) — steel conductivity
        "density": 7800.0,              # kg/m³
        "specific_heat": 500.0,         # J/(kg·K)
        "heat_release_rate": 0.0,       # non-combustible
        "fuel_burn_rate": 0.0,
        "smoke_yield": 0.0,
        "emissivity": 0.30,             # dimensionless — oxidized steel; polished metal ~0.05
        "default_state": EMPTY
    },
    material_id.ASH: { # this is system assigned, not accessible to users
        "name": "Ash",
        "color": (169, 169, 169),
        "fuel": 0.0,
        "ignition_temp": 9999.0,
        "cooling_rate": 5.0,
        "heat_transfer": 0.07,
        "density": 100.0,
        "specific_heat": 800.0,
        "heat_release_rate": 0.0,
        "fuel_burn_rate": 0.0,
        "smoke_yield": 0.0,
        "emissivity": 0.90,
        "default_state": EMPTY
    }
}