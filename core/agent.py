import pygame
from queue import PriorityQueue
from utils.utilities import Color, get_neighbors, state_value, rTemp
temp = rTemp()

class Agent:
    def __init__(self, grid, start_spot):
        self.grid = grid
        self.spot = start_spot
        self.health = 100  # Example health value
        self.alive = (self.health > 0)
        self.speed = 1    # Cells per move
        self.path = []   # Path to follow
        self.path_show = True

        self.move_timer = 0
        self.update_timer = 0
        self.MOVE_INTERVAL = temp.AGENT_MOVE_TIMER  # seconds
        self.UPDATE_INTERVAL = 0.5  # seconds
        self.last_health = self.health
        
    def reset(self):
        self.health = 100
        self.alive = True
        self.path = []
        if self.grid.start:
            self.spot = self.grid.start
    
    def move_along_path(self):
        self.MOVE_INTERVAL = temp.MOVE_TIMER # To have dynamic 
        if not self.path or len(self.path) <= 1:
            return

        next_spot = self.path[1]

        # Check world state using Spot methods
        if next_spot.is_fire() or next_spot.is_barrier():
            return

        # Move agent
        self.spot = next_spot
        self.path.pop(0)

    def best_path(self):
        """Return the best path to the exit considering safety"""
        paths = []
        for exit_spot in self.grid.exits:
            path = a_star(self.grid, self.spot, exit_spot, self.grid.rows)
            if path:
                paths.append(path)

        best_path = min(paths, key=len) if paths else None
        return best_path if best_path else [] 
    
    def update(self, dt):
        """Time-based update with delta time"""
        if not self.alive:
            return False
        
        # Timers
        self.move_timer += dt
        self.update_timer += dt

        if self.spot.is_end():
            return True
        
        # 1. Fire damage (instant death in fire)
        if self.spot.is_fire():
            self.health = 0
            self.alive = False
            return False
        
        # 2. Smoke damage
        smoke = self.spot.smoke
        if smoke > 0:
            # More smoke = more damage
            self.health -= smoke * 8 * dt
        
        # 3. Temperature damage
        temp = self.spot.temperature
        if temp > 50:  # Dangerous temperature threshold
            # Damage increases exponentially with temperature
            temp_damage = (temp - 50) * 0.2 * dt
            self.health -= temp_damage

        # Health check
        if self.health <= 0:
            self.health = 0
            self.alive = False
            return False
        
        # Periodic path safety check
        if self.update_timer >= self.UPDATE_INTERVAL:
            if not self.path or not path_still_safe(self.path, self.grid.grid):
                print("Path not safe, replanning boss")
                self.path = self.best_path()
                self.move_timer = 0
                
            self.update_timer = 0
        
        # Movement
        if self.move_timer >= self.MOVE_INTERVAL and self.path:
            self.move_along_path()
            self.move_timer = 0
            
        return True

    def draw(self, win):
        # Ensure we have a valid cell size
        if not hasattr(self.spot, 'cell_size') or self.spot.cell_size <= 0:
            # Use grid's cell_size as fallback
            cell_size = self.grid.cell_size if hasattr(self.grid, 'cell_size') else 20
            self.spot.width = cell_size
        else:
            cell_size = self.spot.width
        
        # Calculate center position within the cell
        center_x = self.spot.x + cell_size // 2
        center_y = self.spot.y + cell_size // 2
        radius = max(1, cell_size // 2)  
        
        # Health-based color
        health_ratio = self.health / 100
        if health_ratio > 0.7:
            color = Color.BLUE.value
        elif health_ratio > 0.3:
            color = (0, 128, 255)  # Light blue
        else:
            color = (255, 100, 100)  # Reddish
        
        # Draw agent body
        pygame.draw.circle(win, color, (center_x, center_y), radius)
        
        # Draw health bar
        if self.health < 100:
            health_width = max(3, int(health_ratio * (cell_size - 4)))
            health_color = (0, 255, 0) if health_ratio > 0.5 else (255, 255, 0) if health_ratio > 0.2 else (255, 0, 0)
            pygame.draw.rect(win, health_color, 
                            (center_x - cell_size//2 + 2, 
                            center_y - cell_size//2 - 5, 
                            health_width, 3))
        
        # Draw direction indicator if moving
        if self.path and len(self.path) > 1:
            next_spot = self.path[1]
            # Ensure next spot has correct cell size
            if not hasattr(next_spot, 'cell_size'):
                next_spot.cell_size = cell_size
            
            dx = next_spot.x - self.spot.x
            dy = next_spot.y - self.spot.y
            if dx != 0 or dy != 0:
                length = max(0.1, (dx**2 + dy**2)**0.5)
                dx, dy = dx/length, dy/length
                end_x = center_x + dx * radius * 0.8
                end_y = center_y + dy * radius * 0.8
                pygame.draw.line(win, (255, 255, 255), 
                            (center_x, center_y), 
                            (end_x, end_y), 2)

# HEURISTIC FUNCTION
# def heuristic(a, b):
#     return abs(a[0] - b[0]) + abs(a[1] - b[1])

def heuristic(a, b):
    """Octile distance (better for 8-directional with diagonal cost √2)"""
    import math
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 0.1 - 1) * min(dx, dy)

# PATH RECONSTRUCTION
def reconstruct_path(came_from, current):
    path = []
    while current in came_from:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path

# Danger heuristic
def danger_heuristic(spot, danger_weight=2.0):
    """Calculate danger cost for a cell using Spot properties"""
    # Base danger from fire
    fire_danger = 100 if spot.is_fire() else 0
    
    # Danger from smoke (0-50)
    smoke_danger = spot.smoke * 50
    
    # Danger from temperature (>50°C is dangerous)
    temp_danger = max(0, spot.temperature - 50)
    
    return fire_danger + smoke_danger + temp_danger * danger_weight

# ------------------ A* ALGORITHM ------------------
def a_star(grid_obj, start, end, rows):
    grid = grid_obj.grid
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
            path = reconstruct_path(came_from, end)
            return path
        
        # 8-connected grid
        for r, c in get_neighbors(current.row, current.col, rows, rows):
            neighbor = grid[r][c]
            
            # Skip if barrier or fire
            if neighbor.is_barrier() or neighbor.is_fire():
                continue
            
            # Calculate cost with danger
            danger_cost = danger_heuristic(neighbor, danger_weight=2.0)
            is_diagonal = (r != current.row) and (c != current.col)
            
            base_cost = 1
            if is_diagonal:
                if danger_cost > 30:
                    base_cost = 1
                else:
                    base_cost = 1.5
            
            total_cost = base_cost + danger_cost

            temp_g = g_score[current] + total_cost
            
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
    return None

# PATH SAFETY CHECK
def path_still_safe(path, grid, lookahead=20, smoke_threshold=0.7):
    """
    Check if the planned path is still safe to follow.
    
    A path is considered unsafe if:
    1. Any cell ahead contains fire, OR
    2. Smoke density exceeds the safety threshold (agent can't see/navigate)
    
    Args:
        path: List of Spot objects representing the path
        grid: Grid object containing state and smoke data
        lookahead: How many steps ahead to check
        smoke_threshold: Smoke density level (0-1) above which path is unsafe
    """
    if not path:
        return False

    for spot in path[:lookahead]:
        # Check if cell is on fire
        if grid[spot.row][spot.col].is_fire():
            return False
        
        # Check if smoke density is too high for safe navigation
        if grid[spot.row][spot.col].smoke > smoke_threshold:
            return False
    
    return True