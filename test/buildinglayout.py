import pygame
import csv
import sys
from utilities import state_value, Color

# ------------------ GRID UTILS ------------------
def draw_grid(win, rows, width):
    gap = width // rows
    for i in range(rows):
        pygame.draw.line(win, Color.GREY.value, (0, i * gap), (width, i * gap))
        pygame.draw.line(win, Color.GREY.value, (i * gap, 0), (i * gap, width))

def draw(win, grid, rows, width, bg_image=None):
    if bg_image:
        win.blit(bg_image, (0, 0))
    for row in grid:
        for spot in row:
            spot.draw(win)
    draw_grid(win, rows, width)
    pygame.display.update()

def get_clicked_pos(pos, rows, width):
    gap = width // rows
    x, y = pos
    row = y // gap
    col = x // gap
    return row, col

# ------------------ SAVE / LOAD ------------------
def spot_to_value(spot):
    if spot.is_barrier(): return state_value.WALL.value
    if spot.is_start(): return state_value.START.value
    if spot.is_end(): return state_value.END.value
    return state_value.EMPTY.value

def save_layout(grid, filename="layout.csv"):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        for row in grid:
            writer.writerow([spot_to_value(s) for s in row])

def load_layout(grid, filename="layout.csv"):
    start = end = None
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
                        end = spot
    except FileNotFoundError:
        print(f"Layout file {filename} not found. Starting with empty grid.")
    return start, end

# ------------------ EDITOR LOOP ------------------
def run_editor(win, rows, width, bg_image=None):
    # Import here to avoid circular import
    from grid import Grid
    grid_obj = Grid(rows, width)
    
    # Try to load existing layout
    start, end = 0, 0
    bg_image_loaded = False
    run = True
    while run:
        win.fill(Color.WHITE.value)
        draw(win, grid_obj.grid, rows, width, bg_image)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if pygame.mouse.get_pressed()[0]: #Left mouseclick functions
                row, col = get_clicked_pos(event.pos, rows, width)
                if 0 <= row < rows and 0 <= col < rows:
                    spot = grid_obj.get_spot(row, col)
                    if not grid_obj.start:
                        grid_obj.start = spot
                        spot.make_start()
                    elif not grid_obj.end:
                        grid_obj.end = spot
                        spot.make_end()
                    else:
                        spot.make_barrier()
                
            elif pygame.mouse.get_pressed()[2]: #Right mouseclick functions
                row, col = get_clicked_pos(event.pos, rows, width)
                if 0 <= row < rows and 0 <= col < rows:
                    spot = grid_obj.get_spot(row, col)
                    spot.reset()
                    if spot == grid_obj.start:
                        grid_obj.start = None
                    if spot == grid_obj.end:
                        grid_obj.end = None
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_i: # to un/load custom bg_image
                    if bg_image_loaded == False:
                        bg_image_loaded = True
                        bg_image.set_alpha(150)
                    else:
                        bg_image_loaded = False
                        bg_image.set_alpha(0)

                elif event.key == pygame.K_s:
                    save_layout(grid_obj.grid)
                
                elif event.key == pygame.K_l:
                    bg_image_loaded = False
                    bg_image.set_alpha(0)
                    grid_obj.start = None
                    grid_obj.end = None
                    start, end = load_layout(grid_obj.grid)
                    if start:
                        grid_obj.start = start
                    if end:
                       grid_obj.end = end

                elif event.key == pygame.K_SPACE and grid_obj.start and grid_obj.end:
                    return grid_obj
                
                elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()
    return grid_obj