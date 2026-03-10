"""AgentMovement - Handles physical movement and damage for agents.
"""
import math
import logging
import random
from collections import deque
from typing import Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from core.agent.agent import Agent
    from core.spot import Spot

from utils.utilities import StairwellIDGenerator, rTemp

logger = logging.getLogger(__name__)

# Physical constants
# FED toxic: agent is incapacitated when fed_toxic >= 1.0
# Fractional dose per second at smoke = 1.0 (calibrated so heavy continuous
# smoke incapacitates in ~3 minutes, matching empirical corridor evacuation data).
FED_TOXIC_RATE_PER_SMOKE    = 1.0 / 180.0   # dose/s at smoke = 1.0

# FED thermal: agent is incapacitated when fed_thermal >= 1.0
# Above 60 °C convective heat causes pain in ~4 min; above 120 °C in < 30 s.
# We model this as an exponential: rate = exp((T - T_thresh) / T_scale) / T_ref
FED_THERMAL_THRESH_C        = 60.0           # °C — onset of thermal stress
FED_THERMAL_SCALE_C         = 30.0           # °C — e-folding scale
FED_THERMAL_REF_S           = 240.0          # s — time to incapacitate at threshold

# Non-monotonic temperature–speed curve
# Speed peaks at TEMP_BOOST_THRESHOLD, then falls.
TEMP_BOOST_THRESHOLD_C      = 60.0           # °C — speed maximum
TEMP_SPEED_DROP_SCALE_C     = 40.0           # °C — e-folding for drop above threshold
SPEED_BOOST_FACTOR          = 1.35           # peak multiplier vs normal (panic effect)
SPEED_FLOOR_FACTOR          = 0.20           # minimum fraction of normal speed

# Stress accumulation
STRESS_SMOKE_WEIGHT         = 0.6            # contribution per unit smoke
STRESS_HEAT_WEIGHT          = 0.004          # contribution per °C above threshold
STRESS_FIRE_PROXIMITY_WEIGHT= 0.25           # contribution per nearby fire cell
STRESS_DECAY_RATE           = 0.05           # stress lost per second in safe area
STRESS_IMPAIR_THRESHOLD     = 0.70           # above this, cognition is impaired
STRESS_MAX                  = 1.0

# Fire proximity avoidance
FIRE_AVOIDANCE_RADIUS_CELLS = 3              # cells at which repulsion begins
FIRE_AVOIDANCE_PEAK_FORCE   = 2.0            # extra path cost per adjacent fire cell

# Vulnerability profiles  {name: (fed_scale, speed_scale)}
# fed_scale  > 1 → accumulates dose faster (more vulnerable)
# speed_scale < 1 → slower base walking speed
VULNERABILITY_PROFILES = {
    "adult_fit":     (1.0,  1.0),
    "adult_average": (1.15, 0.90),
    "elderly":       (1.50, 0.65),
    "child":         (1.30, 0.75),
    "injured":       (1.80, 0.50),
}


