"""
Utilities module - Re-exports from organized submodules.
This file maintains backwards compatibility while the codebase is organized into separate modules.
"""

# Import from organized modules
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
    rTemp
)

from utils.stairwell_manager import StairwellIDGenerator

from utils.file_utils import (
    spot_to_cell_value,
    parse_cell_value,
    save_layout,
    load_layout,
    pick_csv_file,
    pick_save_csv_file
)

from utils.window_utils import (
    set_dpi_awareness,
    get_dpi_scale,
    user_data_path,
    save_window_state,
    load_window_state,
    loadImage
)

from utils.helpers import (
    get_neighbors,
    visualize_2d,
    resource_path
)

# Re-export everything for backwards compatibility
__all__ = [
    # Constants
    'Dimensions',
    'Color',
    'state_value',
    'smoke_constants',
    'fire_constants',
    'material_id',
    'ToolType',
    'SimulationState',
    'TempConstants',
    'temp',
    'rTemp',
    # Stairwell management
    'StairwellIDGenerator',
    # File utilities
    'spot_to_cell_value',
    'parse_cell_value',
    'save_layout',
    'load_layout',
    'pick_csv_file',
    'pick_save_csv_file',
    # Window utilities
    'set_dpi_awareness',
    'get_dpi_scale',
    'user_data_path',
    'save_window_state',
    'load_window_state',
    'loadImage',
    # Helpers
    'get_neighbors',
    'visualize_2d',
    'resource_path'
]
