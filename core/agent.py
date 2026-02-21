import logging
import math
import heapq
import numpy as np
import pygame
import gc
from typing import List, Optional, Tuple, Sequence, TYPE_CHECKING

from utils.utilities import Color, rTemp, resource_path

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot

logger = logging.getLogger(__name__)
temp_config = rTemp()

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
        self.path_show=True
        
        # Memory Systems
        self.known_smoke = np.full((self.rows, self.rows), -1.0)
        self.known_fire = np.zeros((self.rows, self.rows), dtype=bool)
        self.known_temp = np.full((self.rows, self.rows), 20.0)
        
        # Timers
        self.move_timer = 0
        self.update_timer = 0
        self.replan_timer = 0
        self.current_angle = 0

        # Optimization: Pre-allocate the vision surface to prevent memory leaks
        self.vision_surf = pygame.Surface((grid.rows * grid.cell_size, grid.rows * grid.cell_size), pygame.SRCALPHA)

        try:
            agent_img_pth = resource_path("data/agent.png")
            self.agent_image = pygame.image.load(agent_img_pth).convert_alpha()
            self.original_image = self.agent_image.copy()
        except Exception as e:
            logger.error(f"Failed to load agent image: {e}")
            self.agent_image = None
            self.original_image = None

    def reset(self) -> None:
        """Deep reset to prevent FPS degradation on subsequent runs."""
        self.health = 100
        self.alive = True
        self.path = []
        self.known_smoke.fill(-1.0)
        self.known_fire.fill(False)
        self.known_temp.fill(20.0)
        
        if self.grid.start:
            self.spot = self.grid.start
            
        self.current_angle = 0
        self.move_timer = 0
        self.update_timer = 0
        self.replan_timer = 0
        
        # Manually trigger garbage collection to clear old A* dictionaries
        gc.collect()

    def compute_visibility_radius(self) -> float:
        cell_size = getattr(self.grid, 'cell_size', 20)
        base_radius = 12 * cell_size 
        reduction = 1 - (self.spot.smoke * 0.7)
        return max(cell_size * 2.0, base_radius * reduction)

    def update_memory(self, dt: float) -> None:
        """Throttled memory update: Scan 10 times per second."""
        self.update_timer += dt
        if self.update_timer < 0.1:
            return
        self.update_timer = 0

        vis_r = self.compute_visibility_radius()
        cell_size = getattr(self.grid, 'cell_size', 20)
        radius_cells = int(vis_r / cell_size)
        
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                if dr*dr + dc*dc > radius_cells*radius_cells:
                    continue
                    
                nr, nc = self.spot.row + dr, self.spot.col + dc
                if 0 <= nr < self.rows and 0 <= nc < self.rows:
                    real_spot = self.grid.grid[nr][nc]
                    self.known_smoke[nr, nc] = real_spot.smoke
                    self.known_fire[nr, nc] = real_spot.is_fire()
                    self.known_temp[nr, nc] = real_spot.temperature

    def get_move_interval(self) -> float:
        # Returns time in seconds between moves; increases with smoke density
        penalty = 1.0 + (self.spot.smoke * 1.5)
        return temp_config.AGENT_MOVE_TIMER * penalty

    def update(self, dt: float) -> bool:
        if not self.alive: return False
        
        self.update_memory(dt)
        self.move_timer += dt
        self.replan_timer += dt

        if self.spot.is_end(): return True

        # Damage calculation
        if self.spot.is_fire(): self.health = 0
        self.health -= (self.spot.smoke * 10 + max(0, self.spot.temperature - 50) * 0.3) * dt
        
        if self.health <= 0:
            self.health = 0
            self.alive = False
            return False

        # FPS PROTECTION GATE: Replace old re-planning logic
        # Re-plans if path is empty OR if path is dangerous after 0.2s cooldown
        if not self.path:
            self.path = self.best_path()
            self.replan_timer = 0
        elif self.replan_timer > 0.2:
            if not path_still_safe(self.path, self.grid.grid, self):
                self.path = self.best_path()
                self.replan_timer = 0

        # Movement with instantaneous speed response
        current_interval = self.get_move_interval()
        if self.move_timer >= current_interval:
            if self.path and len(self.path) > 1:
                next_node = self.path[1]
                dx, dy = next_node.x - self.spot.x, next_node.y - self.spot.y
                if dx != 0 or dy != 0:
                    self.current_angle = math.degrees(math.atan2(-dy, dx)) - 90
                
                if not next_node.is_barrier() and not next_node.is_fire():
                    self.spot = next_node
                    self.path.pop(0)
            self.move_timer = 0
        return True

    def best_path(self) -> List["Spot"]:
        # Standard exit check
        paths = []
        for exit_spot in self.grid.exits:
            p = a_star(self.grid, self.spot, exit_spot, self)
            if p: paths.append(p)
        
        # Desperation mode if no safe path exists
        if not paths:
            for exit_spot in self.grid.exits:
                p = a_star(self.grid, self.spot, exit_spot, self, desperate=True)
                if p: paths.append(p)
        
        return min(paths, key=len) if paths else []

    def draw(self, win: pygame.Surface) -> None:
        cell_size = getattr(self.grid, 'cell_size', 20)
        cx, cy = int(self.spot.x + cell_size // 2), int(self.spot.y + cell_size // 2)
        
        # 1. Vision Cone (Optimized Surface)
        vis_radius = self.compute_visibility_radius()
        cone_points = [(cx, cy)]
        start_angle = math.radians(-self.current_angle - 135) 
        end_angle = math.radians(-self.current_angle - 45)
        for i in range(13):
            angle = start_angle + (end_angle - start_angle) * (i / 12)
            cone_points.append((cx + math.cos(angle) * vis_radius, cy + math.sin(angle) * vis_radius))
            
        self.vision_surf.fill((0, 0, 0, 0)) # Clear existing surface
        pygame.draw.polygon(self.vision_surf, (180, 210, 255, 160), cone_points)
        win.blit(self.vision_surf, (0, 0))

        # # 2. Subtle Health Aura (Pastel)
        # h_ratio = max(0.0, min(1.0, self.health / 100.0))
        # r = int(180 + (75 * (1 - h_ratio)))
        # g = int(180 + (75 * h_ratio))
        # b = 180
        # pygame.draw.circle(win, (r, g, b), (cx, cy), (cell_size // 2) + 1, 2)

        # 3. Agent Sprite
        if self.agent_image:
            draw_size = int(cell_size * 2.2) 
            img = pygame.transform.scale(self.original_image, (draw_size, draw_size))
            if self.health < 50:
                img.fill((255, 220, 220, 255), special_flags=pygame.BLEND_MULT)
            rotated = pygame.transform.rotate(img, self.current_angle)
            win.blit(rotated, rotated.get_rect(center=(cx, cy)).topleft)

# --- Pathfinding Helpers ---

def a_star(grid_obj, start, end, agent: Agent, desperate: bool = False):
    rows = agent.rows
    count = 0
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
                if neighbor.is_barrier() or agent.known_fire[nr, nc]:
                    continue
                
                # Wall-Hugging Bias for low-visibility navigation
                wall_bonus = 0
                if agent.compute_visibility_radius() < (6 * 20):
                    # Check if any immediate neighbor is a barrier
                    for tr, tc in ((0,1),(0,-1),(1,0),(-1,0)):
                        trr, tcc = nr+tr, nc+tc
                        if 0 <= trr < rows and 0 <= tcc < rows:
                            if grid_obj.grid[trr][tcc].is_barrier():
                                wall_bonus = -0.3
                                break

                dist_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
                # Penalty for turning (Momentum)
                if last_dir != (0, 0) and (dr, dc) != last_dir:
                    dist_cost += 0.8

                # Calculate weights based on agent's known environment
                smoke_val = max(0, agent.known_smoke[nr, nc])
                smoke_cost = (smoke_val * 35) if not desperate else (smoke_val * 1)
                temp_penalty = max(0, (agent.known_temp[nr, nc] - 60) * 0.8) if not desperate else 0

                temp_g = g_score[current] + dist_cost + smoke_cost + temp_penalty + wall_bonus

                if temp_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = temp_g
                    h = abs(nr - end.row) + abs(nc - end.col)
                    count += 1
                    heapq.heappush(open_heap, (temp_g + h, count, neighbor, (dr, dc)))
    return None

def path_still_safe(path: Sequence["Spot"], grid, agent: Agent) -> bool:
    # Only check ahead as far as vision allows
    vis_cells = int(agent.compute_visibility_radius() / 20)
    for spot in path[:vis_cells]:
        if grid[spot.row][spot.col].is_fire() or \
           grid[spot.row][spot.col].smoke > 0.6 or \
           agent.known_temp[spot.row, spot.col] > 80:
            return False
    return True