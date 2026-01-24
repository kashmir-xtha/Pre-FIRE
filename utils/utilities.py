from enum import Enum
import tkinter as tk
import csv
from tkinter import filedialog
import numpy as np
import matplotlib.pyplot as plt
import pygame

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
    SMOKE_DIFFUSION = 1    # how much smoke spreads
    SMOKE_DECAY = 0.01       # smoke loss per step
    MAX_SMOKE = 1.0

class fire_constants(Enum):
    AMBIENT_TEMP = 39.0       # °C
    DIFFUSION_RATE = 0.2       # heat spreading
    COOLING_RATE = 0.02        # loss to environment
    IGNITION_TEMP = 200.0
    BURN_TEMP = 600.0
    HEAT_TRANSFER = 0.15
    FIRE_SPREAD_PROBABILITY = 0.9 #10%

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

class SimulationState(Enum):
    SIM_CONTINUE = 0
    SIM_EDITOR = 1
    SIM_QUIT = 2

def get_neighbors(r, c, rows, cols):
    # Moore neighborhood
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0: # Skip the current cell
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                yield nr, nc

def visualize_2d(arr):
    h = np.array(arr)
    plt.imshow(h, interpolation='none')
    plt.show()

def loadImage(image_directory, csv_directory, i):
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
        print("Background image not found, proceeding without it.")
        BG_IMAGE = None

    return BG_IMAGE, csv_filename

# ------------------ SAVE / LOAD ------------------
def spot_to_value(spot):
    if spot.is_barrier(): return state_value.WALL.value
    if spot.is_start(): return state_value.START.value
    if spot.is_end(): return state_value.END.value
    return state_value.EMPTY.value

def save_layout(grid, filename="layout_csv\\layout_1.csv"):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        for row in grid:
            writer.writerow([spot_to_value(s) for s in row])

def load_layout(grid, filename="layout_csv\\layout_1.csv"):
    start = None
    end = set()
    try:
        with open(filename, "r") as f:
            reader = csv.reader(f)
            for r, row in enumerate(reader):
                for c, val in enumerate(row):
                    spot = grid[r][c]
                    spot.reset()
                    if int(val) == state_value.WALL.value:
                        spot.make_barrier()
                    elif int(val) == state_value.START.value:
                        spot.make_start()
                        start = spot
                    elif int(val) == state_value.END.value:
                        spot.make_end()
                        end.add(spot)
    except FileNotFoundError:
        print(f"Layout file {filename} not found. Starting with empty grid.")
    return start, end

def pick_csv_file():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(
        filetypes=[("CSV files", "*.csv")]
    )

def pick_save_csv_file(default_name="layout.csv"):
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