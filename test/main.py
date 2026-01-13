# main.py
import pygame
from buildinglayout import run_editor
from agent import Agent, a_star
from simulation import Simulation
from utilities import Dimensions

pygame.init()
WIN = pygame.display.set_mode((Dimensions.WIDTH.value, Dimensions.WIDTH.value))
pygame.display.set_caption("Fire & Smoke Simulation")

# Background
try:
    BG_IMAGE = pygame.image.load("building_layout.png").convert_alpha()
    BG_IMAGE = pygame.transform.scale(BG_IMAGE, (Dimensions.WIDTH.value, Dimensions.WIDTH.value))
    BG_IMAGE.set_alpha(0)
except:
    BG_IMAGE = None


def main():
    # Editor
    grid = run_editor(WIN, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE)
    grid.update_state_from_spots()

    # Agent
    agent = Agent(grid, grid.start)

    # Pathfinding
    if grid.start and grid.end:
        agent.path = a_star(grid.grid, grid.start, grid.end, Dimensions.ROWS.value)
    grid.clear_path_visualization()  # Clear any previous path visualization

    # Simulation
    sim = Simulation(WIN, grid, agent, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE)
    sim.run()


if __name__ == "__main__":
    main()
