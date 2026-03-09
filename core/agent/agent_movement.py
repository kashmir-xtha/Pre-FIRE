"""AgentMovement - Handles physical movement and damage for agents."""
import math
import logging
from collections import deque
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent.agent import Agent
    from core.spot import Spot

from utils.utilities import StairwellIDGenerator, rTemp

logger = logging.getLogger(__name__)


class AgentMovement:
    """
    Handles physical movement and environmental damage.
    
    This class manages:
    - Agent movement along paths
    - Speed calculations based on smoke density
    - Health and damage from fire/smoke/heat
    - Stairwell traversal between floors
    - Movement trail tracking
    """
    
    def __init__(self, agent: "Agent") -> None:
        """
        Initialize movement system.
        
        Args:
            agent: Parent Agent object
        """
        self.agent = agent
        self.move_timer = 0.0
        self.current_angle = 0.0
        
        # Trail tracking (movement history)
        self.trail: deque = deque(maxlen=15)
        self._last_trail_spot: Optional["Spot"] = None
        
        # Temperature config
        self.temp_config = rTemp()
    
    def get_move_interval(self) -> float:
        """
        Calculate time required to move one cell based on conditions.
        
        Movement speed is affected by smoke density according to research
        on visibility and evacuation speeds.
        
        Returns:
            Time in seconds to move one cell
        """
        smoke = self.agent.spot.smoke
        
        # Map smoke density to visibility conditions
        # Based on extinction coefficients from research
        if smoke < 0.13:
            condition = "clear"
        elif smoke < 0.5:
            condition = "slight_smoke"
        else:
            condition = "heavy_smoke"
        
        # Movement speeds in meters per second (from research)
        if condition == "clear":
            floor_speed = 3.67  # Normal walking speed
        elif condition == "slight_smoke":
            floor_speed = 0.96  # Reduced visibility
        else:
            floor_speed = 0.64  # Heavy smoke, very slow
        
        # Apply user-adjustable multiplier
        speed_m_s = max(0.01, floor_speed * self.temp_config.BASE_SPEED_M_S)
        
        # Calculate time to cross one cell
        cell_size_m = max(self.temp_config.CELL_SIZE_M, 0.5)
        return cell_size_m / speed_m_s
    
    def apply_damage(self, dt: float) -> None:
        """
        Apply environmental damage from fire, smoke, and heat.
        
        Args:
            dt: Delta time since last update (seconds)
        """
        # Instant death from fire
        if self.agent.spot.is_fire():
            self.agent.health = 0
            return
        
        # Smoke damage (5 damage per second at full smoke)
        smoke_damage = self.agent.spot.smoke * 5.0
        
        # Heat damage (above 50°C threshold)
        heat_damage = max(0, self.agent.spot.temperature - 50) * 0.3
        
        # Apply total damage
        total_damage = (smoke_damage + heat_damage) * dt
        self.agent.health -= total_damage
        
        # Clamp health to valid range
        self.agent.health = max(0, min(100, self.agent.health))
    
    def move_toward_goal(self, dt: float) -> bool:
        """
        Move agent toward next step in path.
        
        Args:
            dt: Delta time since last update (seconds)
            
        Returns:
            True if agent reached goal or is at exit, False otherwise
        """
        # Check if at exit
        if self.agent.spot.is_end():
            return True
        
        # Accumulate time
        self.move_timer += dt
        
        # Check if enough time has passed to move
        if self.move_timer < self.get_move_interval():
            return False
        
        # Reset timer
        self.move_timer = 0.0
        
        # Check if path exists and has next step
        if not self.agent.path or len(self.agent.path) <= 1:
            return False
        
        # Get next step in path
        next_node = self.agent.path[1]
        
        # Update facing angle for visualization
        dx = next_node.x - self.agent.spot.x
        dy = next_node.y - self.agent.spot.y
        if dx != 0 or dy != 0:
            self.current_angle = math.degrees(math.atan2(-dy, dx)) - 90
        
        # Check for stairwell crossing
        if next_node.is_stairwell and self.agent.building and self.agent.building.num_floors > 1:
            self._cross_stairwell(next_node)
            return False
        
        # Normal movement - check if next cell is passable
        if not next_node.is_barrier() and not next_node.is_fire():
            self.agent.spot = next_node
            self.agent.path.pop(0)  # Remove current position from path
            self._add_trail()
        
        return False
    
    def _cross_stairwell(self, stairwell: "Spot") -> None:
        """
        Handle agent crossing to another floor via stairwell.
        
        Args:
            stairwell: Stairwell Spot being crossed
        """
        if not self.agent.building or stairwell.stair_id is None:
            logger.warning("Stairwell crossing attempted without valid building or stair_id")
            return
        
        # Find connected floors for this stairwell
        connected_floors = StairwellIDGenerator.get_connected_floors(stairwell.stair_id)
        logger.debug(f"Connected floors for stairwell {stairwell.stair_id}: {connected_floors}")
        
        if not connected_floors:
            logger.warning(f"Stairwell {stairwell.stair_id} has no connected floors")
            return
        
        # Remove current floor from options
        candidate_floors = [f for f in connected_floors if f != self.agent.current_floor]
        if not candidate_floors:
            logger.debug(f"No valid stairwell destinations from floor {self.agent.current_floor}")
            return
        
        # Prioritize floors with exits (prefer lower floors)
        floors_with_exits = sorted(
            [f for f in candidate_floors if bool(self.agent.building.get_floor(f).exits)]
        )
        
        if floors_with_exits:
            # Go to lowest floor with exit
            dest_floor = floors_with_exits[0]
            logger.debug(f"Agent taking stairwell to floor {dest_floor} (exit detected)")
        else:
            # Go to lower floor if possible
            lower_candidates = sorted([f for f in candidate_floors if f < self.agent.current_floor])
            dest_floor = lower_candidates[0] if lower_candidates else sorted(candidate_floors)[0]
            logger.debug(f"Agent taking stairwell to floor {dest_floor} (no exit)")
        
        # Prevent upward movement (evacuation goes down)
        if dest_floor >= self.agent.current_floor:
            return
        
        # Move agent between floors
        moved = self.agent.building.move_agent_between_floors(
            self.agent,
            self.agent.current_floor,
            dest_floor,
            stairwell.stair_id
        )
        
        if moved:
            # Recalculate path on new floor
            self.agent.path = self.agent.pathplanner.compute_path()
            logger.info(f"Agent moved to floor {dest_floor}, new path length: {len(self.agent.path)}")
    
    def _add_trail(self) -> None:
        """Add current spot to movement trail for visualization."""
        if self.agent.spot is not self._last_trail_spot:
            self.trail.append(self.agent.spot)
            self._last_trail_spot = self.agent.spot
    
    def reset(self) -> None:
        """Reset movement state (called on simulation reset)."""
        self.move_timer = 0.0
        self.current_angle = 0.0
        self.trail.clear()
        self._last_trail_spot = None


