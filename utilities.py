from enum import Enum
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
    START = 2
    END = 3
    IMPORT = 4
    EXPORT = 5

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