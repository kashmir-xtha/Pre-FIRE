import pygame
from queue import PriorityQueue

# Colors (kept local to avoid circular imports)
ORANGE = (255, 165, 0)
TURQUOISE = (64, 224, 208)
PURPLE = (128, 0, 128)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)

# ------------------ HEURISTIC ------------------
def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

# ------------------ PATH RECONSTRUCTION ------------------
def reconstruct_path(came_from, current, draw):
    path = []
    while current in came_from:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path

# ------------------ A* ALGORITHM ------------------
def a_star(draw, grid, start, end, rows):
    count = 0
    open_set = PriorityQueue()
    open_set.put((0, count, start))
    
    came_from = {}
    g_score = {spot: float("inf") for row in grid for spot in row}
    f_score = {spot: float("inf") for row in grid for spot in row}
    
    g_score[start] = 0
    f_score[start] = heuristic((start.row, start.col), (end.row, end.col))
    
    open_set_hash = {start}
    
    while not open_set.empty():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return None
        
        current = open_set.get()[2]
        open_set_hash.remove(current)
        
        if current == end:
            path = reconstruct_path(came_from, end, draw)
            # Color the path
            for spot in path:
                if spot != start and spot != end:
                    spot.color = PURPLE
            return path
        
        # 4-connected grid
        for dr, dc in [(1,0), (-1,0), (0,1), (0,-1)]:
            r = current.row + dr
            c = current.col + dc
            
            if 0 <= r < rows and 0 <= c < rows:
                neighbor = grid[r][c]
                
                # Skip if barrier or fire (fire is orange: 255, 80, 0)
                if neighbor.color == BLACK or neighbor.color == (255, 80, 0):
                    continue
                
                temp_g = g_score[current] + 1
                
                if temp_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = temp_g
                    f_score[neighbor] = temp_g + heuristic(
                        (neighbor.row, neighbor.col), (end.row, end.col)
                    )
                    
                    if neighbor not in open_set_hash:
                        count += 1
                        open_set.put((f_score[neighbor], count, neighbor))
                        open_set_hash.add(neighbor)
        
        # Visualization (optional)
        if current != start:
            current.color = TURQUOISE
        
        draw()
    
    return None

# ------------------ SIMPLE AGENT MOVEMENT ------------------
def move_agent_along_path(agent_pos, path, grid):
    """Move agent along the found path"""
    if not path or len(path) <= 1:
        return agent_pos  # No path or already at destination
    
    # Move to next position in path
    next_spot = path[1]  # path[0] is current position
    
    # Check if next position is safe (not fire or wall)
    if (next_spot.color == BLACK or next_spot.color == (255, 80, 0)):
        # Recalculate path needed
        return agent_pos
    
    # Mark old position as empty
    if agent_pos:
        agent_pos.color = (255, 255, 255)  # White/empty
    
    # Move to new position
    next_spot.color = BLUE
    return next_spot