class AgentMovement:
    """
    Handles physical movement and environmental damage.

    Core additions vs original:
    - FED accumulators (fed_toxic, fed_thermal) → incapacitation at 1.0
    - Non-monotonic temperature speed curve
    - Stress variable with feedback into behaviour
    - Vulnerability profile (age/condition)
    - Fire proximity avoidance force
    """

    def __init__(self, agent: "Agent", vulnerability: str = "adult_average") -> None:
        """
        Args:
            agent: Parent Agent object.
            vulnerability: Key from VULNERABILITY_PROFILES.
        """
        self.agent = agent
        self.move_timer = 0.0
        self.current_angle = 0.0

        # Trail tracking
        self.trail: deque = deque(maxlen=15)
        self._last_trail_spot: Optional["Spot"] = None

        # Temperature config (global singleton)
        self.temp_config = rTemp()

        # ---- FED accumulators ----------------------------------------
        # Both in range [0.0, ∞); incapacitation when either >= 1.0.
        self.fed_toxic: float = 0.0       # cumulative toxic dose (smoke / CO proxy)
        self.fed_thermal: float = 0.0     # cumulative thermal dose (convective heat)
        self.incapacitated: bool = False  # latched True once FED >= 1.0

        # ---- Stress variable -----------------------------------------
        # Range [0.0, 1.0].  Updated each damage tick from local hazard levels.
        self.stress: float = 0.0

        # ---- Precomputed fire avoidance cost grid -------------------------
        # Rebuilt lazily whenever known_fire changes (flagged by vision system).
        # Avoids recomputing inverse-square repulsion inside the A* inner loop.
        rows = agent.rows
        self._fire_avoid_grid: np.ndarray = np.zeros((rows, rows), dtype=np.float32)
        self._fire_avoid_dirty: bool = True  # force build on first use

        # ---- Vulnerability profile -----------------------------------
        profile = VULNERABILITY_PROFILES.get(vulnerability, VULNERABILITY_PROFILES["adult_average"])
        self.fed_scale: float   = profile[0]   # multiplies FED accumulation rate
        self.speed_scale: float = profile[1]   # multiplies base walking speed
        self.vulnerability_name: str = vulnerability

    # Speed calculation
    def get_move_interval(self) -> float:
        """
        Calculate time required to move one cell.

        Changes vs original:
        - Non-monotonic temperature effect: speed rises toward 60 °C then falls.
        - FED-based speed penalty: incapacitated agents shuffle at floor speed.
        - Stress slows agents once above STRESS_IMPAIR_THRESHOLD.
        - Per-agent vulnerability speed_scale applied.

        Returns:
            Seconds per cell.
        """
        temp_c   = self.agent.spot.temperature
        smoke    = self.agent.spot.smoke
        cell_size_m = max(self.temp_config.CELL_SIZE_M, 0.5)

        # --- Base speed from smoke / visibility (original three-tier model) ---
        if smoke < 0.13:
            base_speed = 3.67
        elif smoke < 0.5:
            base_speed = 0.96
        else:
            base_speed = 0.64

        # --- Non-monotonic temperature modifier ----------------------------
        if temp_c <= TEMP_BOOST_THRESHOLD_C:
            # Linear ramp from 1.0 at ambient to SPEED_BOOST_FACTOR at threshold
            t_frac = max(0.0, temp_c - 25.0) / max(TEMP_BOOST_THRESHOLD_C - 25.0, 1.0)
            temp_modifier = 1.0 + t_frac * (SPEED_BOOST_FACTOR - 1.0)
        else:
            # Exponential decay above threshold, floor at SPEED_FLOOR_FACTOR
            excess = temp_c - TEMP_BOOST_THRESHOLD_C
            decay  = math.exp(-excess / TEMP_SPEED_DROP_SCALE_C)
            temp_modifier = max(
                SPEED_FLOOR_FACTOR,
                SPEED_BOOST_FACTOR * decay
            )

        # --- FED incapacitation penalty ------------------------------------
        # Once FED reaches 0.5 the agent starts to slow; at 1.0 (incapacitated)
        # speed is at floor level.
        fed_penalty = 1.0
        max_fed = max(self.fed_toxic, self.fed_thermal)
        if max_fed > 0.5:
            # Linear interpolation: 1.0 at fed=0.5, SPEED_FLOOR_FACTOR at fed=1.0
            fed_frac  = (max_fed - 0.5) / 0.5
            fed_penalty = 1.0 - fed_frac * (1.0 - SPEED_FLOOR_FACTOR)
            fed_penalty = max(SPEED_FLOOR_FACTOR, fed_penalty)

        # --- Stress cognitive impairment penalty ---------------------------
        stress_penalty = 1.0
        if self.stress > STRESS_IMPAIR_THRESHOLD:
            excess_stress = (self.stress - STRESS_IMPAIR_THRESHOLD) / (1.0 - STRESS_IMPAIR_THRESHOLD)
            stress_penalty = 1.0 - excess_stress * 0.25   # up to 25 % slowdown

        # --- Combine all factors -------------------------------------------
        effective_speed = (
            base_speed
            * temp_modifier
            * fed_penalty
            * stress_penalty
            * self.speed_scale                    # vulnerability
            * self.temp_config.BASE_SPEED_M_S     # user slider
        )
        effective_speed = max(0.01, effective_speed)
        return cell_size_m / effective_speed

    # Damage / FED update
    def apply_damage(self, dt: float) -> None:
        """
        Update FED accumulators and derive health from them.

        Changes vs original:
        - Smoke damage is now accumulated as FED_toxic rather than being
          applied as an immediate HP deduction.  This creates physiological
          debt that persists after the agent leaves the smoke.
        - Thermal FED is computed from an exponential rate above 60 °C.
        - Health is derived from the worse of the two FED values so the
          panel still shows a meaningful HP bar.
        - Instant death from direct fire contact is retained.
        - Stress is updated here from the same hazard signals.
        """
        # Instant death from direct fire
        if self.agent.spot.is_fire():
            self.agent.health = 0
            self.fed_toxic   = 1.0
            self.fed_thermal = 1.0
            self.incapacitated = True
            return

        smoke = self.agent.spot.smoke
        temp_c = self.agent.spot.temperature

        # ---- Toxic FED (smoke / CO proxy) --------------------------------
        # Rate scales linearly with smoke density, modified by vulnerability.
        toxic_rate = smoke * FED_TOXIC_RATE_PER_SMOKE * self.fed_scale
        self.fed_toxic = min(self.fed_toxic + toxic_rate * dt, 2.0)  # cap at 2 for sanity

        # ---- Thermal FED (convective heat) --------------------------------
        if temp_c > FED_THERMAL_THRESH_C:
            excess_temp    = temp_c - FED_THERMAL_THRESH_C
            thermal_rate   = (
                math.exp(excess_temp / FED_THERMAL_SCALE_C)
                / FED_THERMAL_REF_S
                * self.fed_scale
            )
            self.fed_thermal = min(self.fed_thermal + thermal_rate * dt, 2.0)

        # ---- Incapacitation check ----------------------------------------
        if self.fed_toxic >= 1.0 or self.fed_thermal >= 1.0:
            self.incapacitated = True

        # ---- Derive health from FED --------------------------------------
        # Map worst FED to health: 0 FED → 100 HP, 1.0 FED → 0 HP.
        # We use a slightly concave curve so health drops slowly at first
        # then rapidly as the agent nears incapacitation, which looks more
        # realistic on the panel.
        worst_fed = min(max(self.fed_toxic, self.fed_thermal), 1.0)
        # Convex mapping: health = 100 * (1 - fed^0.7)
        self.agent.health = max(0.0, 100.0 * (1.0 - worst_fed ** 0.7))

        if self.incapacitated:
            self.agent.health = 0

        # Stress update (some kind of damage hence inside apply_damage, but not directly tied to health)
        self._update_stress(dt, smoke, temp_c)

    def _update_stress(self, dt: float, smoke: float, temp_c: float) -> None:
        """
        Update the agent's stress level from current hazard exposure.

        Stress contributions:
        - Smoke density (visibility loss is psychologically threatening)
        - Temperature above threshold (radiant heat discomfort)
        - Number of fire cells visible within proximity radius

        Stress decays naturally in the absence of hazards.
        """
        stress_input = 0.0

        # Smoke contribution
        stress_input += smoke * STRESS_SMOKE_WEIGHT

        # Heat contribution (above threshold only)
        if temp_c > FED_THERMAL_THRESH_C:
            stress_input += (temp_c - FED_THERMAL_THRESH_C) * STRESS_HEAT_WEIGHT

        # Fire proximity contribution
        fire_count = self._count_nearby_fire_cells(FIRE_AVOIDANCE_RADIUS_CELLS)
        stress_input += fire_count * STRESS_FIRE_PROXIMITY_WEIGHT

        # Clamp input
        stress_input = min(stress_input, STRESS_MAX)

        # Exponential approach toward stress_input, decay when input < current
        if stress_input > self.stress:
            self.stress = min(STRESS_MAX, self.stress + (stress_input - self.stress) * 2.0 * dt)
        else:
            self.stress = max(0.0, self.stress - STRESS_DECAY_RATE * dt)

    def _count_nearby_fire_cells(self, radius: int) -> int:
        """Count known fire cells within radius of the agent's current position."""
        count  = 0
        rows   = self.agent.rows
        cr, cc = self.agent.spot.row, self.agent.spot.col
        r2     = radius * radius

        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if dr * dr + dc * dc > r2:
                    continue
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < rows and 0 <= nc < rows:
                    if self.agent.known_fire[nr, nc]:
                        count += 1
        return count

    # Fire avoidance force (for pathfinder cost injection)
    def mark_fire_avoid_dirty(self) -> None:
        """Signal that known_fire has changed and the cost grid needs rebuild."""
        self._fire_avoid_dirty = True

    def _rebuild_fire_avoid_grid(self) -> None:
        """
        Precompute inverse-square fire repulsion cost for every cell.

        Called at most once per vision update cycle (not per A* node).
        Uses vectorised numpy operations: for each known fire cell, adds an
        inverse-square cost bowl centred on that cell into the grid.
        """
        rows   = self.agent.rows
        result = np.zeros((rows, rows), dtype=np.float32)
        R      = FIRE_AVOIDANCE_RADIUS_CELLS

        # Build a reusable distance kernel for the repulsion neighbourhood
        ks = 2 * R + 1
        kernel = np.zeros((ks, ks), dtype=np.float32)
        for dr in range(-R, R + 1):
            for dc in range(-R, R + 1):
                dist = math.sqrt(dr * dr + dc * dc)
                if dist < 1e-6:
                    dist = 1e-6
                kernel[dr + R, dc + R] = min(
                    FIRE_AVOIDANCE_PEAK_FORCE,
                    FIRE_AVOIDANCE_PEAK_FORCE / (dist * dist)
                )

        # Stamp the kernel onto every known fire cell
        fire_cells = [
            (r, c)
            for r in range(rows)
            for c in range(rows)
            if self.agent.known_fire[r, c]
        ]

        for fr, fc in fire_cells:
            r0, r1 = fr - R, fr + R + 1
            c0, c1 = fc - R, fc + R + 1
            # Clamp to grid bounds and compute corresponding kernel slice
            gr0 = max(r0, 0);  kr0 = gr0 - r0
            gr1 = min(r1, rows); kr1 = ks - (r1 - gr1)
            gc0 = max(c0, 0);  kc0 = gc0 - c0
            gc1 = min(c1, rows); kc1 = ks - (c1 - gc1)
            result[gr0:gr1, gc0:gc1] += kernel[kr0:kr1, kc0:kc1]

        self._fire_avoid_grid = result
        self._fire_avoid_dirty = False

    def fire_avoidance_cost(self, row: int, col: int) -> float:
        """
        Return precomputed fire avoidance cost for cell (row, col).

        Rebuilds the grid lazily if known_fire has changed since last call.
        O(1) lookup during A* — all heavy work is done in _rebuild once per
        vision update.

        Args:
            row, col: Cell coordinates to evaluate.

        Returns:
            Additional path cost (0.0 if no nearby fire).
        """
        if self._fire_avoid_dirty:
            self._rebuild_fire_avoid_grid()
        return float(self._fire_avoid_grid[row, col])

    # Movement
    def move_toward_goal(self, dt: float) -> bool:
        """
        Move agent toward next step in path.

        Change: incapacitated agents cannot move.

        Returns:
            True if agent reached exit, False otherwise.
        """
        if self.agent.spot.is_end():
            return True

        # Incapacitated agents are immobile
        if self.incapacitated:
            return False

        self.move_timer += dt

        if self.move_timer < self.get_move_interval():
            return False

        self.move_timer = 0.0

        if not self.agent.path or len(self.agent.path) <= 1:
            return False

        next_node = self.agent.path[1]

        dx = next_node.x - self.agent.spot.x
        dy = next_node.y - self.agent.spot.y
        if dx != 0 or dy != 0:
            self.current_angle = math.degrees(math.atan2(-dy, dx)) - 90

        if next_node.is_stairwell and self.agent.building and self.agent.building.num_floors > 1:
            self._cross_stairwell(next_node)
            return False

        if not next_node.is_barrier() and not next_node.is_fire():
            self.agent.spot = next_node
            self.agent.path.pop(0)
            self._add_trail()
        else:
            self.agent.path = self.agent.pathplanner.compute_path()

        return False

    # Stairwell traversal (unchanged logic, kept here for completeness)
    def _cross_stairwell(self, stairwell: "Spot") -> None:
        if not self.agent.building or stairwell.stair_id is None:
            logger.warning("Stairwell crossing attempted without valid building or stair_id")
            return

        connected_floors = StairwellIDGenerator.get_connected_floors(stairwell.stair_id)
        if not connected_floors:
            return

        candidate_floors = [f for f in connected_floors if f != self.agent.current_floor]
        if not candidate_floors:
            return

        floors_with_exits = sorted(
            [f for f in candidate_floors if bool(self.agent.building.get_floor(f).exits)]
        )

        if floors_with_exits:
            dest_floor = floors_with_exits[0]
        else:
            lower_candidates = sorted([f for f in candidate_floors if f < self.agent.current_floor])
            dest_floor = lower_candidates[0] if lower_candidates else sorted(candidate_floors)[0]

        if dest_floor >= self.agent.current_floor:
            return

        moved = self.agent.building.move_agent_between_floors(
            self.agent, self.agent.current_floor, dest_floor, stairwell.stair_id
        )

        if moved:
            self.agent.path = self.agent.pathplanner.compute_path()
            logger.debug(f"Agent moved to floor {dest_floor}, path length: {len(self.agent.path)}")

    # Trail
    def _add_trail(self) -> None:
        if self.agent.spot is not self._last_trail_spot:
            self.trail.append(self.agent.spot)
            self._last_trail_spot = self.agent.spot

    # Reset
    def reset(self) -> None:
        """Reset movement state for a new simulation run."""
        self.move_timer    = 0.0
        self.current_angle = 0.0
        self.trail.clear()
        self._last_trail_spot = None

        # Reset FED and stress
        self.fed_toxic     = 0.0
        self.fed_thermal   = 0.0
        self.incapacitated = False
        self.stress        = 0.0

        # Reset fire avoidance grid
        self._fire_avoid_grid[:] = 0.0
        self._fire_avoid_dirty = True


