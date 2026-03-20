"""SimAnalytics - Handles metrics tracking, snapshots, and data export."""
import time
import logging
from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np

from utils.save_manager import SaveManager, SimulationSnapshot

if TYPE_CHECKING:
    from core.simulation.simulation import Simulation

logger = logging.getLogger(__name__)


class SimAnalytics:
    """
    Handles metrics collection, history tracking, snapshot persistence,
    and CSV export for the Simulation.
    """

    def __init__(self, sim: "Simulation") -> None:
        self.sim = sim

    def update_metrics(self) -> None:
        """Compute and record per-tick metrics into history."""
        sim = self.sim
        sim.building.metrics['elapsed_time'] = sim.time_manager.get_total_time()
        sim.building.compute_metrics(sim.agents)

        metrics = sim.building.metrics
        sim.history["time"].append(metrics["elapsed_time"])
        sim.history["fire_cells"].append(metrics["fire_cells"])
        sim.history["fire_cells_per_floor"].append(metrics["fire_cells_per_floor"].copy())
        sim.history["avg_temp"].append(metrics["avg_temp"])
        sim.history["avg_temp_per_floor"].append(metrics["avg_temp_per_floor"].copy())
        sim.history["avg_smoke"].append(metrics["avg_smoke"])
        sim.history["avg_smoke_per_floor"].append(metrics["avg_smoke_per_floor"].copy())
        sim.history["agent_health"].append(metrics["agent_health"])
        sim.history["path_length"].append(metrics["path_length"])

    def record_new_fire_events(self) -> None:
        """Record newly ignited cells for post-run analysis exports."""
        sim = self.sim
        sim_t = sim.time_manager.get_total_time()
        for floor_idx, floor in enumerate(sim.building.floors):
            current_fire = floor.fire_np
            last_fire = sim._last_fire_masks[floor_idx]
            new_fire = np.argwhere(current_fire & (~last_fire))
            for r, c in new_fire:
                sim.fire_timeline.append((sim_t, floor_idx, int(r), int(c)))
            sim._last_fire_masks[floor_idx] = current_fire.copy()

    def build_snapshot(self) -> SimulationSnapshot:
        """Build a serializable simulation snapshot."""
        sim = self.sim
        elapsed = float(sim.time_manager.get_total_time())
        survival_count = sum(1 for a in sim.agents if a.health > 0)

        agent_trails = []
        for agent in sim.agents:
            trail = []
            for spot in list(agent.trail):
                trail.append((agent.current_floor, int(spot.row), int(spot.col)))
            agent_trails.append(trail)

        params = {
            "num_floors": sim.building.num_floors,
            "grid_rows": sim.rows,
            "cell_size_m": float(sim.temp.CELL_SIZE_M),
            "base_speed_m_s": float(sim.temp.BASE_SPEED_M_S),
            "fire_spread_probability": float(sim.temp.FIRE_SPREAD_PROBABILITY),
            "smoke_diffusion": float(sim.temp.SMOKE_DIFFUSION),
            "smoke_decay": float(sim.temp.SMOKE_DECAY),
            "smoke_production": float(sim.temp.SMOKE_PRODUCTION),
        }

        metrics_copy = {
            "elapsed_time": float(sim.building.metrics.get("elapsed_time", 0.0)),
            "agent_health": sim.building.metrics.get("agent_health", []),
            "fire_cells": int(sim.building.metrics.get("fire_cells", 0)),
            "avg_smoke": float(sim.building.metrics.get("avg_smoke", 0.0)),
            "avg_temp": float(sim.building.metrics.get("avg_temp", 20.0)),
            "path_length": float(sim.building.metrics.get("path_length", 0.0)),
            "escaped_agents": int(sum(1 for a in sim.agents if a.spot and a.spot.is_end())),
            "deceased_agents": int(sum(1 for a in sim.agents if a.health <= 0)),
        }

        return SimulationSnapshot(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            seed=sim.session_seed,
            layout_file=sim.layout_file,
            parameters=params,
            metrics=metrics_copy,
            survival_count=survival_count,
            evacuation_time=elapsed,
            agent_trails=agent_trails,
            fire_timeline=sim.fire_timeline.copy(),
            history={k: v.copy() for k, v in sim.history.items()},
        )

    def save_snapshot(self) -> str:
        """Save current simulation outputs as a JSON snapshot."""
        snapshot = self.build_snapshot()
        path = SaveManager.save_results(snapshot, filename_prefix="simulation")
        return str(path)

    def export_history_csv(self) -> str:
        """Export time-series history to CSV for external analysis."""
        path = SaveManager.export_history_csv(self.sim.history, filename_prefix="simulation_history")
        return str(path)

    def load_latest_snapshot(self) -> Optional[SimulationSnapshot]:
        """Load latest snapshot metadata from disk.

        Note: this loads analysis data, not a full in-place world restore.
        """
        latest = SaveManager.latest_snapshot_path()
        if latest is None:
            return None
        return SaveManager.load_results(latest)
