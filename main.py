import sys
import pygame
from buildinglayout import run_editor
from agent import Agent
from simulation import Simulation
from utilities import Dimensions, SimulationState, visualize_2d

pygame.init()
WIN = pygame.display.set_mode((Dimensions.WIDTH.value + Dimensions.TOOLS_WIDTH.value, Dimensions.WIDTH.value))
pygame.display.set_caption("Fire & Smoke Simulation")
image_directory = "layout_images"
csv_directory = "layout_csv"

def main():
    i = 3 # to change background image, the number should match the csv layout used

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

    #visualize_2d(grid.temperature)

    # Agent
    agent = Agent(grid, grid.start)
    
    # Pathfinding to closest exit
    agent.path = agent.best_path()
    
    # Simulation
    sim = Simulation(WIN, grid, agent, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE)
    # sim.run()

    while(True):
        mode = sim.run()
        if mode == SimulationState.SIM_EDITOR.value:
            print("Entering Editor Mode")
            grid = run_editor(WIN, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE, csv_filename)
            grid.update_state_from_spots()
            agent = Agent(grid, grid.start)
            agent.path = agent.best_path()
            sim = Simulation(WIN, grid, agent, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE)
        elif mode == SimulationState.SIM_QUIT.value:
            print("Quitting Simulation")
            pygame.quit()
            sys.exit()
            
if __name__ == "__main__":
    main()