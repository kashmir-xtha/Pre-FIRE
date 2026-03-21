"""Tests for multi-floor Building logic."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.building import Building
from core.grid import Grid
from core.agent import Agent
from utils.stairwell_manager import StairwellIDGenerator


@pytest.fixture(autouse=True)
def reset_stairwells():
    """Ensure stairwell state is clean for every test."""
    StairwellIDGenerator.reset()
    yield
    StairwellIDGenerator.reset()


@pytest.fixture
def building():
    """2-floor, 10×10 building."""
    return Building(num_of_floors=2, rows=10, width=400)


@pytest.fixture
def building_3f():
    """3-floor building."""
    return Building(num_of_floors=3, rows=10, width=400)


class TestBuildingInit:
    """Building construction."""

    def test_floor_count(self, building):
        assert building.num_floors == 2
        assert len(building.floors) == 2

    def test_each_floor_is_grid(self, building):
        for f in building.floors:
            assert isinstance(f, Grid)

    def test_floors_are_independent_objects(self, building):
        assert building.floors[0] is not building.floors[1]

    def test_default_current_floor(self, building):
        assert building.current_floor == 0

    def test_get_floor_valid(self, building):
        assert building.get_floor(0) is building.floors[0]
        assert building.get_floor(1) is building.floors[1]

    def test_get_floor_invalid_raises(self, building):
        with pytest.raises(ValueError):
            building.get_floor(5)

    def test_metrics_initialized(self, building):
        m = building.metrics
        assert m["fire_cells"] == 0
        assert m["avg_smoke"] == 0
        assert m["avg_temp"] == 20


class TestFloorIndependence:
    """Each floor maintains its own fire/smoke/temp state."""

    def test_fire_on_one_floor_not_on_other(self, building):
        building.floors[0].grid[5][5].set_on_fire()
        building.floors[0].update_np_arrays()
        building.floors[1].update_np_arrays()
        assert building.floors[0].grid[5][5].is_fire()
        assert not building.floors[1].grid[5][5].is_fire()

    def test_smoke_on_one_floor_not_on_other(self, building):
        building.floors[0].grid[3][3].set_smoke(0.8)
        assert building.floors[0].grid[3][3].smoke == pytest.approx(0.8)
        assert building.floors[1].grid[3][3].smoke == pytest.approx(0.0)

    def test_temperature_on_one_floor_not_on_other(self, building):
        building.floors[0].grid[4][4].set_temperature(200.0)
        assert building.floors[0].grid[4][4].temperature == pytest.approx(200.0)
        assert building.floors[1].grid[4][4].temperature < 30.0


class TestMoveAgentBetweenFloors:
    """Agent floor transitions via stairwells."""

    def _setup_stairwells(self, building):
        """Register a stairwell at (2,2) connecting floor 0 and floor 1."""
        sid = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(sid, 0, building.floors[0].grid[2][2])
        StairwellIDGenerator.add(sid, 1, building.floors[1].grid[2][2])
        return sid

    def _make_agent(self, building, floor=0):
        grid = building.floors[floor]
        grid.ensure_material_cache()
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        return Agent(grid, grid.grid[5][5], floor=floor, building=building)

    def test_move_agent_up(self, building):
        sid = self._setup_stairwells(building)
        agent = self._make_agent(building, floor=0)
        assert agent.current_floor == 0

        result = building.move_agent_between_floors(agent, 0, 1, sid)
        assert result is True
        assert agent.current_floor == 1
        assert agent.grid is building.floors[1]
        assert agent.spot is building.floors[1].grid[2][2]

    def test_move_agent_down(self, building):
        sid = self._setup_stairwells(building)
        agent = self._make_agent(building, floor=1)

        result = building.move_agent_between_floors(agent, 1, 0, sid)
        assert result is True
        assert agent.current_floor == 0

    def test_move_invalid_floor_returns_false(self, building):
        sid = self._setup_stairwells(building)
        agent = self._make_agent(building, floor=0)
        assert building.move_agent_between_floors(agent, 0, 99, sid) is False

    def test_move_unregistered_stair_returns_false(self, building):
        agent = self._make_agent(building, floor=0)
        assert building.move_agent_between_floors(agent, 0, 1, 999) is False


class TestComputeMetrics:
    """Building-wide metrics aggregation."""

    def test_no_agents_no_crash(self, building):
        '''Should be able to compute metrics with no agents without crashing.'''
        for f in building.floors:
            f.update_np_arrays()
        building.compute_metrics(agents=None)
        assert building.metrics["fire_cells"] == 0

    def test_fire_counted_across_floors(self, building):
        '''Fires on multiple floors should be counted in total fire_cells and per-floor breakdown.'''
        building.floors[0].grid[3][3].set_on_fire()
        building.floors[1].grid[4][4].set_on_fire()
        building.floors[1].grid[5][5].set_on_fire()
        for f in building.floors:
            f.update_np_arrays()
        building.compute_metrics()
        assert building.metrics["fire_cells"] == 3
        assert building.metrics["fire_cells_per_floor"] == [1, 2]

    def test_agent_health_averaged(self, building):
        '''Agent health should be averaged across all agents regardless of floor.'''
        grid = building.floors[0]
        grid.ensure_material_cache()
        exit_spot = grid.grid[9][9]
        exit_spot.make_end()
        grid.add_exit(exit_spot)
        a1 = Agent(grid, grid.grid[1][1], floor=0)
        a2 = Agent(grid, grid.grid[2][2], floor=0)
        a1.health = 80.0
        a2.health = 60.0
        for f in building.floors:
            f.update_np_arrays()
        building.compute_metrics(agents=[a1, a2])
        import numpy as np
        assert np.mean(building.metrics["agent_health"]) == pytest.approx(70.0)

    def test_per_floor_lists_length(self, building_3f):
        '''Per-floor metric lists should have one entry per floor.'''
        for f in building_3f.floors:
            f.update_np_arrays()
        building_3f.compute_metrics()
        assert len(building_3f.metrics["fire_cells_per_floor"]) == 3
        assert len(building_3f.metrics["avg_temp_per_floor"]) == 3
        assert len(building_3f.metrics["avg_smoke_per_floor"]) == 3


class TestUpdateAllFloor:
    """Physics applied to every floor."""

    def test_temperature_changes_on_fire_floor(self, building):
        spot = building.floors[0].grid[5][5]
        spot.set_on_fire(600.0)
        for f in building.floors:
            f.ensure_material_cache()
            f.update_np_arrays()
        building.update_all_floor(update_dt=0.1)
        # Neighbors should have gained some heat
        neighbor_temp = building.floors[0].grid[5][6].temperature
        assert neighbor_temp > 25.0

    def test_inactive_floor_stays_ambient(self, building):
        # Only floor 0 has fire
        building.floors[0].grid[5][5].set_on_fire(600.0)
        for f in building.floors:
            f.ensure_material_cache()
            f.update_np_arrays()
        building.update_all_floor(update_dt=0.1)
        # Floor 1 center should stay near ambient
        assert building.floors[1].grid[5][5].temperature < 30.0
