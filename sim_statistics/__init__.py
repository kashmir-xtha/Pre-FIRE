"""
statistics package

Standalone analysis tools for post-simulation data.

Run directly:
    python -m statistics.survival_heatmap --csv data/layout_csv/layout_1.csv

Public API (for programmatic use):
    from statistics.survival_heatmap import (
        build_heatmap,
        plot_heatmap,
        build_fresh_grid,
        build_fire_snapshot,
        BatchAgentSim,
        run_scenario,
    )
"""

from sim_statistics.survival_heatmap import (
    build_heatmap,
    plot_heatmap,
    build_fresh_grid,
    restore_grid,
    place_fire,
    build_fire_snapshot,
    bfs_distance,
    compute_next_move,
    BatchAgentSim,
    run_scenario,
)

__all__ = [
    "build_heatmap",
    "plot_heatmap",
    "build_fresh_grid",
    "restore_grid",
    "place_fire",
    "build_fire_snapshot",
    "bfs_distance",
    "compute_next_move",
    "BatchAgentSim",
    "run_scenario",
    "generate_congestion_map",
]