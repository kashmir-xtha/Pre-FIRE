"""General helper functions."""
import csv
from PIL import Image
import os
import sys
from typing import Any, Generator, Tuple
import numpy as np
import matplotlib.pyplot as plt


def get_neighbors(r: int, c: int, rows: int, cols: int) -> Generator[Tuple[int, int], None, None]:
    """
    Generate Moore neighborhood (8 adjacent cells) for a given cell.
    
    :param r: Row index
    :param c: Column index
    :param rows: Total number of rows
    :param cols: Total number of columns
    :yield: (row, col) tuples of valid neighbors
    """
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:  # Skip the current cell
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                yield nr, nc


def visualize_2d(arr: Any) -> None:
    """Display a 2D array as an image using matplotlib."""
    h = np.array(arr)
    plt.imshow(h, interpolation='none')
    plt.show()


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    Used for reading bundled, read-only resources inside .exe or source folder.
    Points to a temporary folder inside the PyInstaller .exe environment.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# CONVERSION FUNCTION
def floor_image_to_csv(
    image_path: str,
    csv_path: str,
    rows: int = 60,
    cols: int = 60,
    wall_color: Tuple[int, int, int] = (0, 0, 0),
    end_color: Tuple[int, int, int] = (255, 0, 0),
) -> None:
    """
    Converts a floor layout image into a 60x60 CSV grid.
    """
    grid = []
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img = img.resize((cols, rows), Image.NEAREST)
        pixels = img.load()

        for r in range(rows):
            row = []
            for c in range(cols):
                color = pixels[c, r]

                if color == wall_color:
                    row.append(1)
                elif color == end_color:
                    row.append(3)
                else:
                    row.append(0)

            grid.append(row)
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(grid)