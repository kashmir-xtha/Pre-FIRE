"""
utils package

All shared utilities, constants, and helpers for Pre-FIRE.

Everything is re-exported here via utilities.py so both import styles work:

    from utils.utilities import rTemp, Color          # legacy flat import
    from utils.constants import rTemp, Color          # direct submodule
    from utils import rTemp, Color                    # package-level
"""

from utils.constants import (
    Dimensions,
    Color,
    state_value,
    smoke_constants,
    fire_constants,
    material_id,
    ToolType,
    SimulationState,
    TempConstants,
    temp,
    rTemp,
)

from utils.stairwell_manager import StairwellIDGenerator

from utils.file_utils import (
    spot_to_cell_value,
    parse_cell_value,
    save_layout,
    load_layout,
    pick_csv_file,
    pick_save_csv_file,
)

from utils.window_utils import (
    set_dpi_awareness,
    get_dpi_scale,
    user_data_path,
    save_window_state,
    load_window_state,
    loadImage,
)

from utils.helpers import (
    get_neighbors,
    visualize_2d,
    resource_path,
    floor_image_to_csv,
)

from utils.save_manager import SaveManager, SimulationSnapshot
from utils.time_manager import TimeManager

__all__ = [
    # constants
    "Dimensions",
    "Color",
    "state_value",
    "smoke_constants",
    "fire_constants",
    "material_id",
    "ToolType",
    "SimulationState",
    "TempConstants",
    "temp",
    "rTemp",
    # stairwell
    "StairwellIDGenerator",
    # file I/O
    "spot_to_cell_value",
    "parse_cell_value",
    "save_layout",
    "load_layout",
    "pick_csv_file",
    "pick_save_csv_file",
    # window / DPI
    "set_dpi_awareness",
    "get_dpi_scale",
    "user_data_path",
    "save_window_state",
    "load_window_state",
    "loadImage",
    # helpers
    "get_neighbors",
    "visualize_2d",
    "resource_path",
    "floor_image_to_csv",
    # persistence
    "SaveManager",
    "SimulationSnapshot",
    # timing
    "TimeManager",
]