# AgentState — unchanged except it now also checks incapacitation
class AgentState:
    """
    Manages agent behavioral state machine.

    States:
    - IDLE:     Agent hasn't detected danger yet.
    - REACTION: Agent detected smoke; waiting before moving (reaction time).
    - MOVING:   Agent is actively evacuating.

    Addition: high stress can shorten reaction time (panic).
    """

    def __init__(self, agent: "Agent") -> None:
        self.agent = agent
        self.state = "IDLE"
        self.reaction_time  = 2.0   # seconds (base)
        self.reaction_timer = 0.0

    def _should_start_reaction(self) -> bool:
        return self.agent.smoke_detected or self.agent.vision.detect_imminent_danger(
            max_distance_cells=int(
                self.agent.vision.compute_visibility_radius() / self.agent.grid.cell_size
            )
        )

    def _effective_reaction_time(self) -> float:
        """
        High stress shortens the pre-movement reaction delay (panic effect).

        At stress = 0: full reaction_time.
        At stress = 1: 30 % of reaction_time (agent reacts almost immediately).
        """
        stress = self.agent.movement.stress
        min_fraction = 0.30
        fraction = 1.0 - stress * (1.0 - min_fraction)
        return self.reaction_time * fraction

    def update(self, dt: float) -> str:
        if self.state == "IDLE":
            if self._should_start_reaction():
                self.state = "REACTION"
                self.reaction_timer = self._effective_reaction_time()
                logger.debug("Danger detected, entering REACTION (timer=%.2fs)", self.reaction_timer)

        elif self.state == "REACTION":
            self.reaction_timer -= dt
            if self.reaction_timer <= 0:
                self.state = "MOVING"
                logger.debug("Reaction complete, entering MOVING")

        return self.state

    def is_moving(self) -> bool:
        return self.state == "MOVING"

    def is_idle(self) -> bool:
        return self.state == "IDLE"

    def is_reacting(self) -> bool:
        return self.state == "REACTION"

    def reset(self) -> None:
        self.state          = "IDLE"
        self.reaction_timer = 0.0
