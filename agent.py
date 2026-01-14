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

    def update(self):
        if not self.alive:
            return

        # Smoke damage
        r, c = self.spot.row, self.spot.col
        smoke = self.grid.smoke[r][c]
        #self.health -= smoke * 5 * dt

        if self.health <= 0:
            self.alive = False
            return

        # Movement
        if not self.path or not path_still_safe(self.path, self.grid):
            self.path = a_star(self.grid.grid, self.spot, self.grid.end, self.grid.rows)
            self.grid.clear_path_visualization()

        if self.path:
            self.move_along_path()
    
    def draw(self, win):
        cell_size = self.grid.cell_size
        pygame.draw.circle(
            win,
            Color.BLUE.value,
            (self.spot.x + cell_size//2, self.spot.y + cell_size//2),
            cell_size // 2
        )

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

# ------------------ A* ALGORITHM ------------------
def a_star(grid, start, end, rows):
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
            neighbor = grid[r][c]
            
            # Skip if barrier or fire (fire is orange: 255, 80, 0)
            if neighbor.color == Color.BLACK.value or neighbor.color == Color.FIRE_COLOR.value:
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