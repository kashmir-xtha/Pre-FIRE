import sys
import pygame
import ctypes
from editor.buildinglayout import run_editor
from core.agent import Agent
from core.simulation import Simulation
from utils.utilities import Dimensions, SimulationState, loadImage, load_window_state, save_window_state, resource_path

pygame.init()
WIN = pygame.display.set_mode(
    (Dimensions.WIDTH.value + Dimensions.TOOLS_WIDTH.value, Dimensions.WIDTH.value),
    pygame.RESIZABLE # Set window size and make it resizable according to monitor resolution
)
pygame.display.set_caption("Fire & Smoke Simulation")
hwnd = pygame.display.get_wm_info()['window'] #HWND - handle to the window
if load_window_state():
    ctypes.windll.user32.ShowWindow(hwnd, 3)  # 3 - MAXIMIZE THE WINDOW


image_directory = resource_path("data/layout_images")
csv_directory = resource_path("data/layout_csv")

def main():
    BG_IMAGE, csv_filename = loadImage(image_directory, csv_directory, 2)

    # This loop allows switching between editor and simulation modes
    try:
        while(True):
            grid = run_editor(WIN, Dimensions.ROWS.value, BG_IMAGE, csv_filename)
            if grid is None:
                sys.exit()
            agent = Agent(grid, grid.start)
            agent.path = agent.best_path()
            sim = Simulation(WIN, grid, agent, Dimensions.ROWS.value, Dimensions.WIDTH.value, BG_IMAGE)
            mode = sim.run()
            if mode == SimulationState.SIM_EDITOR.value:
                print("Switching to Editor Mode")
                continue
            elif mode == SimulationState.SIM_QUIT.value:
                print("Quitting Simulation")
                sys.exit()
    finally:
        is_maximized = ctypes.windll.user32.IsZoomed(hwnd)
        save_window_state(is_maximized)
        pygame.quit()
            
if __name__ == "__main__":
    main()