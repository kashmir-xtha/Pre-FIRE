"""Simulation result persistence utilities (save/load/export)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple



@dataclass
class SimulationSnapshot:
    """Serializable snapshot of simulation outputs for later analysis."""

    timestamp: str
    seed: int
    layout_file: Optional[str]
    parameters: Dict[str, Any]
    metrics: Dict[str, Any]
    survival_count: int
    evacuation_time: float
    agent_trails: List[List[Tuple[int, int, int]]]
    fire_timeline: List[Tuple[float, int, int, int]]
    history: Dict[str, List[Any]]


class SaveManager:
    """Handles saving/loading simulation results and CSV exports."""

    @staticmethod
    def saves_dir() -> Path:
        path = Path(__file__).resolve().parent.parent / "data" / "simulation_history"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def save_results(snapshot: SimulationSnapshot, filename_prefix: str = "simulation") -> Path:
        saves_dir = SaveManager.saves_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = saves_dir / f"{filename_prefix}_{ts}.json"
        out_path.write_text(json.dumps(asdict(snapshot), indent=2), encoding="utf-8")
        return out_path

    @staticmethod
    def load_results(path: str | Path) -> SimulationSnapshot:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return SimulationSnapshot(**data)

    @staticmethod
    def latest_snapshot_path() -> Optional[Path]:
        candidates = sorted(SaveManager.saves_dir().glob("simulation_*.json"))
        return candidates[-1] if candidates else None

    @staticmethod
    def export_history_csv(history: Dict[str, List[Any]], filename_prefix: str = "simulation_history") -> Path:
        saves_dir = SaveManager.saves_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = saves_dir / f"{filename_prefix}_{ts}.csv"

        time_values = history.get("time", [])
        row_count = len(time_values)
        columns = [
            "time",
            "fire_cells",
            "avg_temp",
            "avg_smoke",
            "agent_health",
            "path_length",
        ]

        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for i in range(row_count):
                writer.writerow([
                    history.get("time", [None] * row_count)[i],
                    history.get("fire_cells", [None] * row_count)[i],
                    history.get("avg_temp", [None] * row_count)[i],
                    history.get("avg_smoke", [None] * row_count)[i],
                    'T'.join(str(h) for h in history.get("agent_health", [None] * row_count)[i]),
                    history.get("path_length", [None] * row_count)[i],
                ])

        return out_path
