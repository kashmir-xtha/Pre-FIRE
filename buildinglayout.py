import pygame
import csv
import sys

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (200, 200, 200)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# ------------------ SPOT CLASS ------------------
class Spot: #represents one cell in a grid
    def __init__(self, row, col, width):
        self.row = row
        self.col = col
        self.x = col * width   # horizontal
        self.y = row * width   # vertical
        self.color = WHITE
        self.width = width

    def reset(self): self.color = WHITE
    def make_barrier(self): self.color = BLACK
    def make_start(self): self.color = GREEN
    def make_end(self): self.color = RED

    def is_barrier(self): return self.color == BLACK #returns True if cell color is BLACK   
    def is_start(self): return self.color == GREEN
    def is_end(self): return self.color == RED

    def draw(self, win):
        if self.color != WHITE:
            pygame.draw.rect(win, self.color,
                            (self.x, self.y, self.width, self.width))


# ------------------ GRID UTILS ------------------
def make_grid(rows, width): #creates 2D grid
    grid = []
    gap = width // rows
    for i in range(rows):
        grid.append([])
        for j in range(rows):
            grid[i].append(Spot(i, j, gap))
    return grid


def draw_grid(win, rows, width): # Draws grey horizontal and vertical lines splitting each grid
    gap = width // rows
    for i in range(rows):
        pygame.draw.line(win, GREY, (0, i * gap), (width, i * gap))
        pygame.draw.line(win, GREY, (i * gap, 0), (i * gap, width))


def draw(win, grid, rows, width, bg_image=None):
    win.fill((255, 255, 255))
    if bg_image: #draws background_image if provided at (0, 0) index position
        win.blit(bg_image, (0, 0))
    for row in grid:
        for spot in row:
            spot.draw(win)

    draw_grid(win, rows, width)
    pygame.display.update()


def get_clicked_pos(pos, rows, width):
    gap = width // rows
    x, y = pos
    row = y //gap
    col = x//gap
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
    return start, end


# ------------------ EDITOR LOOP ------------------
def run_editor(win, rows, width, bg_image=None):
    grid = make_grid(rows, width)
    start = end = None
    bg_image_loaded = False

    while True:
        draw(win, grid, rows, width, bg_image)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            if pygame.mouse.get_pressed()[0]: #Left mouseclick functions
                row, col = get_clicked_pos(pygame.mouse.get_pos(), rows, width)
                spot = grid[row][col]
                if not start: #First click = start, if start not already initiated
                    start = spot
                    spot.make_start()
                elif not end: #second click = end, if end not already initiated
                    end = spot
                    spot.make_end()
                else:
                    spot.make_barrier()

            elif pygame.mouse.get_pressed()[2]: #Right mouseclick functions
                row, col = get_clicked_pos(pygame.mouse.get_pos(), rows, width)
                spot = grid[row][col]
                spot.reset()
                if spot == start: start = None
                if spot == end: end = None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_i: # to un/load custom bg_image
                    if bg_image_loaded == False:
                        bg_image_loaded = True
                        bg_image.set_alpha(150)
                    else:
                        bg_image_loaded = False
                        bg_image.set_alpha(0)
                if event.key == pygame.K_s:
                    save_layout(grid)
                if event.key == pygame.K_l:
                    start, end = load_layout(grid)
                if event.key == pygame.K_SPACE and start and end: # to start pathfinding
                    return grid, start, end 
                if event.key == pygame.K_q: # to quit the program
                    pygame.quit()
                    sys.exit()
