import pygame
import sys
from buildinglayout import run_editor, draw
from agentmovement import a_star
from firespread import EMPTY, WALL, START, END, FIRE

WIDTH = 780
ROWS = 60

pygame.init()
WIN = pygame.display.set_mode((WIDTH, WIDTH))
pygame.display.set_caption("Simulation")

# ------------------ BACKGROUND ------------------
BG_IMAGE = pygame.image.load("background.png").convert_alpha()
BG_IMAGE = pygame.transform.scale(BG_IMAGE, (WIDTH, WIDTH))

def spot_grid_to_state(grid, rows):
    state = [[EMPTY for _ in range(rows)] for _ in range(rows)]

    for r in range(rows):
        for c in range(rows):
            spot = grid[r][c]
            if spot.is_barrier():
                state[r][c] = WALL
            elif spot.is_start():
                state[r][c] = START
            elif spot.is_end():
                state[r][c] = END

    return state

def state_to_spot_grid(state, grid, rows):
    for r in range(rows):
        for c in range(rows):
            if state[r][c] == FIRE:
                grid[r][c].color = (255, 80, 0)

def main():
    grid, start, end = run_editor(WIN, ROWS, WIDTH, BG_IMAGE)


    def redraw():
        draw(WIN, grid, ROWS, WIDTH, BG_IMAGE)

    a_star(redraw, grid, start, end, ROWS)

    # Keep window open after pathfinding
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

main()
