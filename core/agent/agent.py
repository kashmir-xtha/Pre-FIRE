"""
Refactored Agent class using specialized submodules.

The Agent class delegates responsibilities to specialized components:
- AgentVision: Perception and environmental awareness
- AgentPathplanner: Pathfinding and route planning
- AgentMovement: Physical movement and damage
- AgentState: Behavioral state management

This improves code organization, maintainability, and testability.
"""

import logging
import math
import pygame
import numpy as np
from typing import List, Optional, TYPE_CHECKING

from core.agent.agent_vision import AgentVision
from core.agent.agent_pathplanner import AgentPathplanner
from core.agent.agent_movement import AgentMovement, AgentState
from utils.utilities import Color, StairwellIDGenerator, rTemp, resource_path

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot
    from core.building import Building

logger = logging.getLogger(__name__)


class SparseFireGrid:
    """
    Memory-efficient sparse representation of fire locations.
    
    Uses a set instead of a 60x60 boolean grid to save memory (~3.6KB per agent).
    Provides array-like getitem interface for compatibility.
    """
    def __init__(self, rows: int):
        self.rows = rows
        self._fire_locations: set = set()  # Set of (row, col) tuples
    
    # Overload array access for compatibility with existing code
    # Basically allows for if x = SparseFireGrid(rows); x[row, col] to check if fire exists at that location
    def __getitem__(self, key: tuple[int, int]) -> bool:
        """Array-like access: fire_grid[row, col] returns True if fire at location."""
        if isinstance(key, tuple) and len(key) == 2:
            return key in self._fire_locations
        raise TypeError(f"Invalid index type: {type(key)}")
    
    # Overload setitem for compatibility (allows fire_grid[row, col] = True/False)
    def __setitem__(self, key: tuple[int, int], value: bool) -> None:
        """Array-like access: fire_grid[row, col] = True/False."""
        if isinstance(key, tuple) and len(key) == 2:
            if value:
                self._fire_locations.add(key)
            else:
                self._fire_locations.discard(key)
        else:
            raise TypeError(f"Invalid index type: {type(key)}")
    
    def fill(self, value: bool) -> None:
        """Clear all fire locations (compatible with numpy.fill)."""
        if not value:
            self._fire_locations.clear()
    
    def any(self) -> bool:
        """Check if any fire exists (replacement for np.any)."""
        return len(self._fire_locations) > 0
    
    def __len__(self) -> int:
        """Return number of fire locations."""
        return len(self._fire_locations)
    
    def reset(self) -> None:
        """Clear all fire locations."""
        self._fire_locations.clear()


