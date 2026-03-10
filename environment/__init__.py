"""
environment package

Physics simulation: fire spread, temperature, smoke diffusion, and material properties.

Public API:
    from environment.fire import (
        do_temperature_update,
        update_fire_with_materials,
        update_temperature_with_materials,
        randomfirespot,
        collect_neighbor_data,
        is_valid_fire_start,
    )
    from environment.smoke import spread_smoke, draw_smoke
    from environment.materials import MATERIALS
"""

from environment.fire import (
    do_temperature_update,
    update_fire_with_materials,
    update_temperature_with_materials,
    randomfirespot,
    collect_neighbor_data,
    is_valid_fire_start,
)
from environment.smoke import spread_smoke, draw_smoke
from environment.materials import MATERIALS

__all__ = [
    # fire
    "do_temperature_update",
    "update_fire_with_materials",
    "update_temperature_with_materials",
    "randomfirespot",
    "collect_neighbor_data",
    "is_valid_fire_start",
    # smoke
    "spread_smoke",
    "draw_smoke",
    # materials
    "MATERIALS",
]