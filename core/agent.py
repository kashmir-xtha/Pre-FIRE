import logging
import math
from typing import Dict, List, Optional, Sequence, Set, Tuple, TYPE_CHECKING
import heapq
import pygame

from utils.utilities import Color, rTemp, resource_path

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot


NEIGHBOR_OFFSETS = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1)
)
logger = logging.getLogger(__name__)
temp = rTemp()
BLUE = Color.BLUE.value
class Agent:
    def __init__(self, grid: "Grid", start_spot: "Spot") -> None:
        self.grid = grid
        self.spot = start_spot
        self.health = 100  # Example health value
        self.alive = (self.health > 0)
        self.speed = 1    # Cells per move
        self.path: List["Spot"] = []   # Path to follow
        self.path_show = True

        self.move_timer = 0
        self.update_timer = 0
        self.MOVE_INTERVAL = temp.AGENT_MOVE_TIMER  # seconds
        self.UPDATE_INTERVAL = 0.5  # seconds
        self.last_health = self.health

        # Load agent image
        try:
            agent_img_pth = resource_path("data/agent.png")
            self.agent_image = pygame.image.load(agent_img_pth)
            self.original_image = self.agent_image.copy()
        except:
            logger.warning("agent.png not found, using fallback circle")
            self.agent_image = None
            self.original_image = None
        
        # Movement direction tracking (0=right, 45=down-right, 90=down, etc.)
        self.current_angle = 0

    def reset(self) -> None:
        self.health = 100
        self.alive = True
        self.path = []
        if self.grid.start:
            self.spot = self.grid.start
        self.current_angle = 0
    
    def move_along_path(self) -> None:
        self.MOVE_INTERVAL = temp.AGENT_MOVE_TIMER # To have dynamic 
        if not self.path or len(self.path) <= 1:
            return

        next_spot = self.path[1]

        # Check world state using Spot methods
        if next_spot.is_fire() or next_spot.is_barrier():
            return

        # Move agent
        self.spot = next_spot
        self.path.pop(0)

    def best_path(self) -> List["Spot"]:
        """Return the best path to the exit considering safety"""
        paths = []
        for exit_spot in self.grid.exits:
            path = a_star(self.grid, self.spot, exit_spot, self.grid.rows)
            if path:
                paths.append(path)

        best_path = min(paths, key=len) if paths else None
        return best_path if best_path else [] 
    
    def update(self, dt: float) -> bool:
        """Time-based update with delta time"""
        if not self.alive:
            return False
        
        # Timers
        self.move_timer += dt
        self.update_timer += dt
        #print(self.move_timer)
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
                logger.info("Path not safe, replanning boss")
                self.path = self.best_path()
                self.move_timer = 0
                
            self.update_timer = 0
        
        # Movement
        if self.move_timer >= self.MOVE_INTERVAL and self.path:
            self.move_along_path()
            self.move_timer = 0
            
        return True

    def draw(self, win: pygame.Surface) -> None:
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
        
        # Determine rotation based on path direction (8 directions)
        if self.path and len(self.path) > 1:
            next_spot = self.path[1]
            # Ensure next spot has correct cell size
            if not hasattr(next_spot, 'cell_size'):
                next_spot.cell_size = cell_size
            
            dx = next_spot.x - self.spot.x
            dy = next_spot.y - self.spot.y
            
            # Calculate angle using atan2 for 8 directions
            if dx != 0 or dy != 0:
                angle_radians = math.atan2(dy, dx)
                angle_degrees = math.degrees(angle_radians)
                
                # Round to nearest 45 degrees for 8-directional movement
                # Directions: 0°(E), 45°(SE), 90°(S), 135°(SW), 180°(W), 225°(NW), 270°(N), 315°(NE)
                self.current_angle = round(angle_degrees / 45) * 45 - 90
        
        if self.agent_image is not None:
            # Scale image to fit the cell
            image_size = int(cell_size * 3.25)  # 120% of cell size
            scaled_image = pygame.transform.scale(self.original_image, (image_size, image_size))
            
            # Apply health-based tint
            health_ratio = self.health / 100
            if health_ratio <= 0.3:
                # Red tint for low health
                tinted_image = scaled_image.copy()
                tinted_image.fill((255, 100, 100, 128), special_flags=pygame.BLEND_MULT)
                scaled_image = tinted_image
            elif health_ratio <= 0.7:
                # Slight yellow tint for medium health
                tinted_image = scaled_image.copy()
                tinted_image.fill((255, 200, 150, 200), special_flags=pygame.BLEND_MULT)
                scaled_image = tinted_image
            
            # Rotate the image based on current angle (8 directions)
            rotated_image = pygame.transform.rotate(scaled_image, -self.current_angle)
            
            # Get the rect of the rotated image and center it
            rotated_rect = rotated_image.get_rect(center=(center_x, center_y))
            
            # Draw the rotated agent image
            win.blit(rotated_image, rotated_rect.topleft)
        else:
            # Fallback to circle if image not loaded
            # Health-based color
            health_ratio = self.health / 100
            if health_ratio > 0.7:
                color = BLUE
            elif health_ratio > 0.3:
                color = (0, 128, 255)  # Light blue
            else:
                color = (255, 100, 100)  # Reddish
            
            # Draw agent body
            pygame.draw.circle(win, color, (center_x, center_y), radius)

