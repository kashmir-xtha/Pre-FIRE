from smoke import draw_smoke, spread_smoke
from buildinglayout import draw, run_editor
from agent import a_star, Agent
from fire import randomfirespot, update_fire
import pygame
import sys
from utilities import Color

# Initialization
WIDTH = 780
ROWS = 60

pygame.init()
WIN = pygame.display.set_mode((WIDTH, WIDTH))
pygame.display.set_caption("Fire and Smoke Simulation with Agent")

# Background
try:
    BG_IMAGE = pygame.image.load("building_layout.png").convert_alpha()
    BG_IMAGE = pygame.transform.scale(BG_IMAGE, (WIDTH, WIDTH))
    BG_IMAGE.set_alpha(0)
except:
    BG_IMAGE = None
    print("Background image not found. Running without background.")

def main():
    # Run editor first
    grid = run_editor(WIN, ROWS, WIDTH, BG_IMAGE)

    # Convert spots to state
    grid.update_state_from_spots()
            
    # Create agent at start position
    agent = Agent(grid, grid.start)  
   
    # Set random fire location (not at start or end)
    fire_set = randomfirespot(grid, ROWS)

    if not fire_set:
        print("Could not find empty spot for fire")
    
    # Find path from agent to end
    if grid.start and grid.end:
        agent.path = a_star(grid.grid, grid.start, grid.end, ROWS)
        grid.clear_path_visualization()  # Clear any previous path visualization
    
    clock = pygame.time.Clock()
    running = True
    frame_count = 0

    paused = False
    while running:
        clock.tick(120)  # 120 FPS
        frame_count += 1
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    # Reset simulation
                    grid.clear_simulation_visuals()
                    
                    # Reset frame count and fire source
                    frame_count = 0
                    fire_set = False

                    # Reset agent
                    agent.spot = grid.start
                    agent.path = []

                    # Recalculate path
                    if grid.start and grid.end:
                        agent.path = a_star(grid.grid, grid.start, grid.end, ROWS)
                        grid.clear_path_visualization()  # Clear any previous path visualization
                
                elif event.key == pygame.K_p:
                    paused = not paused

        #generate fire after reset
        if not fire_set:
            fire_set = randomfirespot(grid, ROWS)

        if paused: 
            continue

        #updating stuffs...
        # Update fire spread every 5 frames
        if frame_count % 5 == 0:
            grid.state = update_fire(grid.state, fire_prob=0.3)

        # Update smoke
        if frame_count % 1 == 0:
            grid.smoke = spread_smoke(grid.state, grid.smoke, ROWS, ROWS)

        # Apply fire visualization to spots
        grid.apply_fire_to_spots()
    
        # Move agent along path every 10 frames
        if agent.path and frame_count % 10 == 0 and agent.spot != grid.end:
            agent.update()
    
        # Draw everything
        WIN.fill(Color.WHITE.value) # Clear screen
        draw_smoke(grid, WIN, ROWS) # Draw smoke
        draw(WIN, grid.grid, ROWS, WIDTH) # Draw grid and spots
        agent.draw(WIN) # Draw agent
        
        pygame.display.update()
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()