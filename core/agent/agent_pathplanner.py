"""AgentPathplanner - Handles pathfinding and route planning for agents."""
import heapq
import logging
import numpy as np
from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent.agent import Agent
    from core.spot import Spot
    from core.grid import Grid

logger = logging.getLogger(__name__)

# 8-directional movement offsets
NEIGHBOR_OFFSETS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
)


class AgentPathplanner:
    """
    Handles pathfinding and route planning for agents.
    
    This class manages:
    - A* pathfinding algorithm
    - Path validation (checking if current path is still safe)
    - Multi-floor navigation (stairwell pathfinding)
    """
    
    def __init__(self, agent: "Agent") -> None:
        """
        Initialize pathplanner.
        
        Args:
            agent: Parent Agent object
        """
        self.agent = agent
        self.replan_timer = 0.0
        self.replan_interval = 0.8  # Check path safety every 0.8 seconds
    
    def compute_path(self, desperate: bool = False) -> List["Spot"]:
        """
        Calculate best evacuation path using A* algorithm.
        
        Tries multiple strategies in order:
        1. Find path to any exit on current floor
        2. If multi-floor building, find path to stairwell
        3. Desperate mode: ignore smoke/heat dangers
        
        Args:
            desperate: If True, ignore smoke and temperature in pathfinding
            
        Returns:
            List of Spot objects representing the path (empty if no path found)
        """
        # Handle edge cases
        if isinstance(self.agent.spot, list):
            if len(self.agent.spot) > 0:
                self.agent.spot = self.agent.spot[0]
            else:
                return []
        
        if not self.agent.spot:
            return []
        
        paths = []
        
        # Strategy 1: Find path to exits on current floor
        if bool(self.agent.grid.exits):
            for exit_spot in self.agent.grid.exits:
                path = self._a_star(
                    self.agent.grid,
                    self.agent.spot,
                    exit_spot,
                    desperate=desperate
                )
                if path:
                    paths.append(path)
            
            if paths:
                return min(paths, key=len)
        
        # Strategy 2: Find path to stairwell (multi-floor buildings)
        if self.agent.building and self.agent.building.num_floors > 1:
            stairs = self._find_stairwells_on_floor(self.agent.grid)
            for stair in stairs:
                if stair is self.agent.spot:
                    continue
                path = self._a_star(
                    self.agent.grid,
                    self.agent.spot,
                    stair,
                    desperate=desperate
                )
                if path:
                    paths.append(path)
            
            if paths:
                return min(paths, key=len)
        
        # Strategy 3: Desperate mode - ignore dangers
        if not paths and bool(self.agent.grid.exits):
            for exit_spot in self.agent.grid.exits:
                path = self._a_star(
                    self.agent.grid,
                    self.agent.spot,
                    exit_spot,
                    desperate=True
                )
                if path:
                    paths.append(path)
        
        return min(paths, key=len) if paths else []
    
    def is_path_valid(self, path: Sequence["Spot"]) -> bool:
        """
        Check if a cached path is still safe to follow.
        
        Examines the portion of the path that's visible to the agent
        and checks for dangerous conditions.
        
        Args:
            path: Path to validate
            
        Returns:
            False if path is blocked or dangerous, True otherwise
        """
        if not path:
            return False
        
        # Calculate visible range (vision is already an AgentVision instance)
        vis_cells = int(self.agent.vision.compute_visibility_radius_in_pixels() / self.agent.grid.cell_size)
        
        # Check visible portion of path for dangers
        for spot in path[:vis_cells]:
            # Check for fire
            if self.agent.known_fire[spot.row, spot.col]:
                return False
            
            # Check for heavy smoke
            if self.agent.known_smoke[spot.row, spot.col] > 0.6:
                return False
            
            # Check for high temperature
            if self.agent.known_temp[spot.row, spot.col] > 80:
                return False
        
        return True
    
    def update_path(self, dt: float) -> None:
        """
        Re-plan path if it becomes unsafe.
        
        Periodically checks if the current path is still safe and
        recalculates if necessary.
        
        Args:
            dt: Delta time since last update (seconds)
        """
        self.replan_timer += dt
        
        # If no path exists, compute one
        if not self.agent.path:
            self.agent.path = self.compute_path()
            self.replan_timer = 0.0
            return
        
        # Check path safety periodically
        if self.replan_timer > self.replan_interval:
            if not self.is_path_valid(self.agent.path):
                logger.debug(f"Path unsafe, replanning for agent at ({self.agent.spot.row}, {self.agent.spot.col})")
                self.agent.path = self.compute_path()
            self.replan_timer = 0.0
    
    def _find_stairwells_on_floor(self, grid: "Grid") -> List["Spot"]:
        """
        Find all stairwell spots on current floor.
        
        Args:
            grid: Grid to search
            
        Returns:
            List of stairwell Spot objects
        """
        stairs = []
        for row in grid.grid:
            for spot in row:
                if spot.is_stairwell:
                    stairs.append(spot)
        return stairs
    
    def _compute_danger_cost(self, nr: int, nc: int, desperate: bool, vis_cells: float) -> float:
        """Aggregate environmental danger cost for A* node (nr, nc)."""
        raw_smoke = self.agent.known_smoke[nr, nc]
        smoke_val = 0.8 if raw_smoke < 0 else raw_smoke

        if desperate:
            return smoke_val * 2

        cost = smoke_val * 12
        cost += max(0, (self.agent.known_temp[nr, nc] - 60) * 0.8)
        cost += self.agent.movement.fire_avoidance_cost(nr, nc)

        if vis_cells <= 3.0:
            barrier_count = self.agent.barrier_adjacent[nr, nc]
            wall_map = {0: 0.5, 1: -0.15}
            cost += wall_map.get(barrier_count, -0.3)

        return cost

    def _a_star(
        self,
        grid: "Grid",
        start: "Spot",
        end: "Spot",
        desperate: bool = False,
        max_iterations: int = 6000 # so that it can reach the whole grid
    ) -> List["Spot"]:
        """
        High-performance A* pathfinding implementation.
        
        Uses numpy arrays for optimized performance instead of dictionaries.
        
        Args:
            grid: Grid containing the navigation mesh
            start: Starting Spot
            end: Goal Spot
            desperate: If True, ignore smoke/temperature penalties
            max_iterations: Maximum nodes to explore (prevents infinite loops)
            
        Returns:
            List of Spot objects from start to end, or empty list if no path found
        """
        rows = self.agent.rows
        cell_size = getattr(grid, 'cell_size', 20)
        vis_cells = self.agent.vision.compute_visibility_radius_in_pixels() / cell_size
        
        # Initialize arrays for tracking
        g_score = np.full((rows, rows), np.inf, dtype=np.float32)
        g_score[start.row, start.col] = 0.0
        
        visited = np.zeros((rows, rows), dtype=bool)
        
        parent = np.empty((rows, rows), dtype=object)
        for i in range(rows):
            for j in range(rows):
                parent[i, j] = None
        
        # Open set: heap of (f_score, counter, row, col, last_direction)
        count = 0
        open_heap = [(0.0, count, start.row, start.col, (0, 0))]
        iterations = 0
        
        # Main A* loop
        while open_heap and iterations < max_iterations:
            _, _, r, c, last_dir = heapq.heappop(open_heap)
            iterations += 1
            
            # Skip if already visited
            if visited[r, c]:
                continue
            visited[r, c] = True
            
            # Goal check
            if r == end.row and c == end.col:
                return self._reconstruct_path(parent, end.row, end.col, grid, rows)
            
            current_g = g_score[r, c]
            
            # Explore neighbors
            for dr, dc in NEIGHBOR_OFFSETS:
                nr, nc = r + dr, c + dc
                
                # Bounds check
                if not (0 <= nr < rows and 0 <= nc < rows):
                    continue
                
                # Skip if already visited
                if visited[nr, nc]:
                    continue
                
                neighbor = grid.grid[nr][nc]
                
                # Obstacle check
                if neighbor.is_barrier() or self.agent.known_fire[nr, nc]:
                    continue
                
                # Calculate movement cost
                dist_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
                
                # Turning penalty (encourage straight paths)
                turn_cost = 0.2 if last_dir != (0, 0) and (dr, dc) != last_dir else 0.0
                
                # Danger cost (smoke, heat, fire avoidance, wall proximity)
                danger_cost = self._compute_danger_cost(nr, nc, desperate, vis_cells)

                # Total tentative g-score
                temp_g = current_g + dist_cost + turn_cost + danger_cost
                
                # Update if this is a better path
                if temp_g < g_score[nr, nc]:
                    g_score[nr, nc] = temp_g
                    parent[nr, nc] = (r, c)
                    
                    # Calculate f-score (g + h) using Chebyshev heuristic
                    # Better for 8-directional movement than Manhattan distance
                    dx = abs(nr - end.row)
                    dy = abs(nc - end.col)
                    h = max(dx, dy)  # Chebyshev distance
                    f_score = temp_g + h
                    
                    count += 1
                    heapq.heappush(open_heap, (f_score, count, nr, nc, (dr, dc)))
        
        # No path found
        return []
    
    def _reconstruct_path(
        self,
        parent: np.ndarray,
        end_r: int,
        end_c: int,
        grid: "Grid",
        rows: int
    ) -> List["Spot"]:
        """
        Reconstruct path from parent array.
        
        Args:
            parent: Array of parent coordinates
            end_r: Goal row
            end_c: Goal column
            grid: Grid object
            rows: Grid size
            
        Returns:
            List of Spot objects from start to end
        """
        path = []
        r, c = end_r, end_c
        
        while parent[r, c] is not None:
            path.append(grid.grid[r][c])
            r, c = parent[r, c]
        
        # Add start node
        path.append(grid.grid[r][c])
        
        return path[::-1]  # Reverse to get start -> end
    
    def reset(self) -> None:
        """Reset pathplanner state (called on simulation reset)."""
        self.replan_timer = 0.0