# HEURISTIC FUNCTION
# def heuristic(a, b):
#     return abs(a[0] - b[0]) + abs(a[1] - b[1])

def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Octile distance (better for 8-directional with diagonal cost √2)"""
    import math
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return max(dx, dy) + (1.4142 - 0.1 - 1) * min(dx, dy)

# PATH RECONSTRUCTION
def reconstruct_path(came_from: Dict["Spot", "Spot"], current: "Spot") -> List["Spot"]:
    path: List["Spot"] = []
    while current in came_from:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path

# Danger heuristic
def danger_heuristic(spot: "Spot", danger_weight: float = 2.0) -> float:
    """Calculate danger cost for a cell using Spot properties"""
    # Base danger from fire
    fire_danger = 100 if spot.is_fire() else 0
    
    # Danger from smoke (0-50)
    smoke_danger = spot.smoke * 50
    
    # Danger from temperature (>50°C is dangerous)
    temp_danger = max(0, spot.temperature - 50)
    
    return fire_danger + smoke_danger + temp_danger * danger_weight

# ------------------ A* ALGORITHM ------------------
def a_star(grid_obj: "Grid", start: "Spot", end: "Spot", rows: int) -> Optional[List["Spot"]]:
    grid = grid_obj.grid
    count = 0
    open_heap = [(0.0, count, start)]  # (f_score, tie_breaker, spot)
    open_set: Set["Spot"] = {start}
    closed_set: Set["Spot"] = set()
    
    came_from: Dict["Spot", "Spot"] = {}
    g_score: Dict["Spot", float] = {spot: float("inf") for row in grid for spot in row}
    f_score: Dict["Spot", float] = {spot: float("inf") for row in grid for spot in row}
    
    g_score[start] = 0
    f_score[start] = heuristic((start.row, start.col), (end.row, end.col))
    
    open_set_hash = {start}
    
    while open_heap:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return None
        
        _, _, current = heapq.heappop(open_heap)
        open_set.remove(current)
        if current in closed_set:
            continue
        closed_set.add(current)
        
        if current == end:
            path = reconstruct_path(came_from, end)
            return path
        
        # 8-connected grid
        for dr, dc in NEIGHBOR_OFFSETS:
            nr, nc = current.row + dr, current.col + dc
            if not (0 <= nr < rows and 0 <= nc < rows):
                continue
            neighbor = grid[nr][nc]
            if neighbor.is_barrier() or neighbor.is_fire():
                continue
            
            # Calculate cost with danger
            danger_cost = danger_heuristic(neighbor, danger_weight=2.0)
            is_diagonal = (dr != 0) and (dc != 0)
            
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
                
                if neighbor not in open_set:
                    count += 1
                    heapq.heappush(open_heap, (f_score[neighbor], count, neighbor))
                    open_set.add(neighbor)
    return None


# PATH SAFETY CHECK
def path_still_safe(
    path: Sequence["Spot"],
    grid: Sequence[Sequence["Spot"]],
    lookahead: int = 20,
    smoke_threshold: float = 0.7,
) -> bool:
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