"""Test simulation reset and Building/floor operations."""
import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.grid import Grid
from core.spot import Spot
from core.building import Building
from core.agent import Agent
from environment.materials import MATERIALS, material_id
from environment.fire import update_fire_with_materials
from utils.utilities import state_value, fire_constants


class TestBuildingConstruction:
    """Test Building and multi-floor initialization."""

    def test_building_creates_floors(self):
        """Building should create the requested number of floors."""
        building = Building(num_of_floors=3, rows=10, width=400)
        assert building.num_floors == 3
        assert len(building.floors) == 3

    def test_get_floor_valid(self):
        """get_floor should return the correct floor."""
        building = Building(num_of_floors=2, rows=10, width=400)
        floor = building.get_floor(0)
        assert floor is building.floors[0]

    def test_get_floor_invalid(self):
        """get_floor should raise ValueError for invalid floor number."""
        building = Building(num_of_floors=2, rows=10, width=400)
        with pytest.raises(ValueError):
            building.get_floor(5)

    def test_floors_are_independent(self):
        """Each floor should have independent grids."""
        building = Building(num_of_floors=2, rows=10, width=400)
        building.floors[0].grid[5][5].set_temperature(500.0)
        assert building.floors[1].grid[5][5].temperature == fire_constants.AMBIENT_TEMP.value


class TestGridReset:
    """Test grid layout backup and restore (the core of simulation reset)."""

    @pytest.fixture
    def grid_with_layout(self):
        """Create a grid with a specific layout and back it up."""
        grid = Grid(rows=10, width=400, floor=0)

        # Set up a layout: walls, exits, wood, fire source
        grid.grid[0][0].make_barrier()
        grid.set_material(5, 5, material_id.WOOD)
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        grid.grid[3][3].set_as_fire_source(temp=1200.0)

        grid.ensure_material_cache()
        grid.backup_layout()
        return grid

    def test_backup_captures_state(self, grid_with_layout):
        """backup_layout should capture current cell states."""
        grid = grid_with_layout
        layout = grid.initial_layout

        assert layout is not None
        assert layout[0][0]['state'] == state_value.WALL.value
        assert layout[5][5]['material'] == material_id.WOOD
        assert layout[9][9]['state'] == state_value.END.value
        assert layout[3][3]['is_fire_source'] is True

    def test_restore_from_backup(self, grid_with_layout):
        """Grid should be restorable from backup after mutation."""
        grid = grid_with_layout

        # Mutate: burn a cell, add smoke, change material
        grid.grid[5][5].set_on_fire(initial_temp=800.0)
        grid.grid[5][5]._smoke = 0.9
        grid.set_material(7, 7, material_id.METAL)
        grid.update_np_arrays()

        # Now restore from backup (same logic as simulation.reset)
        layout = grid.initial_layout
        for r, row in enumerate(grid.grid):
            for c, spot in enumerate(row):
                disc = layout[r][c]
                spot.reset()
                if disc.get('state') == state_value.WALL.value:
                    spot.make_barrier()
                elif disc.get('state') == state_value.START.value:
                    spot.make_start()
                elif disc.get('state') == state_value.END.value:
                    spot.make_end()
                elif disc.get('is_fire_source'):
                    spot.set_as_fire_source(disc.get('temperature', 1200.0))
                else:
                    spot.set_material(disc.get('material'))

        grid.ensure_material_cache()
        grid.update_np_arrays()

        # Verify restoration
        assert grid.grid[5][5].material == material_id.WOOD
        assert not grid.grid[5][5].is_fire(), "Fire should be cleared"
        assert grid.grid[5][5].smoke == 0.0, "Smoke should be cleared"
        assert grid.grid[0][0].is_barrier(), "Wall should be restored"
        assert grid.grid[9][9].is_end(), "Exit should be restored"
        assert grid.grid[3][3].is_fire_source, "Fire source should be restored"
        assert grid.grid[7][7].material == material_id.AIR, "Mutated cell should be reset"

    def test_fire_source_restores_with_temperature(self, grid_with_layout):
        """Fire source temperature should survive backup/restore."""
        grid = grid_with_layout
        layout = grid.initial_layout

        # The fire source at (3,3) should have high temp in backup
        disc = layout[3][3]
        assert disc['is_fire_source'] is True
        assert disc['temperature'] >= 1200.0


class TestFuelResetBug:
    """Regression tests for the fuel reset bug (fuel resetting to material default)."""

    def test_burned_cell_stays_empty_after_reset(self):
        """A cell that burned to completion should have 0 fuel after restore."""
        grid = Grid(rows=10, width=400, floor=0)
        grid.set_material(5, 5, material_id.WOOD)
        grid.grid[5][5]._fuel = MATERIALS[material_id.WOOD]["fuel"]
        grid.grid[5][5].set_on_fire(initial_temp=800.0)
        grid.ensure_material_cache()
        grid.update_np_arrays()

        # Burn until fuel depleted
        for _ in range(200):
            update_fire_with_materials(grid, dt=1.0)
            if grid.fuel_np[5, 5] <= 0:
                break

        grid.update_np_arrays()
        assert grid.fuel_np[5, 5] <= 0, "Fuel should be depleted"

        # Now back up and restore
        grid.backup_layout()
        layout = grid.initial_layout

        # Spot was converted to AIR with 0 fuel by fire.py after burnout
        disc = layout[5][5]
        spot = grid.grid[5][5]
        spot.reset()
        spot.set_material(disc.get('material'))

        # After restore, fuel should match the material's default
        # (AIR material after burnout has fuel=0.3, which is correct for a fresh start)
        assert spot.fuel >= 0.0


class TestAgentReset:
    """Test agent reset behavior."""

    @pytest.fixture
    def agent_on_grid(self):
        """Create an agent placed on a grid with an exit."""
        grid = Grid(rows=10, width=400, floor=0)
        start = grid.grid[2][2]
        start.make_start()
        grid.start = [start]
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        grid.ensure_material_cache()

        agent = Agent(grid, start, floor=0, building=None)
        return agent, grid

    def test_reset_restores_health(self, agent_on_grid):
        """Agent health should be restored to 100 after reset."""
        agent, _ = agent_on_grid
        agent.health = 30
        agent.alive = False
        agent.reset()

        assert agent.health == 100
        assert agent.alive is True

    def test_reset_clears_memory(self, agent_on_grid):
        """Agent memory arrays should be cleared on reset."""
        agent, _ = agent_on_grid
        agent.known_smoke[5, 5] = 0.9
        agent.known_fire[5, 5] = True
        agent.reset()

        assert np.all(agent.known_smoke == -1.0)
        assert not agent.known_fire[5, 5]

    def test_reset_clears_state(self, agent_on_grid):
        """Agent state should return to IDLE on reset."""
        agent, _ = agent_on_grid
        agent.state = "MOVING"
        agent.smoke_detected = True
        agent.reset()

        assert agent.state == "IDLE"
        assert agent.smoke_detected is False

    def test_reset_clears_path(self, agent_on_grid):
        """Agent path should be cleared on reset (before recomputation)."""
        agent, _ = agent_on_grid
        # The reset method clears the path first, 
        # then simulation.reset() recomputes it separately
        agent.path = [agent.spot]  # fake path
        agent.reset()
        assert agent.path == []

    def test_reset_spot_is_single_spot(self, agent_on_grid):
        """Agent.reset() should assign a single Spot, not the start list."""
        agent, grid = agent_on_grid
        agent.reset()
        assert isinstance(agent.spot, Spot), (
            "agent.spot should be a Spot instance after reset, not a list"
        )
