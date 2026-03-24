"""
Simulation package - contains the Simulation class and its submodules.

Submodules:
- SimRenderer: All drawing and rendering
- SimAnalytics: Metrics tracking, snapshots, and data export

Usage:
    from core.simulation import Simulation
    from core.simulation import SimRenderer, SimAnalytics
"""

from core.simulation.simulation import Simulation
from core.simulation.sim_renderer import SimRenderer, AnalyticsRunner, draw_temperature, plot_fire_environment, plot_path_length
from core.simulation.sim_analytics import SimAnalytics

# Re-export constants for backward compatibility
from utils.utilities import SimulationState
SIM_QUIT = SimulationState.SIM_QUIT.value
SIM_EDITOR = SimulationState.SIM_EDITOR.value
SIM_CONTINUE = SimulationState.SIM_CONTINUE.value

__all__ = [
    'Simulation', 'SimRenderer', 'SimAnalytics',
    'draw_temperature', 'plot_fire_environment', 'plot_path_length',
    'SIM_QUIT', 'SIM_EDITOR', 'SIM_CONTINUE',
]
