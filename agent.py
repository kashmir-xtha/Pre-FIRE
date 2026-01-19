import pygame
from queue import PriorityQueue
from utilities import Color, get_neighbors, state_value

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
        self.MOVE_INTERVAL = 0.1  # seconds
        self.UPDATE_INTERVAL = 0.5  # seconds
        self.last_health = self.health
        
    def reset(self):
        self.health = 100
        self.alive = True
        self.path = []
        self.spot = self.grid.start
    
    def move_along_path(self):
        if not self.path or len(self.path) <= 1:
            return

        next_spot = self.path[1]
        r, c = next_spot.row, next_spot.col

        # Check world state
        if self.grid.state[r][c] == state_value.FIRE.value:
            return
        if next_spot.is_barrier() or self.grid.state[r][c] == state_value.FIRE.value:
            return

        # Move agent
        self.spot = next_spot
        self.path.pop(0)

    def update(self, dt):
        """Time-based update with delta time"""
        if not self.alive:
            return False
        
        # Timers
        self.move_timer += dt
        self.update_timer += dt
        
        r, c = self.spot.row, self.spot.col

        # 1. Fire damage (instant death in fire)
        if self.grid.state[r][c] == state_value.FIRE.value:
            self.health = 0
            self.alive = False
            return False
        
        # 2. Smoke damage
        smoke = self.grid.smoke[r][c]
        if smoke > 0:
            # More smoke = more damage
            self.health -= smoke * 8 * dt
        
        # 3. Temperature damage
        temp = self.grid.temperature[r][c]
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
            if not self.path or not path_still_safe(self.path, self.grid):
                print("Path not safe, replanning boss")
                self.path = a_star(self.grid, self.spot, self.grid.end, self.grid.rows)
                self.grid.clear_path_visualization()
            self.update_timer = 0
        
        # Movement
        if self.move_timer >= self.MOVE_INTERVAL and self.path:
            self.move_along_path()
            self.move_timer = 0
            
        return True

    def draw(self, win):
        cell_size = self.grid.cell_size
        center_x = self.spot.x + cell_size // 2
        center_y = self.spot.y + cell_size // 2
        radius = cell_size // 2
        
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

# ------------------ HEURISTIC ------------------
def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

# ------------------ PATH RECONSTRUCTION ------------------
def reconstruct_path(came_from, current):
    path = []
    while current in came_from:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path

#danger heuristic
# In agent.py - add new heuristic function
def danger_heuristic(spot, grid, danger_weight=2.0):
    """Calculate danger cost for a cell"""
    r, c = spot.row, spot.col
    
    # Base danger from fire
    fire_danger = 100 if grid.state[r][c] == state_value.FIRE.value else 0
    
    # Danger from smoke (0-100)
    smoke_danger = grid.smoke[r][c] * 50
    
    # Danger from temperature (>50°C is dangerous)
    temp_danger = max(0, grid.temperature[r][c] - 50)
    
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
            # Color the path
            for spot in path:
                if spot != start and spot != end:
                    spot.color = Color.PURPLE.value
            return path
        
        # 4-connected grid
        for r, c in get_neighbors(current.row, current.col, rows, rows):
            neighbor = grid_obj.state[r][c]
            # Skip if barrier or fire (fire is orange: 255, 80, 0)
            if neighbor == state_value.WALL.value or neighbor == state_value.FIRE.value:
                continue
            
            neighbor = grid[r][c]
            # Calculate cost with danger
            base_cost = 1
            danger_cost = danger_heuristic(neighbor, grid_obj, danger_weight=2.0)
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
        
        # Visualization
        if current != start:
            current.color = Color.TURQUOISE.value
    
    return None

# ------------------ PATH SAFETY CHECK ------------------
def path_still_safe(path, grid, lookahead=10):
    if not path:
        return False

    for spot in path[:lookahead]:
        if grid.state[spot.row][spot.col] == state_value.FIRE.value:
            return False
    return True