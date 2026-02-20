import logging
import math
import heapq
import numpy as np
import pygame
from typing import List, Optional, Tuple, Sequence, TYPE_CHECKING

from utils.utilities import Color, rTemp, resource_path

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot

logger = logging.getLogger(__name__)
temp_config = rTemp()
BLUE = Color.BLUE.value

# Directions for A* (8-way movement)
NEIGHBOR_OFFSETS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
)

class Agent:
    def __init__(self, grid: "Grid", start_spot: "Spot") -> None:
        self.grid = grid
        self.spot = start_spot
        self.rows = grid.rows
        self.health = 100
        self.alive = True
        self.path: List["Spot"] = []
        self.path_show = True
        
        # Memory Systems
        self.known_smoke = np.full((self.rows, self.rows), 0.0) # -1 = unknown, 0 = clear, >0 = smoke density
        self.known_fire = np.zeros((self.rows, self.rows), dtype=bool)
        self.known_temp = np.full((self.rows, self.rows), 39) # Assume starting room temp
        
        self.move_timer = 0
        self.update_timer = 0
        self.MOVE_INTERVAL = temp_config.AGENT_MOVE_TIMER
        self.UPDATE_INTERVAL = 0.3
        self.current_angle = 0

        try:
            agent_img_pth = resource_path("data/agent.png")
            self.agent_image = pygame.image.load(agent_img_pth)
            self.original_image = self.agent_image.copy()
        except Exception as e:
            logger.error(f"Could not load agent image: {e}")
            self.agent_image = None
            self.original_image = None

    def reset(self) -> None:
        self.health = 100
        self.alive = True
        self.path = []
        self.known_smoke.fill(-1.0)
        self.known_fire.fill(False)
        self.known_temp.fill(20.0)
        if self.grid.start:
            self.spot = self.grid.start
        self.current_angle = 0

    def move_along_path(self) -> None:
        # self.MOVE_INTERVAL = temp_config.AGENT_MOVE_TIMER # To have dynamic 
        if not self.path or len(self.path) <= 1:
            return

        next_spot = self.path[1]

        # # Check world state using Spot methods
        if next_spot.is_fire() or next_spot.is_barrier():
            return

        if self.move_timer >= self.get_move_interval():
            next_node = self.path[1]
            dx, dy = next_node.x - self.spot.x, next_node.y - self.spot.y
            if dx != 0 or dy != 0:
                self.current_angle = math.degrees(math.atan2(-dy, dx)) - 90
            
            self.spot = next_node
            self.path.pop(0)
            self.move_timer = 0
        return True

    def compute_visibility_radius(self) -> float:
        """Linear visibility reduction based on current cell smoke."""
        cell_size = getattr(self.grid, 'cell_size', 20)
        base_radius = 12 * cell_size
        #reduction = 1 - (self.spot.smoke * 0.7)
        reduction = math.exp(-2.5 * self.spot.smoke)
        return max(cell_size * 1.5, base_radius * reduction)

    def update_memory(self) -> None:
        """Update internal agent knowledge based on current visibility radius."""
        radius_cells = int(self.compute_visibility_radius() / getattr(self.grid, 'cell_size', 20))
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                nr, nc = self.spot.row + dr, self.spot.col + dc
                if 0 <= nr < self.rows and 0 <= nc < self.rows:
                    real_spot = self.grid.grid[nr][nc]
                    self.known_smoke[nr, nc] = real_spot.smoke
                    self.known_fire[nr, nc] = real_spot.is_fire()
                    self.known_temp[nr, nc] = real_spot.temperature

    def get_move_interval(self) -> float:
        """Slow down the agent as smoke increases."""
        penalty = 1.0 + (self.spot.smoke * 1.5)
        #print(temp_config.AGENT_MOVE_TIMER, penalty)
        return temp_config.AGENT_MOVE_TIMER * penalty

    def best_path(self) -> List["Spot"]:
        """Evaluate all exits and pick the best path; fallback to Desperation Mode if stuck."""
        paths = []
        for exit_spot in self.grid.exits:
            p = a_star(self.grid, self.spot, exit_spot, self)
            if p: paths.append(p)
        
        if not paths:
            logger.warning("Agent trapped! Switching to Desperation Mode...")
            for exit_spot in self.grid.exits:
                p = a_star(self.grid, self.spot, exit_spot, self, desperate=True)
                if p: paths.append(p)
        
        return min(paths, key=len) if paths else []

    def update(self, dt: float) -> bool:
        if not self.alive: return False
        
        self.update_memory()
        self.move_timer += dt
        self.update_timer += dt

        if self.spot.is_end(): return True

        # Damage Logic
        if self.spot.is_fire(): self.health = 0
        self.health -= (self.spot.smoke * 10 + max(0, self.spot.temperature - 50) * 0.3) * dt

        if self.health <= 0:
            self.health = 0
            self.alive = False
            return False

        # Replanning
        if self.update_timer >= self.UPDATE_INTERVAL:
            if not self.path or not path_still_safe(self.path, self.grid.grid, self):
                self.path = self.best_path()
            self.update_timer = 0

        # Movement & Rotation
        if self.move_timer >= self.get_move_interval():
            self.move_along_path()
            self.move_timer = 0
        return True

    def draw(self, win: pygame.Surface) -> None:
        cell_size = getattr(self.grid, 'cell_size', 20)
        cx, cy = self.spot.x + cell_size // 2, self.spot.y + cell_size // 2
        
        # 1. Vision Cone (Polygonal Beam)
        vis_radius = self.compute_visibility_radius()
        cone_points = [(cx, cy)]
        start_angle = math.radians(-self.current_angle - 135) 
        end_angle = math.radians(-self.current_angle - 45)
        
        segments = 12
        for i in range(segments + 1):
            angle = start_angle + (end_angle - start_angle) * (i / segments)
            px = cx + math.cos(angle) * vis_radius
            py = cy + math.sin(angle) * vis_radius
            cone_points.append((px, py))
            
        vision_surf = pygame.Surface(win.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(vision_surf, (200, 230, 255, 110), cone_points)
        win.blit(vision_surf, (0, 0))

        # 2. Agent Sprite
        if self.agent_image:
            draw_size = int(cell_size * 2.2) 
            img = pygame.transform.scale(self.original_image, (draw_size, draw_size))
            if self.health < 40:
                img.fill((255, 50, 50, 100), special_flags=pygame.BLEND_MULT)
            rotated = pygame.transform.rotate(img, self.current_angle)
            win.blit(rotated, rotated.get_rect(center=(cx, cy)).topleft)
        else:
            pygame.draw.circle(win, BLUE, (cx, cy), cell_size // 2)

# --- Pathfinding Helper Functions ---

def a_star(grid_obj, start, end, agent: Agent, desperate: bool = False):
    rows = agent.rows
    count = 0
    # Queue stores: (f_score, tie_breaker, current_node, last_direction)
    open_heap = [(0.0, count, start, (0, 0))]
    came_from = {}
    g_score = {spot: float("inf") for row in grid_obj.grid for spot in row}
    g_score[start] = 0
    
    while open_heap:
        _, _, current, last_dir = heapq.heappop(open_heap)
        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]

        for dr, dc in NEIGHBOR_OFFSETS:
            nr, nc = current.row + dr, current.col + dc
            if 0 <= nr < rows and 0 <= nc < rows:
                neighbor = grid_obj.grid[nr][nc]
                if neighbor.is_barrier() or agent.known_fire[nr, nc]: continue
                
                # 1. Smoke Cost
                mem_smoke = max(0, agent.known_smoke[nr, nc])
                smoke_cost = (mem_smoke * 35) if not desperate else (mem_smoke * 1)
                
                # 2. Thermal Buffer (Steer clear of heat)
                mem_temp = agent.known_temp[nr, nc]
                heat_penalty = max(0, (mem_temp - 50) * 0.8) if not desperate else 0

                # 3. Movement & Directional Stubbornness
                is_diagonal = (dr != 0 and dc != 0)
                dist_cost = 1.414 if is_diagonal else 1.0
                
                # Turn penalty prevents zig-zagging
                if last_dir != (0, 0) and (dr, dc) != last_dir:
                    dist_cost += 0.8

                temp_g = g_score[current] + dist_cost + smoke_cost + heat_penalty

                if temp_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = temp_g
                    # Manhattan heuristic
                    f = temp_g + abs(nr - end.row) + abs(nc - end.col)
                    count += 1
                    heapq.heappush(open_heap, (f, count, neighbor, (dr, dc)))
    return None

def path_still_safe(path: Sequence["Spot"], grid, agent: Agent) -> bool:
    """Checks the upcoming path based on the agent's current visibility/memory."""
    radius_cells = int(agent.compute_visibility_radius() / getattr(agent.grid, 'cell_size', 20))
    for spot in path[:radius_cells]:
        m_temp = agent.known_temp[spot.row, spot.col]
        # Recalculate if fire is present, smoke is blinding, or it's dangerously hot
        if grid[spot.row][spot.col].is_fire() or grid[spot.row][spot.col].smoke > 0.8 or m_temp > 60:
            return False
    return True