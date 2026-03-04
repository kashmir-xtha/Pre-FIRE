import ctypes
import logging
import sys
import pygame
from editor.editor import run_editor
from core.agent import Agent
from core.simulation import Simulation
from utils.utilities import Dimensions, SimulationState, loadImage, load_window_state, save_window_state, resource_path, set_dpi_awareness, get_dpi_scale
from core.floors import Building

logger = logging.getLogger(__name__)
set_dpi_awareness() #before pygame initialization to ensure proper DPI scaling on Windows
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
SCALE = get_dpi_scale(hwnd)

def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

def main() -> None:
    configure_logging()
    BG_IMAGE, csv_filename = loadImage(image_directory, csv_directory, 2)

    # This loop allows switching between editor and simulation modes
    try:
        while(True):
            num_of_floors = 2
            
            grids = run_editor(WIN, Dimensions.ROWS.value, num_of_floors, BG_IMAGE, csv_filename)
            if grids is None:
                sys.exit()

            building = Building(num_of_floors=num_of_floors, rows=Dimensions.ROWS.value, width=int(Dimensions.WIDTH.value * SCALE))
            building.floors = grids  # Assign the created grids to the floors of the building
            print(f"Created building with {len(building.floors)} floors.")
            agents = []

            for f in range(num_of_floors):
                if building.floors[f].start:
                    num_agents = min(3, len(building.floors[f].start))
                    for i in range(num_agents):
                        # Assign each agent to a unique start spot from the list
                        new_agent = Agent(building.floors[f], building.floors[f].start[i], floor=f)
                        new_agent.path = new_agent.best_path()
                        agents.append(new_agent)

            sim = Simulation(WIN, building, agents, Dimensions.ROWS.value,int(Dimensions.WIDTH.value * SCALE), BG_IMAGE,)
            mode = sim.run()
            if mode == SimulationState.SIM_EDITOR.value:
                logger.info("Switching to Editor Mode")
                continue
            elif mode == SimulationState.SIM_QUIT.value:
                logger.info("Quitting Simulation")
                sys.exit()
    finally:
        is_maximized = ctypes.windll.user32.IsZoomed(hwnd)
        save_window_state(is_maximized)
        pygame.quit()
            
if __name__ == "__main__":
    main()