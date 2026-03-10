"""File I/O utilities for saving and loading layouts."""
import csv
import logging
import os
from typing import Any, Optional, Set, Tuple
import tkinter as tk
from tkinter import filedialog

from utils.constants import state_value, material_id

logger = logging.getLogger(__name__)


def spot_to_cell_value(spot) -> str:
    """Convert a spot to a CSV cell value."""
    return f"{spot.state}|{spot.material.value}"


def parse_cell_value(value: str) -> Tuple[int, Optional[int]]:
    """Parse a CSV cell value into state and material."""
    value = value.strip()
    if "|" in value:
        state_str, material_str = value.split("|", 1)
        return int(state_str), int(material_str)
    return int(value), None


def save_layout(grid, filename: str = "layout_csv\\layout_1.csv") -> None:
    """Save grid layout to CSV file."""
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        for row in grid:
            writer.writerow([spot_to_cell_value(s) for s in row])


def load_layout(grid, filename: str = "layout_csv\\layout_1.csv") -> Tuple[Optional[Any], Set[Any]]:
    """Load grid layout from CSV file."""
    start = []
    end = set()
    try:
        with open(filename, "r") as f:
            reader = csv.reader(f)
            for r, row in enumerate(reader):
                for c, val in enumerate(row):
                    spot = grid[r][c]
                    spot.reset()
                    try:
                        cell_state, cell_material = parse_cell_value(val)
                    except ValueError:
                        continue

                    if cell_material is not None:
                        try:
                            spot.set_material(material_id(cell_material))
                        except ValueError:
                            pass

                    if cell_state == state_value.WALL.value:
                        spot.make_barrier()
                    elif cell_state == state_value.START.value:
                        spot.make_start()
                        start.append(spot)
                    elif cell_state == state_value.END.value:
                        spot.make_end()
                        end.add(spot)
                    elif cell_state == state_value.FIRE.value:
                        spot.set_on_fire()
    except FileNotFoundError:
        logger.warning("Layout file %s not found. Starting with empty grid.", filename)
    
    return start, end


def pick_csv_file() -> str:
    """Open file dialog to select a CSV or JSON file."""
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(
        filetypes=[("Layout files", "*.csv *.json"), ("CSV files", "*.csv"), ("JSON files", "*.json")]
    )


def pick_save_csv_file(default_name: str = "layout.csv") -> str:
    """Open save dialog for CSV or JSON file."""
    root = tk.Tk()
    root.withdraw()  # hide tk window
    filename = filedialog.asksaveasfilename(
        title="Save layout",
        defaultextension=".csv",
        initialfile=default_name,
        filetypes=[("Layout files", "*.csv *.json"), ("CSV Files", "*.csv"), ("JSON Building", "*.json")]
    )
    root.destroy()
    return filename


def save_building_json(json_path: str, grids) -> None:
    """Save a multi-floor building as JSON + individual floor CSVs."""
    import json

    json_dir = os.path.dirname(json_path)
    base_name = os.path.splitext(os.path.basename(json_path))[0]
    csv_dir = os.path.join(json_dir, base_name + "_floors")
    os.makedirs(csv_dir, exist_ok=True)

    floors = []
    for i, grid in enumerate(grids):
        csv_name = f"floor_{i}.csv"
        csv_path = os.path.join(csv_dir, csv_name)
        save_layout(grid.grid, csv_path)
        # Store path relative to the JSON file
        rel_path = os.path.relpath(csv_path, json_dir).replace("\\", "/")
        floors.append({"floor": i, "layout": rel_path})

    building = {
        "building_name": base_name,
        "num_floors": len(grids),
        "floors": floors
    }

    with open(json_path, 'w') as f:
        json.dump(building, f, indent=2)

    logger.info("Building saved to %s with %d floors", json_path, len(grids))
