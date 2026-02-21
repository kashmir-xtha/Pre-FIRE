import logging
from enum import Enum
from typing import Any, Generator, Optional, Set, Tuple
import tkinter as tk
import csv
from tkinter import filedialog
import numpy as np
import matplotlib.pyplot as plt
import pygame
import json
import os
import sys

logger = logging.getLogger(__name__)

class Dimensions(Enum):
    WIDTH = 780
    ROWS = 60
    TOOLS_WIDTH = 200

class Color(Enum):
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GREY = (200, 200, 200)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)
    ORANGE = (255, 165, 0)
    TURQUOISE = (64, 224, 208)
    PURPLE = (128, 0, 128)
    BLUE = (0, 0, 255)
    FIRE_COLOR = (255, 80, 0)

class state_value(Enum):
    EMPTY = 0
    WALL = 1
    FIRE = 2
    START = 8
    END = 9

class smoke_constants(Enum):
    SMOKE_DIFFUSION = 0.03    # how much smoke spreads
    SMOKE_DECAY = 0.01       # smoke loss per step
    MAX_SMOKE = 1.0
    SMOKE_PRODUCTION = 0.25  # units per second

class fire_constants(Enum):
    AMBIENT_TEMP = 39.0       # °C
    DIFFUSION_RATE = 0.2       # heat spreading
    COOLING_RATE = 0.02        # loss to environment
    IGNITION_TEMP = 200.0
    BURN_TEMP = 600.0
    HEAT_TRANSFER = 0.15
    FIRE_SPREAD_PROBABILITY = 0.5 #10%

class material_id(Enum):
    AIR = 0
    WOOD = 1
    CONCRETE = 2
    METAL = 3
    FIRE = 4

class ToolType(Enum):
    MATERIAL = 1
    START = 8
    END = 9
    FIRE_SOURCE = 10
    
class SimulationState(Enum):
    SIM_CONTINUE = 0
    SIM_EDITOR = 1
    SIM_QUIT = 2

class TempConstants:
    def __init__(self) -> None:
        self.AMBIENT_TEMP = fire_constants.AMBIENT_TEMP.value       # °C
        self.FIRE_SPREAD_PROBABILITY = fire_constants.FIRE_SPREAD_PROBABILITY.value #10%
        self.SMOKE_DIFFUSION = smoke_constants.SMOKE_DIFFUSION.value    # how much smoke spreads
        self.SMOKE_DECAY = smoke_constants.SMOKE_DECAY.value
        self.MAX_SMOKE = smoke_constants.MAX_SMOKE.value
        self.SMOKE_PRODUCTION = smoke_constants.SMOKE_PRODUCTION.value
        self.AGENT_MOVE_TIMER = 0.1
        self.PARAMS = {
            "FIRE_SPREAD_PROBABILITY": {
                "label": "Fire Spread Probability",
                "min": 0.0,
                "max": 1.0
            },
            "SMOKE_DIFFUSION": {
                "label": "Smoke Diffusion",
                "min": 0.0,
                "max": 0.5
            },
            "SMOKE_DECAY": {
                "label": "Smoke Decay",
                "min": 0.0,
                "max": 1.0
            },
            "SMOKE_PRODUCTION": {
                "label": "Smoke Production",
                "min": 0.0,
                "max": 1.0
            },
            "AGENT_MOVE_TIMER": {
                "label": "Speed",
                "min": 0.1,
                "max": 2.0
            }
        }

temp = TempConstants()
def rTemp() -> TempConstants:
    return temp
    
def get_neighbors(r: int, c: int, rows: int, cols: int) -> Generator[Tuple[int, int], None, None]:
    # Moore neighborhood
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0: # Skip the current cell
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                yield nr, nc

def visualize_2d(arr: Any) -> None:
    h = np.array(arr)
    plt.imshow(h, interpolation='none')
    plt.show()

def loadImage(image_directory: str, csv_directory: str, i: int) -> Tuple[Optional[pygame.Surface], str]:
    '''
    Docstring for loadImage
    
    :param image_directory: Image Directory
    :param csv_directory: CSV Directory
    :param i: layout_{i}.png from image_directory and layout_{i}.csv from csv_directory
    :return: BG_IMAGE, csv_filename
    '''
    try:
        img_filename = f"{image_directory}/layout_{i}.png"
        csv_filename = f"{csv_directory}/layout_{i}.csv"
        BG_IMAGE = pygame.image.load(img_filename).convert_alpha()
        BG_IMAGE = pygame.transform.scale(BG_IMAGE, (Dimensions.WIDTH.value, Dimensions.WIDTH.value))
        BG_IMAGE.set_alpha(0)
    except:
        logger.warning("Background image not found, proceeding without it.")
        BG_IMAGE = None

    return BG_IMAGE, csv_filename

# ------------------ SAVE / LOAD ------------------
def spot_to_cell_value(spot) -> str:
    return f"{spot.state}|{spot.material.value}"

def parse_cell_value(value: str) -> Tuple[int, Optional[int]]:
    value = value.strip()
    if "|" in value:
        state_str, material_str = value.split("|", 1)
        return int(state_str), int(material_str)
    return int(value), None

def save_layout(grid, filename: str = "layout_csv\\layout_1.csv") -> None:
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        for row in grid:
            writer.writerow([spot_to_cell_value(s) for s in row])

def load_layout(grid, filename: str = "layout_csv\\layout_1.csv") -> Tuple[Optional[Any], Set[Any]]:
    start = None
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
                        start = spot
                    elif cell_state == state_value.END.value:
                        spot.make_end()
                        end.add(spot)
                    elif cell_state == state_value.FIRE.value:
                        spot.set_on_fire()
    except FileNotFoundError:
        logger.warning("Layout file %s not found. Starting with empty grid.", filename)
    # fname, bname = os.path.split(filename)
    # fname = os.path.splitext(bname)[0]
    # print(fname[len(fname) - 1])
    # loadImage(f"layout_images", filename, fname[len(fname) - 1])
    return start, end

def pick_csv_file() -> str:
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(
        filetypes=[("CSV files", "*.csv")]
    )

def pick_save_csv_file(default_name: str = "layout.csv") -> str:
    root = tk.Tk()
    root.withdraw()  # hide tk window
    filename = filedialog.asksaveasfilename(
        title="Export layout as CSV",
        defaultextension=".csv",
        initialfile=default_name,
        filetypes=[("CSV Files", "*.csv")]
    )
    root.destroy()
    return filename

# ------------------ WINDOW STATE ------------------
def user_data_path(filename: str) -> str:#Used for storing user-generated, writable data like preferences, logs, or saved states
    #points to a permanent writable directory 
    """
    Returns a writable path for user-generated files.
    Works both for normal Python runs and PyInstaller executables.
    """
    base_dir = os.path.join(os.path.expanduser("~"), ".prefire")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)


def save_window_state(is_maximized: bool) -> None: 
    state = {"maximized": is_maximized}
    path = user_data_path("window_state.json")
    with open(path, "w") as f:
        json.dump(state, f)


def load_window_state() -> bool:
    path = user_data_path("window_state.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            state = json.load(f)
            return state.get("maximized", False)
    return False

def resource_path(relative_path: str) -> str:#Used for reading bundled, read-only resources inside .exe or source folder
    #Points to a temporary folder inside the PyInstaller .exe environment
    if hasattr(sys, "_MEIPASS"):#points to the temporary folder created by pyinstaller
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)