# buildinglayout.py
import pygame
import csv
import sys

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (200, 200, 200)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

class Spot:
    def __init__(self, row, col, width):
        self.row = row
        self.col = col
        self.x = col * width
        self.y = row * width
        self.color = WHITE
        self.width = width

    def reset(self): self.color = WHITE
    def make_barrier(self): self.color = BLACK
    def make_start(self): self.color = GREEN
    def make_end(self): self.color = RED

    def is_barrier(self): return self.color == BLACK
    def is_start(self): return self.color == GREEN
    def is_end(self): return self.color == RED

    def draw(self, win):
        if self.color != WHITE:
            pygame.draw.rect(win, self.color,
                            (self.x, self.y, self.width, self.width))

# ------------------ GRID UTILS ------------------
def make_grid(rows, width):  #creates 2D grid
    grid = []
    gap = width // rows
    for i in range(rows):
        grid.append([])
        for j in range(rows):
            grid[i].append(Spot(i, j, gap))
    return grid

def draw_grid(win, rows, width):
    gap = width // rows
    for i in range(rows):
        pygame.draw.line(win, GREY, (0, i * gap), (width, i * gap))
        pygame.draw.line(win, GREY, (i * gap, 0), (i * gap, width))

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
    if spot.is_barrier(): return 1
    if spot.is_start(): return 2
    if spot.is_end(): return 3
    return 0

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
                    if val == "1":
                        spot.make_barrier()
                    elif val == "2":
                        spot.make_start()
                        start = spot
                    elif val == "3":
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
        win.fill(WHITE)
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