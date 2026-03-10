"""AgentVision - Handles agent perception of the environment."""
import numpy as np
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent.agent import Agent

logger = logging.getLogger(__name__)


class AgentVision:
    """
    Handles agent perception and environmental awareness.
    
    This class manages:
    - Smoke detection and tracking
    - Fire awareness within vision range
    - Temperature sensing
    - Vision radius calculations based on smoke density
    """
    
    def __init__(self, agent: "Agent") -> None:
        """
        Initialize agent vision system.
        
        Args:
            agent: Parent Agent object
        """
        self.agent = agent
        self.update_timer = 0.0
        self.update_interval = 0.1  # Update perception 10 times per second
    
    def compute_visibility_radius(self) -> float:
        """
        Calculate current visibility radius based on smoke density.
        
        Smoke reduces visibility, so the effective vision range decreases
        with higher smoke concentrations.
        
        Returns:
            Visibility radius in pixels
        """
        cell_size = getattr(self.agent.grid, 'cell_size', 20)
        base_radius = 20 * cell_size  # Base visibility range
        
        # Smoke reduces visibility by up to 70%
        smoke_at_position = self.agent.spot.smoke
        reduction = 1.0 - (smoke_at_position * 0.7)
        
        # Minimum visibility is 3 cells
        return max(cell_size * 3, base_radius * reduction)
    
    def detect_smoke(self) -> bool:
        """
        Check if agent has detected smoke in their known area.
        
        Returns:
            True if smoke above threshold is detected, False otherwise
        """
        # Use the smoke_detected flag that's updated in update_memory
        return self.agent.smoke_detected
    
    def detect_fire(self) -> bool:
        """
        Check if agent has detected fire in their known area.
        
        Returns:
            True if fire is detected, False otherwise
        """
        return self.agent.known_fire.any()

    def detect_imminent_danger(self, max_distance_cells: int = 3) -> bool:
        """
        Detect danger that is close enough to trigger evacuation behavior.

        This keeps the vision system meaningful while avoiding overreaction to
        distant smoke that is visible but not yet an immediate threat.

        Args:
            max_distance_cells: Radius around the agent to treat as imminent

        Returns:
            True if nearby fire/smoke/heat is detected, False otherwise
        """
        # Immediate danger at current position always triggers reaction.
        if self.agent.spot.is_fire() or self.agent.spot.smoke > 0.2 or self.agent.spot.temperature > 100.0:
            return True

        rows = self.agent.rows
        center_r = self.agent.spot.row
        center_c = self.agent.spot.col
        radius_sq = max_distance_cells * max_distance_cells

        for dr in range(-max_distance_cells, max_distance_cells + 1):
            for dc in range(-max_distance_cells, max_distance_cells + 1):
                # Check if within circular radius
                if dr * dr + dc * dc > radius_sq:
                    continue
                
                nr = center_r + dr
                nc = center_c + dc
                
                # Check bounds 
                if not (0 <= nr < rows and 0 <= nc < rows):
                    continue
                
                # Check known fire first (most critical)
                if self.agent.known_fire[nr, nc]:
                    return True
                
                known_smoke = self.agent.known_smoke[nr, nc]
                
                # Check for significant smoke
                if known_smoke >= 0.0 and known_smoke > 0.1:
                    return True

                known_temp = self.agent.known_temp[nr, nc]
                if known_temp > 100.0:
                    return True

        return False
    
    def get_smoke_level_at_position(self) -> float:
        """
        Get smoke density at agent's current position.
        
        Returns:
            Smoke density (0.0 to 1.0)
        """
        return self.agent.spot.smoke
    
    def get_temperature_at_position(self) -> float:
        """
        Get temperature at agent's current position.
        
        Returns:
            Temperature in degrees Celsius
        """
        return self.agent.spot.temperature
    
    def is_position_safe(self) -> bool:
        """
        Determine if current position is safe for the agent.
        
        Returns:
            False if position has fire or is dangerous, True otherwise
        """
        if self.agent.spot.is_fire():
            return False
        
        if self.agent.spot.smoke > 0.8:  # Very high smoke
            return False
        
        if self.agent.spot.temperature > 100.0:  # Dangerous heat
            return False
        
        return True
    
    def update_memory(self, dt: float) -> None:
        """
        Update agent's knowledge of the environment.
        
        Scans visible area and updates known_smoke, known_fire, and known_temp
        arrays. Throttled to run approximately 10 times per second for performance.
        
        Args:
            dt: Delta time since last update (seconds)
        """
        self.update_timer += dt
        if self.update_timer < self.update_interval:
            return
        
        self.update_timer = 0.0
        
        # Calculate visibility range
        vis_radius_px = self.compute_visibility_radius()
        cell_size = getattr(self.agent.grid, 'cell_size', 20)
        radius_cells = int(vis_radius_px / cell_size)
        
        rows = self.agent.rows
        grid = self.agent.grid.grid
        current_row = self.agent.spot.row
        current_col = self.agent.spot.col
        
        # Reset smoke detection flag
        smoke_found = False
        
        # Scan circular area around agent
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                # Check if within circular radius
                if dr*dr + dc*dc > radius_cells*radius_cells:
                    continue
                
                nr = current_row + dr
                nc = current_col + dc
                
                # Check bounds
                if not (0 <= nr < rows and 0 <= nc < rows):
                    continue
                
                # Update knowledge from actual grid state
                real_spot = grid[nr][nc]
                self.agent.known_smoke[nr, nc] = real_spot.smoke
                self.agent.known_fire[nr, nc] = real_spot.is_fire()
                self.agent.known_temp[nr, nc] = real_spot.temperature
                
                # Check for smoke above threshold
                if real_spot.smoke > 0.2:
                    smoke_found = True
        
        # Update smoke detection flag
        if smoke_found:
            self.agent.smoke_detected = True

        # Notify movement system that known_fire may have changed so the
        # precomputed fire avoidance cost grid is rebuilt before next A* call.
        self.agent.movement.mark_fire_avoid_dirty()
    
    def get_known_smoke_in_path(self, path) -> float:
        """
        Calculate average smoke density along a path.
        
        Args:
            path: List of Spot objects representing a path
            
        Returns:
            Average smoke density along path
        """
        if not path:
            return 0.0
        
        total_smoke = 0.0
        count = 0
        
        for spot in path:
            if 0 <= spot.row < self.agent.rows and 0 <= spot.col < self.agent.rows:
                smoke_val = self.agent.known_smoke[spot.row, spot.col]
                if smoke_val >= 0:  # Only count known values
                    total_smoke += smoke_val
                    count += 1
        
        return total_smoke / count if count > 0 else 0.0
    
    def is_area_explored(self, row: int, col: int) -> bool:
        """
        Check if a specific cell has been observed.
        
        Args:
            row: Row index
            col: Column index
            
        Returns:
            True if cell has been observed, False otherwise
        """
        if not (0 <= row < self.agent.rows and 0 <= col < self.agent.rows):
            return False
        
        # A cell is explored if smoke value is not the initial -1.0
        return self.agent.known_smoke[row, col] >= 0.0
    
    def reset(self) -> None:
        """Reset vision state (called on simulation reset)."""
        self.update_timer = 0.0
        # Note: known arrays are reset in the main Agent.reset() method
