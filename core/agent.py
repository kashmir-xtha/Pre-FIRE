import logging
import math
import heapq
import numpy as np
import pygame
from collections import deque
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
        self.path_show = True
        
        # Memory Systems
        self.known_smoke = np.full((self.rows, self.rows), -1.0)
        self.known_fire = np.zeros((self.rows, self.rows), dtype=bool)
        self.known_temp = np.full((self.rows, self.rows), 20.0)
        
        # Timers
        self.move_timer = 0
        self.update_timer = 0
        self.replan_timer = 0
        self.current_angle = 0

        # ----- Pre‑movement (recognition + reaction) state -----
        self.state = "IDLE"               # "IDLE", "REACTION", or "MOVING"
        self.reaction_time = 2.0           # seconds after smoke is detected
        self.reaction_timer = 0.0
        self.smoke_detected = False   # NEW (replaces np.any scan)

        # --- Trail (NEW) ---
        # deque of Spot objects; maxlen caps memory automatically
        self.trail: deque = deque(maxlen=15)
        self._last_trail_spot: Optional["Spot"] = None

        # Pre-allocate surfaces to prevent memory leaks
        grid_px = grid.rows * grid.cell_size
        self.vision_surf = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
        self.trail_surf  = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
        
        # Load sprite once and scale once
        try:
            agent_img_pth = resource_path("data/agent.png")
            img = pygame.image.load(agent_img_pth).convert_alpha()
            draw_size = int(grid.cell_size * 2.2)
            self.base_image = pygame.transform.scale(img, (draw_size, draw_size))
        except Exception as e:
            logger.error(f"Failed to load agent image: {e}")
            self.base_image = None
        
        # ----- Precompute barrier adjacency (number of cardinal barriers) -----
        self.barrier_adjacent = self._compute_barrier_adjacency()

    # ----------------------------------------------------------
    def _compute_barrier_adjacency(self) -> np.ndarray:
        """Return a 2D array where each cell stores how many cardinal neighbours are barriers."""
        rows = self.rows
        adj = np.zeros((rows, rows), dtype=np.uint8)
        for r in range(rows):
            for c in range(rows):
                count = 0
                for dr, dc in ((0,1),(0,-1),(1,0),(-1,0)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < rows:
                        if self.grid.grid[nr][nc].is_barrier():
                            count += 1
                adj[r, c] = count
        return adj
    
    def reset(self) -> None:
        """Deep reset to prevent FPS degradation on subsequent runs."""
        self.health = 100
        self.alive = True
        self.path = []

        self.trail.clear()
        self._last_trail_spot = None

        self.known_smoke.fill(-1.0)
        self.known_fire.fill(False)
        self.known_temp.fill(20.0)
        
        if self.grid.start:
            self.spot = self.grid.start
            
        self.current_angle = 0
        self.move_timer = 0
        self.update_timer = 0
        self.replan_timer = 0

        # Reset pre‑movement state
        self.state = "IDLE"
        self.reaction_timer = 0.0
        self.smoke_detected = False

    def compute_visibility_radius(self) -> float:
        cell_size = getattr(self.grid, 'cell_size', 20)
        base_radius = 20 * cell_size 
        reduction = 1 - (self.spot.smoke * 0.7)
        return max(cell_size * 3, base_radius * reduction)

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
                    if real_spot.smoke > 0.2:
                        self.smoke_detected = True   # constant-time flag

    def get_move_interval(self) -> float:
        # Returns time in seconds between moves; increases with smoke density
        penalty = 1.0 + (self.spot.smoke * 0.5)
        return temp_config.AGENT_MOVE_TIMER * penalty

    def update(self, dt: float) -> bool:
        if not self.alive:
            return False
        
        # Always update memory and apply damage (even during pre‑movement phases)
        self.update_memory(dt)
        
        # Damage calculation
        if self.spot.is_fire():
            self.health = 0
        self.health -= (self.spot.smoke * 5 + max(0, self.spot.temperature - 50) * 0.3) * dt
        
        if self.health <= 0:
            self.health = 0
            self.alive = False
            return False

        # ----- State machine for pre‑movement and egress -----
        if self.state == "IDLE":
            # Check if any smoke has been detected above threshold (0.2)
            if self.smoke_detected:
                self.state = "REACTION"
                self.reaction_timer = self.reaction_time
                logger.debug("Smoke detected – entering reaction phase")
            return False

        elif self.state == "REACTION":
            self.reaction_timer -= dt
            if self.reaction_timer <= 0:
                self.state = "MOVING"
                logger.debug("Reaction time finished – starting to move")
            return False

        # ----- MOVING state (normal egress behaviour) -----
        self.move_timer += dt
        self.replan_timer += dt

        if self.spot.is_end():
            return True

        # Re‑planning logic
        if not self.path:
            self.path = self.best_path()
            self.replan_timer = 0
        elif self.replan_timer > 0.8:
            if not path_still_safe(self.path, self.grid.grid, self):
                self.path = self.best_path()
                self.replan_timer = 0

        # Movement
        if self.move_timer >= self.get_move_interval():
            if self.path and len(self.path) > 1:
                next_node = self.path[1]
                dx, dy = next_node.x - self.spot.x, next_node.y - self.spot.y
                if dx != 0 or dy != 0:
                    self.current_angle = math.degrees(math.atan2(-dy, dx)) - 90
                
                if not next_node.is_barrier() and not next_node.is_fire():
                    self.spot = next_node
                    self.path.pop(0)

                    if self.spot is not self._last_trail_spot:
                        self.trail.append(self.spot)
                        self._last_trail_spot = self.spot
            self.move_timer = 0
        return True

    def best_path(self) -> List["Spot"]:
        if isinstance(self.spot, list):
            if len(self.spot) > 0:
                self.spot = self.spot[0]
            else:
                return []

        if not self.spot or not self.grid.exits:
            return []
        
        # Standard exit check
        paths = []
        for exit_spot in self.grid.exits:
            p = a_star(self.grid, self.spot, exit_spot, self)
            if p:
                paths.append(p)
        
        # Desperation mode if no safe path exists
        if not paths:
            for exit_spot in self.grid.exits:
                p = a_star(self.grid, self.spot, exit_spot, self, desperate=True)
                if p:
                    paths.append(p)
        
        return min(paths, key=len) if paths else []

    def draw(self, win: pygame.Surface) -> None:
        cell_size = self.grid.cell_size
        cx, cy = int(self.spot.x + cell_size // 2), int(self.spot.y + cell_size // 2)
        
        #1. Trail 
        trail_list = list(self.trail)
        n = len(trail_list)
        if n > 0:
            # Recreate surface if cell size changed since construction
            expected_px = self.grid.rows * cell_size
            if self.trail_surf.get_width() != expected_px:
                self.trail_surf = pygame.Surface((expected_px, expected_px), pygame.SRCALPHA)

            self.trail_surf.fill((0, 0, 0, 0))
            dot_radius = max(2, cell_size // 5)
            for i, ts in enumerate(trail_list):
                # alpha ramps from near-invisible (oldest) → bright (newest)
                alpha = 0 if self.spot.is_end() else int(180 * (i + 1) / n)
                tx = int(ts.x + cell_size // 2)
                ty = int(ts.y + cell_size // 2)
                pygame.draw.circle(
                    self.trail_surf,
                    (60, 179, 113, alpha),  # soft green
                    (tx, ty),
                    dot_radius,
                )
            win.blit(self.trail_surf, (0, 0))

        #2. Vision Cone (Optimized Surface)
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

        # 3. Agent Sprite
        if self.base_image:
            img = self.base_image.copy()
            if self.health < 50:
                img.fill((255, 220, 220, 255),
                         special_flags=pygame.BLEND_MULT)

            rotated = pygame.transform.rotate(img, self.current_angle + 180)
            win.blit(rotated,
                     rotated.get_rect(center=(cx, cy)).topleft)

def a_star(
    grid_obj: "Grid", 
    start: "Spot", 
    end: "Spot", 
    agent: Agent,
    desperate: bool = False,
    max_iterations: int = 3000
) -> Optional[List]:
    """
    High-performance A* pathfinding using numpy arrays instead of dictionaries.
    Args:
        grid_obj: Grid object containing cells
        start: Starting Spot object
        end: Goal Spot object
        agent: Agent object with known_smoke, known_temp, known_fire, barrier_adjacent
        desperate: If True, ignore smoke/temp (flee mode)
        max_iterations: Maximum nodes to explore before giving up (default 3000)
    Returns:
        List of Spot objects from start to end, or empty list if no path found
    """
    rows = agent.rows
    cell_size = getattr(grid_obj, 'cell_size', 20)
    vis_cells = agent.compute_visibility_radius() / cell_size
    
    # ----- Initialize arrays -----
    # g_score: cost from start to each cell (numpy array, not dict)
    g_score = np.full((rows, rows), np.inf, dtype=np.float32)
    g_score[start.row, start.col] = 0.0
    
    # visited: track explored cells to avoid re-exploration
    visited = np.zeros((rows, rows), dtype=bool)
    
    # parent: track path for reconstruction as (row, col) tuples
    parent = np.empty((rows, rows), dtype=object)
    for i in range(rows):
        for j in range(rows):
            parent[i, j] = None
    
    # Open set: heap of (f_score, counter, row, col, last_direction)
    count = 0
    open_heap = [(0.0, count, start.row, start.col, (0, 0))]
    iterations = 0
    
    # ----- Main A* loop -----
    while open_heap and iterations < max_iterations:
        _, _, r, c, last_dir = heapq.heappop(open_heap)
        iterations += 1
        
        # Skip if already visited
        if visited[r, c]:
            continue
        visited[r, c] = True
        
        # Goal check (early termination)
        if r == end.row and c == end.col:
            return _reconstruct_path(parent, end.row, end.col, grid_obj, rows)
        
        current_g = g_score[r, c]
        
        # ----- Explore neighbors -----
        for dr, dc in NEIGHBOR_OFFSETS:
            nr, nc = r + dr, c + dc
            
            # Bounds check
            if not (0 <= nr < rows and 0 <= nc < rows):
                continue
            
            # Skip if already visited
            if visited[nr, nc]:
                continue
            
            neighbor = grid_obj.grid[nr][nc]
            
            # Obstacle check (barrier or fire)
            if neighbor.is_barrier() or agent.known_fire[nr, nc]:
                continue
            
            # ----- Cost calculation (INLINED for speed) -----
            
            # 1. Movement cost (diagonal vs cardinal)
            dist_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
            
            # 2. Turning penalty (prefer straight paths)
            turn_cost = 0.0
            if last_dir != (0, 0) and (dr, dc) != last_dir:
                turn_cost = 0.2
            
            # 3. Danger cost (smoke + temperature)
            # INLINED compute_danger_cost logic
            raw_smoke = agent.known_smoke[nr, nc]
            smoke_val = 0.8 if raw_smoke < 0 else raw_smoke
            danger_cost = (smoke_val * 12) if not desperate else (smoke_val * 2)
            if not desperate:
                danger_cost += max(0, (agent.known_temp[nr, nc] - 60) * 0.8)
            
            # 4. Wall proximity cost
            # INLINED compute_wall_proximity_cost logic
            wall_cost = 0.0
            if vis_cells <= 3.0 and not desperate:
                barrier_count = agent.barrier_adjacent[nr, nc]
                if barrier_count == 0:
                    wall_cost = 0.5
                elif barrier_count == 1:
                    wall_cost = -0.15
                else:
                    wall_cost = -0.3
            
            # Total tentative g-score
            temp_g = current_g + dist_cost + turn_cost + danger_cost + wall_cost
            
            # Only add to open set if this is a better path
            if temp_g < g_score[nr, nc]:
                g_score[nr, nc] = temp_g
                parent[nr, nc] = (r, c)
                
                # f-score = g + h (with Manhattan heuristic)
                h = abs(nr - end.row) + abs(nc - end.col)
                f_score = temp_g + h
                
                count += 1
                heapq.heappush(open_heap, (f_score, count, nr, nc, (dr, dc)))
    
    # No path found
    return []


def _reconstruct_path(parent: np.ndarray, end_r: int, end_c: int, grid_obj, rows: int) -> List:
    path = []
    r, c = end_r, end_c
    
    while parent[r, c] is not None:
        path.append(grid_obj.grid[r][c])
        r, c = parent[r, c]
    
    # Add start node
    path.append(grid_obj.grid[r][c])
    
    return path[::-1]  # Reverse to get start -> end

def path_still_safe(path: Sequence["Spot"], grid, agent: Agent) -> bool:
    # How many cells ahead can the agent currently see?
    vis_cells = int(agent.compute_visibility_radius() / agent.grid.cell_size)
    for spot in path[:vis_cells]:
        if (agent.known_fire[spot.row, spot.col] or
            agent.known_smoke[spot.row, spot.col] > 0.6 or
            agent.known_temp[spot.row, spot.col] > 80):
            return False
    return True