class Agent:
    """
    Represents an evacuee in the fire simulation.
    
    This refactored version delegates responsibilities to specialized submodules:
    - AgentVision: Handles perception and environmental awareness
    - AgentPathplanner: Manages pathfinding and route planning
    - AgentMovement: Controls physical movement and damage
    - AgentState: Manages behavioral state (IDLE/REACTION/MOVING)
    
    Attributes:
        grid: The Grid the agent occupies
        spot: Current Spot position
        health: Current health (0-100)
        alive: Whether agent is still alive
        path: Current evacuation path
        current_floor: Which floor agent is on
        building: Parent Building object (for multi-floor navigation)
        
        vision: AgentVision instance
        pathplanner: AgentPathplanner instance
        movement: AgentMovement instance
        state_manager: AgentState instance
    """
    
    def __init__(
        self,
        grid: "Grid",
        start_spot: "Spot",
        floor: int = 0,
        building: Optional["Building"] = None
    ) -> None:
        """
        Initialize agent.
        
        Args:
            grid: The Grid the agent occupies
            start_spot: Starting Spot on the grid
            floor: Which floor of building (default 0)
            building: Parent Building object (for multi-floor navigation)
        """
        # Core attributes
        self.grid = grid
        self.spot = start_spot
        self.rows = grid.rows
        self.health = 100
        self.alive = True
        self.path: List["Spot"] = []
        self.path_show = True
        self.current_floor = floor
        self.building = building
        
        # Memory systems (known environment state)
        self.known_smoke = np.full((self.rows, self.rows), -1.0)
        # Memory-efficient sparse fire representation (saves ~3.6KB per agent)
        self.known_fire = SparseFireGrid(self.rows)
        self.known_temp = np.full((self.rows, self.rows), 20.0)
        
        # Precompute barrier adjacency for pathfinding
        self.barrier_adjacent = self._compute_barrier_adjacency()
        
        # Flag for smoke detection (set by vision system)
        self.smoke_detected = False
        
        # Initialize submodules
        self.vision = AgentVision(self)
        self.pathplanner = AgentPathplanner(self)
        self.movement = AgentMovement(self)
        self.state_manager = AgentState(self)
        
        # Graphics
        self._initialize_graphics()
    
    def _compute_barrier_adjacency(self) -> np.ndarray:
        """
        Precompute number of adjacent barriers for each cell.
        
        Used by pathfinding to encourage wall-following in low visibility.
        
        Returns:
            2D array where each cell contains count of cardinal barrier neighbors
        """
        rows = self.rows
        adj = np.zeros((rows, rows), dtype=np.uint8)
        
        for r in range(rows):
            for c in range(rows):
                count = 0
                # Check cardinal neighbors
                for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < rows:
                        if self.grid.grid[nr][nc].is_barrier():
                            count += 1
                adj[r, c] = count
        
        return adj
    
    def _initialize_graphics(self) -> None:
        """Initialize graphics resources (lazy-allocated on first use)."""
        self._vision_surf = None  # Lazy allocate
        self._trail_surf = None
        
        # Load agent sprite
        try:
            agent_img_path = resource_path("data/agent.png")
            img = pygame.image.load(agent_img_path).convert_alpha()
            draw_size = int(self.grid.cell_size * 2.2)
            self.base_image = pygame.transform.scale(img, (draw_size, draw_size))
        except Exception as e:
            logger.error(f"Failed to load agent image: {e}")
            self.base_image = None
    
    @property
    def vision_surf(self) -> pygame.Surface:
        """Lazy-allocate vision surface on first use (memory optimization)."""
        if self._vision_surf is None:
            grid_px = self.grid.rows * self.grid.cell_size
            self._vision_surf = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
        return self._vision_surf
    
    @property
    def trail_surf(self) -> pygame.Surface:
        """Lazy-allocate trail surface on first use (memory optimization)."""
        if self._trail_surf is None:
            grid_px = self.grid.rows * self.grid.cell_size
            self._trail_surf = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
        return self._trail_surf
    
    # ========== Main Update Loop ==========
    
    def update(self, dt: float) -> bool:
        """
        Update agent state each frame.
        
        Args:
            dt: Delta time since last update (seconds)
            
        Returns:
            True if agent reached exit, False otherwise
        """
        if not self.alive:
            return False
        
        # Always update perception and take damage
        self.vision.update_memory(dt)
        self.movement.apply_damage(dt)
        
        # Check if agent died
        if self.health <= 0:
            self.health = 0
            self.alive = False
            return False
        
        # Update behavioral state
        current_state = self.state_manager.update(dt)
        
        # Only move if in MOVING state
        if not self.state_manager.is_moving():
            return False
        
        # Check if at exit
        if self.spot.is_end():
            return True
        
        # Update path if needed
        self.pathplanner.update_path(dt)
        
        # Move toward goal
        return self.movement.move_toward_goal(dt)
    
    # ========== Path Planning ==========
    
    def best_path(self) -> List["Spot"]:
        """
        Calculate best evacuation path.
        
        Delegates to pathplanner submodule.
        
        Returns:
            List of Spot objects representing path (empty if no valid path)
        """
        return self.pathplanner.compute_path()
    
    def compute_visibility_radius(self) -> float:
        """
        Calculate current visibility radius.
        
        Delegates to vision submodule.
        
        Returns:
            Visibility radius in pixels
        """
        return self.vision.compute_visibility_radius()
    
    # ========== State Management ==========
    
    @property
    def state(self) -> str:
        """Get current behavioral state (IDLE/REACTION/MOVING)."""
        return self.state_manager.state
    
    @state.setter
    def state(self, value: str) -> None:
        """Set behavioral state."""
        self.state_manager.state = value
    
    @property
    def reaction_time(self) -> float:
        """Get reaction time in seconds."""
        return self.state_manager.reaction_time
    
    @reaction_time.setter
    def reaction_time(self, value: float) -> None:
        """Set reaction time in seconds."""
        self.state_manager.reaction_time = value
    
    @property
    def reaction_timer(self) -> float:
        """Get remaining reaction time."""
        return self.state_manager.reaction_timer
    
    @reaction_timer.setter
    def reaction_timer(self, value: float) -> None:
        """Set remaining reaction time."""
        self.state_manager.reaction_timer = value
    
    @property
    def trail(self):
        """Get movement trail."""
        return self.movement.trail
    
    @property
    def current_angle(self) -> float:
        """Get current facing angle."""
        return self.movement.current_angle
    
    @current_angle.setter
    def current_angle(self, value: float) -> None:
        """Set current facing angle."""
        self.movement.current_angle = value
    
    # ========== Reset ==========
    
    def reset(self) -> None:
        """Reset agent to initial state."""
        self.health = 100
        self.alive = True
        self.path = []
        
        self.known_smoke.fill(-1.0)
        self.known_fire.fill(False)  # Clears all fire locations
        self.known_temp.fill(20.0)
        
        if self.grid.start:
            self.spot = self.grid.start[0]
        
        self.smoke_detected = False
        
        # Reset submodules
        self.vision.reset()
        self.pathplanner.reset()
        self.movement.reset()
        self.state_manager.reset()
    
    # ========== Rendering ==========
    
    def draw(self, win: pygame.Surface) -> None:
        """
        Draw agent on the screen.
        
        Args:
            win: Surface to draw on
        """
        cell_size = self.grid.cell_size
        cx = int(self.spot.x + cell_size // 2)
        cy = int(self.spot.y + cell_size // 2)
        
        self._draw_trail(win, cell_size)
        self._draw_vision_cone(win, cx, cy)
        self._draw_sprite(win, cx, cy)
    
    def _draw_trail(self, win: pygame.Surface, cell_size: int) -> None:
        """Draw movement trail."""
        trail_list = list(self.movement.trail)
        n = len(trail_list)
        if n <= 0:
            return
        
        expected_px = self.grid.rows * cell_size
        if self.trail_surf.get_width() != expected_px:
            self.trail_surf = pygame.Surface((expected_px, expected_px), pygame.SRCALPHA)
        
        self.trail_surf.fill((0, 0, 0, 0))
        dot_radius = max(2, cell_size // 5)
        
        for i, ts in enumerate(trail_list):
            alpha = 0 if self.spot.is_end() else int(180 * (i + 1) / n)
            tx = int(ts.x + cell_size // 2)
            ty = int(ts.y + cell_size // 2)
            pygame.draw.circle(
                self.trail_surf,
                (60, 179, 113, alpha),
                (tx, ty),
                dot_radius
            )
        
        win.blit(self.trail_surf, (0, 0))
    
    def _draw_vision_cone(self, win: pygame.Surface, cx: int, cy: int) -> None:
        """Draw agent's vision cone."""
        vis_radius = self.vision.compute_visibility_radius()
        cone_points = [(cx, cy)]
        
        start_angle = math.radians(-self.movement.current_angle - 135)
        end_angle = math.radians(-self.movement.current_angle - 45)
        
        for i in range(13):
            angle = start_angle + (end_angle - start_angle) * (i / 12)
            cone_points.append((
                cx + math.cos(angle) * vis_radius,
                cy + math.sin(angle) * vis_radius
            ))
        
        self.vision_surf.fill((0, 0, 0, 0))
        pygame.draw.polygon(self.vision_surf, (180, 210, 255, 160), cone_points)
        win.blit(self.vision_surf, (0, 0))
    
    def _draw_sprite(self, win: pygame.Surface, cx: int, cy: int) -> None:
        """Draw agent sprite."""
        if not self.base_image:
            return
        
        img = self.base_image.copy()
        
        # Tint red if health is low
        if self.health < 50:
            img.fill((255, 220, 220, 255), special_flags=pygame.BLEND_MULT)
        
        rotated = pygame.transform.rotate(img, self.movement.current_angle + 180)
        win.blit(rotated, rotated.get_rect(center=(cx, cy)).topleft)
