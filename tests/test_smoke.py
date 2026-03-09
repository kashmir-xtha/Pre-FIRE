"""Test smoke diffusion physics."""
import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from environment.smoke import spread_smoke
from environment.materials import MATERIALS, material_id
from core.grid import Grid
from utils.utilities import smoke_constants


class TestSmokeDiffusion:
    """Test smoke spread and decay mechanics."""

    @pytest.fixture
    def grid_with_fire(self):
        """Create grid with a single fire cell producing smoke."""
        grid = Grid(rows=10, width=400, floor=0)
        center = grid.grid[5][5]
        grid.set_material(5, 5, material_id.WOOD)
        center._fuel = MATERIALS[material_id.WOOD]["fuel"]
        center.set_on_fire(initial_temp=800.0)
        grid.ensure_material_cache()
        grid.update_np_arrays()
        return grid

    def test_fire_produces_smoke(self, grid_with_fire):
        """Fire cells should produce smoke."""
        grid = grid_with_fire
        assert grid.smoke_np[5, 5] == 0.0, "No smoke initially"

        spread_smoke(grid, dt=1.0)

        assert grid.smoke_np[5, 5] > 0.0, "Fire should produce smoke"

    def test_smoke_diffuses_to_neighbors(self, grid_with_fire):
        """Smoke should spread to adjacent cells."""
        grid = grid_with_fire

        # Run several ticks so smoke can spread outward
        for _ in range(10):
            spread_smoke(grid, dt=1.0)

        # Neighbors should have picked up some smoke
        assert grid.smoke_np[5, 6] > 0.0, "Smoke should diffuse east"
        assert grid.smoke_np[4, 5] > 0.0, "Smoke should diffuse north"

    def test_barriers_block_smoke(self):
        """Barriers should block smoke diffusion."""
        grid = Grid(rows=10, width=400, floor=0)

        # Wall separating left from right at column 5
        for r in range(10):
            grid.grid[r][5].make_barrier()

        # Fire on the left side
        grid.set_material(5, 3, material_id.WOOD)
        grid.grid[5][3]._fuel = MATERIALS[material_id.WOOD]["fuel"]
        grid.grid[5][3].set_on_fire(initial_temp=800.0)

        grid.ensure_material_cache()
        grid.update_np_arrays()

        for _ in range(20):
            spread_smoke(grid, dt=1.0)

        left_smoke = grid.smoke_np[5, 4]
        right_smoke = grid.smoke_np[5, 6]
        assert left_smoke > right_smoke, \
            f"Wall should block smoke: left={left_smoke}, right={right_smoke}"

    def test_smoke_decays_over_time(self):
        """Smoke should decay when source is removed."""
        grid = Grid(rows=10, width=400, floor=0)

        # Manually inject smoke (no fire source)
        grid.smoke_np[5, 5] = 0.8
        grid.grid[5][5]._smoke = 0.8
        grid.ensure_material_cache()
        grid.update_np_arrays()

        initial = grid.smoke_np[5, 5]
        for _ in range(20):
            spread_smoke(grid, dt=1.0)

        final = grid.smoke_np[5, 5]
        # Smoke should decrease (decays + diffuses outward)
        assert final < initial, \
            f"Smoke should decay: initial={initial}, final={final}"

    def test_smoke_stays_in_bounds(self, grid_with_fire):
        """Smoke values should stay in [0, max_smoke]."""
        grid = grid_with_fire

        for _ in range(50):
            spread_smoke(grid, dt=1.0)

        assert np.all(grid.smoke_np >= 0.0), "Smoke should not go negative"
        assert np.all(grid.smoke_np <= 1.0), "Smoke should not exceed max"

    def test_barrier_has_no_smoke(self):
        """Barrier cells should always have zero smoke."""
        grid = Grid(rows=10, width=400, floor=0)

        # Place barrier first, then fire
        grid.grid[4][5].make_barrier()
        grid.set_material(5, 5, material_id.WOOD)
        grid.grid[5][5]._fuel = MATERIALS[material_id.WOOD]["fuel"]
        grid.grid[5][5].set_on_fire(initial_temp=800.0)

        grid.ensure_material_cache()
        grid.update_np_arrays()

        for _ in range(20):
            spread_smoke(grid, dt=1.0)

        assert grid.smoke_np[4, 5] == 0.0, "Barriers should have no smoke"
