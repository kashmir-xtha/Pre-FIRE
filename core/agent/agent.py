"""
Refactored Agent class using specialized submodules.

"""

import logging
import math
import random
import pygame
import numpy as np
from typing import List, Optional, TYPE_CHECKING

from core.agent.agent_vision import AgentVision
from core.agent.agent_pathplanner import AgentPathplanner
from core.agent.agent_movement import AgentMovement, AgentState, VULNERABILITY_PROFILES
from utils.utilities import Color, StairwellIDGenerator, rTemp, resource_path

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot
    from core.building import Building

logger = logging.getLogger(__name__)


class SparseFireGrid:
    """
    Memory-efficient sparse representation of fire locations.

    Uses a set instead of a 60x60 boolean grid to save ~3.6 KB per agent.
    Provides array-like __getitem__ / __setitem__ for compatibility.
    """

    def __init__(self, rows: int) -> None:
        self.rows = rows
        self._fire_locations: set = set()

    def __getitem__(self, key: tuple) -> bool:
        if isinstance(key, tuple) and len(key) == 2:
            return key in self._fire_locations
        raise TypeError(f"Invalid index type: {type(key)}")

    def __setitem__(self, key: tuple, value: bool) -> None:
        if isinstance(key, tuple) and len(key) == 2:
            if value:
                self._fire_locations.add(key)
            else:
                self._fire_locations.discard(key)
        else:
            raise TypeError(f"Invalid index type: {type(key)}")

    def fill(self, value: bool) -> None:
        if not value:
            self._fire_locations.clear()

    def any(self) -> bool:
        return len(self._fire_locations) > 0

    def __len__(self) -> int:
        return len(self._fire_locations)

    def reset(self) -> None:
        self._fire_locations.clear()


