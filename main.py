import sys
import pygame
from editor.buildinglayout import run_editor
from core.agent import Agent
from core.simulation import Simulation
from utils.utilities import Dimensions, SimulationState, loadImage, visualize_2d

pygame.init()
WIN = pygame.display.set_mode((Dimensions.WIDTH.value + Dimensions.TOOLS_WIDTH.value, Dimensions.WIDTH.value))
pygame.display.set_caption("Fire & Smoke Simulation")
image_directory = "data\\layout_images"
csv_directory = "data\\layout_csv"

def main():
    BG_IMAGE, csv_filename = loadImage(image_directory, csv_directory, 2)

    # This loop allows switching between editor and simulation modes
    while(True):
        grid = run_editor(WIN, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE, csv_filename)
        grid.update_state_from_spots()
        agent = Agent(grid, grid.start)
        agent.path = agent.best_path()
        sim = Simulation(WIN, grid, agent, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE)
        mode = sim.run()
        if mode == SimulationState.SIM_EDITOR.value:
            print("Switching to Editor Mode")
            continue
        elif mode == SimulationState.SIM_QUIT.value:
            print("Quitting Simulation")
            pygame.quit()
            sys.exit()
            
if __name__ == "__main__":
    main()