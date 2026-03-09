"""Test agent state machine and damage mechanics."""
import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import Agent
from core.agent.agent_movement import AgentState
from core.grid import Grid
from core.spot import Spot
from environment.materials import MATERIALS, material_id
from utils.utilities import fire_constants


class TestAgentStateMachine:
    """Test IDLE -> REACTION -> MOVING state transitions."""

    @pytest.fixture
    def agent(self):
        """Create an agent for state testing."""
        grid = Grid(rows=10, width=400, floor=0)
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        grid.ensure_material_cache()
        agent = Agent(grid, grid.grid[5][5], floor=0)
        return agent

    def test_starts_idle(self, agent):
        """Agent should start in IDLE state."""
        assert agent.state == "IDLE"
        assert agent.state_manager.is_idle()

    def test_idle_to_reaction_on_smoke(self, agent):
        """Agent should enter REACTION when smoke is detected."""
        agent.smoke_detected = True
        agent.state_manager.update(dt=0.1)
        assert agent.state == "REACTION"
        assert agent.state_manager.is_reacting()

    def test_stays_idle_without_smoke(self, agent):
        """Agent should stay IDLE if no danger detected."""
        agent.smoke_detected = False
        for _ in range(10):
            agent.state_manager.update(dt=0.1)
        assert agent.state == "IDLE"

    def test_reaction_to_moving_after_timer(self, agent):
        """Agent should transition to MOVING after reaction time expires."""
        agent.smoke_detected = True
        agent.state_manager.update(dt=0.1)  # -> REACTION
        assert agent.state == "REACTION"

        # Tick through the full reaction time (default 2.0s)
        for _ in range(25):
            agent.state_manager.update(dt=0.1)

        assert agent.state == "MOVING"
        assert agent.state_manager.is_moving()

    def test_reaction_timer_decrements(self, agent):
        """Reaction timer should count down each update."""
        agent.smoke_detected = True
        agent.state_manager.update(dt=0.1)  # -> REACTION

        timer_before = agent.state_manager.reaction_timer
        agent.state_manager.update(dt=0.5)
        timer_after = agent.state_manager.reaction_timer

        assert timer_after < timer_before

    def test_moving_state_persists(self, agent):
        """MOVING state should not transition to anything else."""
        agent.state = "MOVING"
        for _ in range(20):
            agent.state_manager.update(dt=0.1)
        assert agent.state == "MOVING"

    def test_state_reset(self, agent):
        """State reset should return to IDLE."""
        agent.state = "MOVING"
        agent.state_manager.reset()
        assert agent.state == "IDLE"
        assert agent.state_manager.reaction_timer == 0.0


class TestAgentDamage:
    """Test agent damage from environmental hazards."""

    @pytest.fixture
    def agent_on_grid(self):
        """Create agent on a grid with an exit."""
        grid = Grid(rows=10, width=400, floor=0)
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        grid.ensure_material_cache()
        agent = Agent(grid, grid.grid[5][5], floor=0)
        return agent, grid

    def test_fire_instant_death(self, agent_on_grid):
        """Agent on a fire cell should die instantly."""
        agent, grid = agent_on_grid
        agent.spot.set_on_fire(initial_temp=800.0)
        agent.movement.apply_damage(dt=0.1)
        assert agent.health == 0

    def test_smoke_damage(self, agent_on_grid):
        """Agent in heavy smoke should take damage."""
        agent, grid = agent_on_grid
        agent.spot._smoke = 0.8
        initial_health = agent.health

        agent.movement.apply_damage(dt=1.0)
        assert agent.health < initial_health

    def test_heat_damage_above_threshold(self, agent_on_grid):
        """Agent in high temperature should take damage."""
        agent, grid = agent_on_grid
        agent.spot.set_temperature(200.0)  # Well above 50°C threshold
        initial_health = agent.health

        agent.movement.apply_damage(dt=1.0)
        assert agent.health < initial_health

    def test_no_damage_at_ambient(self, agent_on_grid):
        """Agent at ambient temperature with no smoke should take no damage."""
        agent, grid = agent_on_grid
        initial_health = agent.health
        agent.movement.apply_damage(dt=1.0)
        assert agent.health == initial_health

    def test_health_clamps_to_zero(self, agent_on_grid):
        """Health should not go below zero."""
        agent, grid = agent_on_grid
        agent.health = 1.0
        agent.spot._smoke = 1.0
        agent.spot.set_temperature(500.0)

        agent.movement.apply_damage(dt=10.0)
        assert agent.health == 0

    def test_agent_dies_when_health_zero(self, agent_on_grid):
        """Agent update should set alive=False when health reaches 0."""
        agent, grid = agent_on_grid
        agent.spot.set_on_fire(initial_temp=800.0)
        grid.update_np_arrays()

        # Full update cycle
        agent.update(dt=0.1)
        assert not agent.alive
        assert agent.health == 0

    def test_dead_agent_stops_updating(self, agent_on_grid):
        """Dead agent's update should return False immediately."""
        agent, _ = agent_on_grid
        agent.alive = False
        result = agent.update(dt=0.1)
        assert result is False