class Agent:
    """
    Represents an evacuee in the fire simulation.

    Delegates to specialized submodules:
    - AgentVision:      Perception and environmental awareness
    - AgentPathplanner: Pathfinding and route planning
    - AgentMovement:    Physical movement, FED damage, stress
    - AgentState:       Behavioral state machine (IDLE/REACTION/MOVING)

    New public API:
        agent.fed_toxic       – cumulative toxic dose  [0, 2]
        agent.fed_thermal     – cumulative thermal dose [0, 2]
        agent.stress          – current stress level    [0, 1]
        agent.incapacitated   – True once FED >= 1.0
        agent.vulnerability   – profile name string
    """

    def __init__(
        self,
        grid: "Grid",
        start_spot: "Spot",
        floor: int = 0,
        building: Optional["Building"] = None,
        vulnerability: str = "adult_average",
    ) -> None:
        """
        Args:
            grid:          The Grid the agent occupies.
            start_spot:    Starting Spot on the grid.
            floor:         Which floor of the building (default 0).
            building:      Parent Building object (multi-floor navigation).
            vulnerability: Key from VULNERABILITY_PROFILES – controls FED
                           accumulation rate and base walking speed.
        """
        # Core attributes
        self.grid    = grid
        self.spot    = start_spot
        self.rows    = grid.rows
        self.health  = 100.0
        self.alive   = True
        self.path:  List["Spot"] = []
        self.path_show   = True
        self.current_floor = floor
        self.building    = building

        # Memory systems
        self.known_smoke = np.full((self.rows, self.rows), -1.0)
        self.known_fire  = SparseFireGrid(self.rows)
        self.known_temp  = np.full((self.rows, self.rows), 20.0)

        # Precompute barrier adjacency for pathfinding wall-following
        self.barrier_adjacent = self._compute_barrier_adjacency()

        # Smoke detection flag (set by vision system)
        self.smoke_detected = False

        # Validate vulnerability profile, fall back gracefully
        if vulnerability not in VULNERABILITY_PROFILES:
            logger.warning(
                "Unknown vulnerability profile %r, using 'adult_average'", vulnerability
            )
            vulnerability = "adult_average"
        self._vulnerability = vulnerability

        # Initialise submodules
        self.vision        = AgentVision(self)
        self.pathplanner   = AgentPathplanner(self)
        self.movement      = AgentMovement(self, vulnerability=vulnerability)
        self.state_manager = AgentState(self)

        # Graphics
        self._initialize_graphics()

    # FED / stress properties (delegate to AgentMovement)
    @property
    def fed_toxic(self) -> float:
        """Cumulative toxic FED in [0, 2]. Incapacitation at >= 1.0."""
        return self.movement.fed_toxic

    @property
    def fed_thermal(self) -> float:
        """Cumulative thermal FED in [0, 2]. Incapacitation at >= 1.0."""
        return self.movement.fed_thermal

    @property
    def stress(self) -> float:
        """Current stress level in [0, 1]."""
        return self.movement.stress

    @property
    def incapacitated(self) -> bool:
        """True once either FED accumulator reaches 1.0."""
        return self.movement.incapacitated

    @property
    def vulnerability(self) -> str:
        """Vulnerability profile name."""
        return self._vulnerability

    # Internal helpers
    def _compute_barrier_adjacency(self) -> np.ndarray:
        rows = self.rows
        adj  = np.zeros((rows, rows), dtype=np.uint8)
        for r in range(rows):
            for c in range(rows):
                count = 0
                for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < rows:
                        if self.grid.grid[nr][nc].is_barrier():
                            count += 1
                adj[r, c] = count
        return adj

    def _initialize_graphics(self) -> None:
        self._vision_surf = None
        self._trail_surf  = None
        try:
            agent_img_path = resource_path("data/agent.png")
            img = pygame.image.load(agent_img_path).convert_alpha()
            draw_size = int(self.grid.cell_size * 2.2)
            self.base_image = pygame.transform.scale(img, (draw_size, draw_size))
        except Exception as e:
            logger.error("Failed to load agent image: %s", e)
            self.base_image = None

    @property
    def vision_surf(self) -> pygame.Surface:
        if self._vision_surf is None:
            grid_px = self.grid.rows * self.grid.cell_size
            self._vision_surf = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
        return self._vision_surf

    @property
    def trail_surf(self) -> pygame.Surface:
        if self._trail_surf is None:
            grid_px = self.grid.rows * self.grid.cell_size
            self._trail_surf = pygame.Surface((grid_px, grid_px), pygame.SRCALPHA)
        return self._trail_surf

    # Main update loop
    def update(self, dt: float) -> bool:
        """
        Update agent state each frame.

        Returns:
            True if agent reached exit, False otherwise.
        """
        if not self.alive:
            return False
        
        if self.spot.is_end():
            return True
        

        # Perception and damage always run (even pre-movement)
        self.vision.update_memory(dt)
        self.movement.apply_damage(dt)

        # Death check — covers both FED incapacitation and direct fire
        if self.health <= 0 or self.movement.incapacitated:
            self.health = 0
            self.alive  = False
            return False

        # Behavioural state machine
        self.state_manager.update(dt)

        if not self.state_manager.is_moving():
            return False

        if self.spot.is_end():
            return True

        self.pathplanner.update_path(dt)
        return self.movement.move_toward_goal(dt)

    # Path planning
    def best_path(self) -> List["Spot"]:
        return self.pathplanner.compute_path()

    def compute_visibility_radius(self) -> float:
        return self.vision.compute_visibility_radius()

    # State properties (delegating to state_manager)
    @property
    def state(self) -> str:
        return self.state_manager.state

    @state.setter
    def state(self, value: str) -> None:
        self.state_manager.state = value

    @property
    def reaction_time(self) -> float:
        return self.state_manager.reaction_time

    @reaction_time.setter
    def reaction_time(self, value: float) -> None:
        self.state_manager.reaction_time = value

    @property
    def reaction_timer(self) -> float:
        return self.state_manager.reaction_timer

    @reaction_timer.setter
    def reaction_timer(self, value: float) -> None:
        self.state_manager.reaction_timer = value

    @property
    def trail(self):
        return self.movement.trail

    @property
    def current_angle(self) -> float:
        return self.movement.current_angle

    @current_angle.setter
    def current_angle(self, value: float) -> None:
        self.movement.current_angle = value

    # Reset
    def reset(self) -> None:
        """Reset agent to initial state (called by Simulation.reset)."""
        self.health = 100.0
        self.alive  = True
        self.path   = []

        self.known_smoke.fill(-1.0)
        self.known_fire.fill(False)
        self.known_temp.fill(20.0)

        if self.grid.start:
            self.spot = self.grid.start[0]

        self.smoke_detected = False

        self.vision.reset()
        self.pathplanner.reset()
        self.movement.reset()      # also resets FED, stress, incapacitated
        self.state_manager.reset()

    # Rendering
    def draw(self, win: pygame.Surface, tint_color = None) -> None:
        cell_size = self.grid.cell_size
        cx = int(self.spot.x + cell_size // 2)
        cy = int(self.spot.y + cell_size // 2)

        self._draw_trail(win, cell_size)
        self._draw_vision_cone(win, cx, cy)
        self._draw_sprite(win, cx, cy, tint_color)

    def _draw_trail(self, win: pygame.Surface, cell_size: int) -> None:
        trail_list = list(self.movement.trail)
        n = len(trail_list)
        if n <= 0:
            return

        expected_px = self.grid.rows * cell_size
        if self.trail_surf.get_width() != expected_px:
            self._trail_surf = pygame.Surface((expected_px, expected_px), pygame.SRCALPHA)

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
                dot_radius,
            )

        win.blit(self.trail_surf, (0, 0))

    def _draw_vision_cone(self, win: pygame.Surface, cx: int, cy: int) -> None:
        vis_radius   = self.vision.compute_visibility_radius()
        cone_points  = [(cx, cy)]
        start_angle  = math.radians(-self.movement.current_angle - 135)
        end_angle    = math.radians(-self.movement.current_angle - 45)

        for i in range(13):
            angle = start_angle + (end_angle - start_angle) * (i / 12)
            cone_points.append((
                cx + math.cos(angle) * vis_radius,
                cy + math.sin(angle) * vis_radius,
            ))

        self.vision_surf.fill((0, 0, 0, 0))
        pygame.draw.polygon(self.vision_surf, (180, 210, 255, 160), cone_points)
        win.blit(self.vision_surf, (0, 0))

    def _draw_sprite(self, win: pygame.Surface, cx: int, cy: int, tint_color=None) -> None:
        """
        Draw agent sprite with FED-based colour feedback.

        Tint progression:
        - FED in [0, 0.33):  no tint (healthy)
        - FED in [0.33, 0.66): yellow tint (moderate exposure)
        - FED in [0.66, 1.0]:  red tint   (near incapacitation)
        Incapacitated agents are drawn fully red.
        """
        if not self.base_image:
            return

        img    = self.base_image.copy()
        if tint_color:
                img.fill(tint_color, special_flags=pygame.BLEND_RGBA_MULT)

        max_fed = max(self.movement.fed_toxic, self.movement.fed_thermal)

        if self.movement.incapacitated:
            img.fill((255, 180, 180, 255), special_flags=pygame.BLEND_MULT)
        elif max_fed >= 0.66:
            # Red tint — near incapacitation
            img.fill((255, 200, 200, 255), special_flags=pygame.BLEND_MULT)
        elif max_fed >= 0.33:
            # Yellow tint — notable exposure
            img.fill((255, 255, 180, 255), special_flags=pygame.BLEND_MULT)
        # else: no tint

        rotated = pygame.transform.rotate(img, self.movement.current_angle + 180)
        win.blit(rotated, rotated.get_rect(center=(cx, cy)).topleft)
