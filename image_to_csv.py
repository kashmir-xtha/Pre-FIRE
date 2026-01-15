from PIL import Image
import csv
import os
import numpy as np

# adaptive threshold with otsu's method: 
def otsu_threshold(img_array):
    """Automatically calculates an optimal threshold to separate walls from floors in a grayscale image."""
    hist, _ = np.histogram(img_array, bins=256, range=(0, 256)) # to compute histogram of each pixel intensity
    total = img_array.size

    sum_total = np.dot(np.arange(256), hist) #dotproduct of pixel intensity and histogram values
    sum_bg = 0
    weight_bg = 0
    max_variance = 0
    threshold = 0

    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue

        weight_fg = total - weight_bg
        if weight_fg == 0: # if no of foreground pixels is zero
            break

        sum_bg += t * hist[t]
        mean_bg = sum_bg / weight_bg #mean intensities of bg and fg
        mean_fg = (sum_total - sum_bg) / weight_fg

        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2 # between-class variance
        if variance > max_variance:
            max_variance = variance
            threshold = t #threshold value corresponding to max variance that best separates the background and foreground i.e. max varience

    return threshold

# wall thickening function for images with very thin walls
def thicken_walls(grid, iterations=1):
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

# NOISE REMOVAL
def remove_isolated_walls(grid):
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
                if neighbors < 2: #if each wall cell has less than 2 wall neighbors, remove it
                    new_grid[r][c] = 0

    return new_grid

# main conversion function
def floor_image_to_wall_csv(image_path, csv_path, rows=60, cols=60, thicken_iterations=1):
    """Main function to convert a floor plan image into a CSV representing walls and floors."""
    # Load image and convert to grayscale
    img = Image.open(image_path).convert("L") #convert to grayscale

    img = img.resize((cols, rows), Image.LANCZOS) #LANCZOS is a high-quality resampling algorithm used when downscaling images
    img_array = np.array(img) # creates a 2D numpy array of pixel intensities from 0 to 255

    # Compute adaptive threshold
    threshold = otsu_threshold(img_array)

    # Build grid (NO forced boundary walls)
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            row.append(1 if img_array[r, c] < threshold else 0) # assign wall(1(0)) or floor(0(255)) based on threshold
        grid.append(row)

    # Improve wall quality
    #grid = thicken_walls(grid, thicken_iterations) # (Optional) Thicken walls
    grid = remove_isolated_walls(grid)

    # Save CSV
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(grid)

    #print(f"CSV saved in: {csv_path}")


image_directory = 'layout_images'
csv_directory = 'layout_csv'
image_entries = os.listdir(image_directory)
csv_entries = os.listdir(csv_directory) 

i = 1 
csv_filename = 'layout_1.csv'

while f'layout_{i}.csv' in csv_entries:
    i += 1
csv_filename = f"{csv_directory}/layout_{i}.csv"

floor_image_to_wall_csv(image_path="layout_images/building_layout.png", csv_path=csv_filename, rows=60, cols=60, thicken_iterations=1)
