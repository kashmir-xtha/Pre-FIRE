import csv
import os
from typing import List

import numpy as np
from PIL import Image

# adaptive threshold with otsu's method: 
def otsu_threshold(img_array: np.ndarray) -> int:
    """Automatically calculates an optimal threshold to separate walls from floors in a grayscale image."""
    hist, _ = np.histogram(img_array, bins=256, range=(0, 256))
    total = img_array.size

    sum_total = np.dot(np.arange(256), hist)
    sum_bg = 0
    weight_bg = 0
    max_variance = 0
    threshold = 0

    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue

        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        sum_bg += t * hist[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg

        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if variance > max_variance:
            max_variance = variance
            threshold = t

    return threshold


def thicken_walls(grid: List[List[int]], iterations: int = 1) -> List[List[int]]:
    """Makes wall cells thicker in the generated grid for better wall continuity."""
    rows = len(grid)
    cols = len(grid[0])

    for _ in range(iterations):
        new_grid = [row[:] for row in grid]
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                if grid[r][c] == 1:
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            new_grid[r + dr][c + dc] = 1
        grid = new_grid

    return grid


def remove_isolated_walls(grid: List[List[int]]) -> List[List[int]]:
    """Removes noise/wall cells that are most likely errors because they have very few neighbors."""
    rows = len(grid)
    cols = len(grid[0])
    new_grid = [row[:] for row in grid]

    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if grid[r][c] == 1:
                neighbors = sum(
                    grid[r + dr][c + dc]
                    for dr in (-1, 0, 1)
                    for dc in (-1, 0, 1)
                    if not (dr == 0 and dc == 0)
                )
                if neighbors < 1:
                    new_grid[r][c] = 0

    return new_grid


def floor_image_to_wall_csv(
    image_path: str,
    csv_path: str,
    rows: int = 60,
    cols: int = 60,
    thicken_iterations: int = 1,
) -> None:
    """Convert a floor plan image into a CSV representing walls and floors.

    Args:
        image_path: Path to the input floor plan image.
        csv_path: Destination path for the output CSV file.
        rows: Number of grid rows in the output (default 60).
        cols: Number of grid columns in the output (default 60).
        thicken_iterations: Unused — wall thickening is disabled by default.
            Pass to thicken_walls() manually if needed.
    """
    with Image.open(image_path) as img:
        img = img.convert("L")
        img_array = np.array(img)

    threshold = otsu_threshold(img_array)

    # Auto-detect whether walls are darker or lighter than background
    if img_array.mean() < 127:  # dark background — walls are lighter
        binary = (img_array > threshold).astype(np.uint8)
    else:                        # light background — walls are darker
        binary = (img_array < threshold).astype(np.uint8)

    grid = binary.tolist()
    grid = remove_isolated_walls(grid)

    # Resize to target grid dimensions using nearest-neighbour to preserve hard edges
    binary_img = Image.fromarray(np.array(grid, dtype=np.uint8) * 255)
    binary_img = binary_img.resize((cols, rows), Image.NEAREST)
    grid = (np.array(binary_img) > 0).astype(int).tolist()

    # grid = thicken_walls(grid, thicken_iterations)  # optional — uncomment if needed

    os.makedirs(os.path.dirname(csv_path), exist_ok=True) if os.path.dirname(csv_path) else None

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(grid)


def _next_layout_index(image_dir: str, csv_dir: str) -> int:
    """Return the next unused layout index by scanning existing CSV files."""
    existing = set(os.listdir(csv_dir)) if os.path.isdir(csv_dir) else set()
    i = 1
    while f"layout_{i}.csv" in existing:
        i += 1
    return i


if __name__ == "__main__":
    IMAGE_DIR = "data/layout_images"
    CSV_DIR = "data/layout_csv"

    if not os.path.isdir(IMAGE_DIR):
        raise SystemExit(f"Image directory not found: {IMAGE_DIR!r}")
    if not os.path.isdir(CSV_DIR):
        os.makedirs(CSV_DIR)

    i = _next_layout_index(IMAGE_DIR, CSV_DIR)
    img_path = os.path.join(IMAGE_DIR, f"layout_{i}.png")
    csv_path = os.path.join(CSV_DIR, f"layout_{i}.csv")

    if not os.path.isfile(img_path):
        raise SystemExit(f"Expected image not found: {img_path!r}")

    floor_image_to_wall_csv(image_path=img_path, csv_path=csv_path, rows=60, cols=60)
    print(f"Saved: {csv_path}")