"""Test Grid and Spot cell operations."""
import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.grid import Grid
from core.spot import Spot
from environment.materials import MATERIALS, material_id
from utils.utilities import state_value, fire_constants


class TestSpotState:
    """Test Spot cell state transitions."""

    @pytest.fixture
    def spot(self):
        """Create a default spot."""
        return Spot(row=5, col=5, width=10)

    def test_default_state(self, spot):
        """New spot should be empty air."""
        assert spot.is_empty()
        assert not spot.is_barrier()
        assert not spot.is_fire()
        assert spot.material == material_id.AIR
        assert spot.temperature == fire_constants.AMBIENT_TEMP.value

    def test_make_barrier(self, spot):
        """Spot should become a wall with concrete material."""
        spot.make_barrier()
        assert spot.is_barrier()
        assert spot.material == material_id.CONCRETE
        assert spot.fuel == 0.0

    def test_make_start(self, spot):
        """Spot should become a start position."""
        spot.make_start()
        assert spot.is_start()
        assert spot.material == material_id.AIR

    def test_make_end(self, spot):
        """Spot should become an exit."""
        spot.make_end()
        assert spot.is_end()
        assert spot.material == material_id.AIR

    def test_set_on_fire(self, spot):
        """Setting fire should update state and mark burned."""
        spot.set_on_fire(initial_temp=700.0)
        assert spot.is_fire()
        assert spot.temperature >= 700.0
        assert spot.burned is True

    def test_extinguish_fire(self, spot):
        """Extinguishing should restore state but keep burned flag."""
        spot.set_on_fire(initial_temp=700.0)
        spot.extinguish_fire()
        assert not spot.is_fire()
        assert spot.burned is True  # Cannot reignite

    def test_reset(self, spot):
        """Reset should restore all defaults."""
        spot.set_on_fire(initial_temp=800.0)
        spot._smoke = 0.5
        spot.reset()
        assert spot.is_empty()
        assert spot.temperature == fire_constants.AMBIENT_TEMP.value
        assert spot.smoke == 0.0
        assert spot.burned is False

    def test_temperature_bounds(self, spot):
        """Temperature should be clamped to valid range."""
        spot.set_temperature(2000.0)
        assert spot.temperature <= 1200.0

        spot.set_temperature(-100.0)
        assert spot.temperature >= fire_constants.AMBIENT_TEMP.value

    def test_smoke_bounds(self, spot):
        """Smoke should be clamped to [0, 1]."""
        spot.set_smoke(5.0)
        assert spot.smoke <= 1.0

        spot.set_smoke(-1.0)
        assert spot.smoke >= 0.0

    def test_fuel_consumption(self, spot):
        """Fuel should decrease but not go below 0."""
        spot.set_material(material_id.WOOD)
        initial = spot.fuel
        spot.consume_fuel(1.0)
        assert spot.fuel == initial - 1.0

        spot.consume_fuel(9999.0)
        assert spot.fuel == 0.0

    def test_set_material_updates_fuel(self, spot):
        """Setting material should initialize fuel from material properties."""
        spot.set_material(material_id.WOOD)
        assert spot.fuel == MATERIALS[material_id.WOOD]["fuel"]
        assert spot.material == material_id.WOOD

    def test_burned_spot_not_flammable(self, spot):
        """A spot that has already burned should not be flammable."""
        spot.set_on_fire(initial_temp=600.0)
        spot.extinguish_fire()
        assert not spot.is_flammable()

    def test_to_dict_roundtrip(self, spot):
        """to_dict should capture current state."""
        spot.set_material(material_id.WOOD)
        spot.set_temperature(300.0)
        spot._smoke = 0.4
        d = spot.to_dict()
        assert d['material'] == material_id.WOOD
        assert d['temperature'] == 300.0
        assert d['smoke'] == 0.4


class TestGridOperations:
    """Test Grid initialization and material operations."""

    @pytest.fixture
    def grid(self):
        """Create a 10x10 grid."""
        return Grid(rows=10, width=400, floor=0)

    def test_grid_initialization(self, grid):
        """Grid should initialize with correct dimensions."""
        assert grid.rows == 10
        assert len(grid.grid) == 10
        assert len(grid.grid[0]) == 10
        assert grid.temp_np.shape == (10, 10)
        assert grid.smoke_np.shape == (10, 10)

    def test_get_spot_valid(self, grid):
        """get_spot should return Spot for valid coordinates."""
        spot = grid.get_spot(5, 5)
        assert spot is not None
        assert spot.row == 5
        assert spot.col == 5

    def test_get_spot_out_of_bounds(self, grid):
        """get_spot should return None for out-of-bounds coordinates."""
        assert grid.get_spot(-1, 0) is None
        assert grid.get_spot(0, 10) is None
        assert grid.get_spot(10, 10) is None

    def test_in_bounds(self, grid):
        """in_bounds should correctly check boundaries."""
        assert grid.in_bounds(0, 0)
        assert grid.in_bounds(9, 9)
        assert not grid.in_bounds(-1, 0)
        assert not grid.in_bounds(10, 0)

    def test_set_material(self, grid):
        """set_material should update spot and mark cache dirty."""
        grid.set_material(5, 5, material_id.WOOD)
        spot = grid.grid[5][5]
        assert spot.material == material_id.WOOD
        assert grid.material_cache_dirty

    def test_material_cache_rebuild(self, grid):
        """Material cache should reflect current materials after rebuild."""
        grid.set_material(5, 5, material_id.WOOD)
        grid.ensure_material_cache()

        wood_ht = MATERIALS[material_id.WOOD]["heat_transfer"]
        assert grid.heat_transfer_np[5, 5] == pytest.approx(wood_ht, rel=0.01)

    def test_neighbor_map_center(self, grid):
        """Center cell should have 8 neighbors."""
        neighbors = grid.neighbor_map[5][5]
        assert len(neighbors) == 8

    def test_neighbor_map_corner(self, grid):
        """Corner cell should have 3 neighbors."""
        neighbors = grid.neighbor_map[0][0]
        assert len(neighbors) == 3

    def test_np_array_sync(self, grid):
        """update_np_arrays should sync spot state to numpy arrays."""
        grid.grid[3][3].set_temperature(500.0)
        grid.grid[3][3]._smoke = 0.6
        grid.update_np_arrays()

        assert grid.temp_np[3, 3] == pytest.approx(500.0)
        assert grid.smoke_np[3, 3] == pytest.approx(0.6)

    def test_backup_and_restore_layout(self, grid):
        """backup_layout should capture current state for reset."""
        grid.set_material(2, 2, material_id.WOOD)
        grid.grid[3][3].make_barrier()
        grid.backup_layout()

        assert grid.initial_layout is not None
        assert grid.initial_layout[2][2]['material'] == material_id.WOOD
        assert grid.initial_layout[3][3]['state'] == state_value.WALL.value

    def test_exits_management(self, grid):
        """Exit add/remove/clear should work correctly."""
        spot = grid.grid[9][9]
        spot.make_end()
        grid.add_exit(spot)
        assert grid.is_exit(spot)

        grid.remove_exit(spot)
        assert not grid.is_exit(spot)

        grid.add_exit(spot)
        grid.clear_exits()
        assert not grid.is_exit(spot)
