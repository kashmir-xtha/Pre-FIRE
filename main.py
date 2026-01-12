from smokespread import draw_smoke, spread_smoke
from buildinglayout import draw, run_editor
from agentmovement import a_star, move_agent_along_path
from firespread import randomfirespot, update_fire, EMPTY, WALL, START, END, FIRE
import pygame
import sys

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
    agent_pos = grid.start
    if agent_pos:
        agent_pos.color = (0, 0, 255)  # Blue for agent
    
    # Set random fire location (not at start or end)
    fire_set = randomfirespot(grid, ROWS)
    randomfirespot(grid, ROWS)  # Try to set another fire

    if not fire_set:
        print("Could not find empty spot for fire")
    
    # Find path from agent to end
    path = None
    if grid.start and grid.end:
        # Create a draw function for A* visualization
        def draw_a_star():
            WIN.fill((255, 255, 255))
            if BG_IMAGE:
                WIN.blit(BG_IMAGE, (0, 0))
            
            # Draw smoke (if any)
            cell = grid.cell_size
            for r in range(ROWS):
                for c in range(ROWS):
                    s = grid.smoke[r][c]
                    if s > 0:
                        shade = int(255 * (1 - s))
                        pygame.draw.rect(
                            WIN,
                            (shade, shade, shade),
                            (c * cell, r * cell, cell, cell)
                        )
            
            # Draw grid lines and spots
            draw(WIN, grid.grid, ROWS, WIDTH, BG_IMAGE)

            pygame.display.update()
        
        # Find path using A*
        path = a_star(draw_a_star, grid.grid, grid.start, grid.end, ROWS)
        if path:
            print(f"Path found with {len(path)} steps")
        else:
            print("No path found!")
    
    clock = pygame.time.Clock()
    running = True
    frame_count = 0
    
    while running:
        clock.tick(120)  # 10 FPS
        frame_count += 1
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    # Reset agent position and recalculate path
                    if agent_pos:
                        agent_pos.color = (255, 255, 255)
                    agent_pos = grid.start
                    if agent_pos:
                        agent_pos.color = (0, 0, 255)
                    if grid.start and grid.end:
                        path = a_star(lambda: None, grid.grid, grid.start, grid.end, ROWS)
        
        # Update fire spread every 5 frames
        if frame_count % 5 == 0:
            grid.state = update_fire(grid.state, fire_prob=0.3)
        
        # Update smoke
        grid.smoke = spread_smoke(grid.state, grid.smoke, ROWS, ROWS)
        
        # Apply fire visualization to spots
        grid.apply_fire_to_spots()
        
        # Move agent along path every 10 frames
        if path and frame_count % 10 == 0 and agent_pos != grid.end:
            agent_pos = move_agent_along_path(agent_pos, path, grid.grid)
            # Remove the first element (current position) from path
            if path and len(path) > 1:
                path.pop(0)
        
        # Draw everything
        WIN.fill((255, 255, 255))
        if BG_IMAGE:
            WIN.blit(BG_IMAGE, (0, 0))
        
        cell = grid.cell_size
        
        # Draw smoke
        draw_smoke(grid, WIN, ROWS)
        
        # Draw grid and spots
        draw(WIN, grid.grid, ROWS, WIDTH)

        # Draw agent position indicator
        if agent_pos:
            pygame.draw.circle(WIN, (0, 0, 255), 
                             (agent_pos.x + cell//2, agent_pos.y + cell//2), 
                             cell//3)
        
        pygame.display.update()
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()