class AgentState:
    """
    Manages agent behavioral state machine.
    
    States:
    - IDLE: Agent hasn't detected danger yet
    - REACTION: Agent detected smoke, waiting before moving (reaction time)
    - MOVING: Agent is actively evacuating
    """
    
    def __init__(self, agent: "Agent") -> None:
        """
        Initialize state manager.
        
        Args:
            agent: Parent Agent object
        """
        self.agent = agent
        self.state = "IDLE"
        self.reaction_time = 2.0  # seconds
        self.reaction_timer = 0.0

    def _should_start_reaction(self) -> bool:
        """
        Decide when the agent should leave IDLE.

        Reacts when smoke is detected anywhere within the agent's vision cone.
        The smoke_detected flag is set by vision.update_memory() which scans
        the full visible radius (base 20 cells, reduced by local smoke).
        """
        return self.agent.smoke_detected
    
    def update(self, dt: float) -> str:
        """
        Update agent state based on perception and time.
        
        Args:
            dt: Delta time since last update (seconds)
            
        Returns:
            Current state after update
        """
        if self.state == "IDLE":
            # Start reaction only when local danger reaches the agent.
            if self._should_start_reaction():
                self.state = "REACTION"
                self.reaction_timer = self.reaction_time
                logger.debug("Local danger detected, entering REACTION state")
        
        elif self.state == "REACTION":
            # Count down reaction time
            self.reaction_timer -= dt
            if self.reaction_timer <= 0:
                self.state = "MOVING"
                logger.debug(f"Reaction time complete, entering MOVING state")
        
        # MOVING state doesn't transition, agent stays in this state
        
        return self.state
    
    def is_moving(self) -> bool:
        """Check if agent is in MOVING state."""
        return self.state == "MOVING"
    
    def is_idle(self) -> bool:
        """Check if agent is in IDLE state."""
        return self.state == "IDLE"
    
    def is_reacting(self) -> bool:
        """Check if agent is in REACTION state."""
        return self.state == "REACTION"
    
    def reset(self) -> None:
        """Reset state to IDLE."""
        self.state = "IDLE"
        self.reaction_timer = 0.0
