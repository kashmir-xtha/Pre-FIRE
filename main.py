import pygame
from buildinglayout import run_editor
from agent import Agent, a_star
from simulation import Simulation
from utilities import Dimensions, visualize_2d

pygame.init()
WIN = pygame.display.set_mode((Dimensions.WIDTH.value + Dimensions.TOOLS_WIDTH.value, Dimensions.WIDTH.value))
pygame.display.set_caption("Fire & Smoke Simulation")
image_directory = "layout_images"
csv_directory = "layout_csv"

def main():
    i = 3 # to change background image, the number should match the csv layout used

    img_filename = f"{image_directory}/layout_{i}.png"
    csv_filename = f"{csv_directory}/layout_{i}.csv"

    try:
        img_filename = f"{image_directory}/layout_{i}.png"
        csv_filename = f"{csv_directory}/layout_{i}.csv"
        BG_IMAGE = pygame.image.load(img_filename).convert_alpha()
        BG_IMAGE = pygame.transform.scale(BG_IMAGE, (Dimensions.WIDTH.value, Dimensions.WIDTH.value))
        BG_IMAGE.set_alpha(0)
    except:
        BG_IMAGE = None
    # Editor
    grid = run_editor(WIN, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE, csv_filename)
    grid.update_state_from_spots()

    #visualize_2d(grid.state)

    # Agent
    agent = Agent(grid, grid.start)
    
    # Pathfinding to closest exit
    if grid.start and bool(grid.exits):
        paths = []
        for exit_spot in grid.exits:
            path = a_star(grid, agent.spot, exit_spot, grid.rows)
            if path:
                paths.append(path)

        best_path = min(paths, key=len) if paths else None
        agent.path = best_path if best_path else []
    
    # Simulation
    sim = Simulation(WIN, grid, agent, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE)
    sim.run()

if __name__ == "__main__":
    main()