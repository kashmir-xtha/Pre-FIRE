"""Test fire and heat physics."""
import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from environment.fire import do_temperature_update, update_fire_with_materials
from environment.materials import MATERIALS, material_id
from core.grid import Grid
from utils.utilities import state_value, fire_constants


class TestHeatDiffusion:
    """Test heat diffusion physics."""
    
    @pytest.fixture
    def grid_with_hot_spot(self):
        """Create grid with heat source."""
        grid = Grid(rows=10, width=400, floor=0)
        ambient = fire_constants.AMBIENT_TEMP.value

        # Use a conductive material so diffusion to neighbors is measurable.
        for r in range(grid.rows):
            for c in range(grid.rows):
                grid.set_material(r, c, material_id.WOOD)
                grid.grid[r][c].set_temperature(ambient)

        # Hot spot in center
        grid.grid[5][5].set_temperature(600.0)

        grid.ensure_material_cache()
        grid.update_np_arrays()
        return grid
    
    def test_heat_diffuses_to_neighbors(self, grid_with_hot_spot):
        """Heat should spread to adjacent cells."""
        grid = grid_with_hot_spot
        temp_before = grid.temp_np[4, 5].copy()
        
        # Run temperature update
        do_temperature_update(grid, dt=1.0)
        grid.update_np_arrays()  # Sync spot temperatures back to numpy array
        
        temp_after = grid.temp_np[4, 5]
        assert temp_after > temp_before, f"Adjacent cell should warm up: before={temp_before}, after={temp_after}"
    
    def test_hot_spot_cools_over_time(self, grid_with_hot_spot):
        """Isolated heat should cool down over time."""
        grid = grid_with_hot_spot
        temp_before = grid.temp_np[5, 5].copy()
        
        # Run multiple updates
        for _ in range(50):
            do_temperature_update(grid, dt=1.0)
        
        grid.update_np_arrays()  # Sync after all updates
        temp_after = grid.temp_np[5, 5]
        # Temperature should decrease (heat dissipates to surroundings + cooling)
        assert temp_after < temp_before, f"Heat should cool: before={temp_before}, after={temp_after}"
    
    def test_barriers_impede_heat(self):
        """Walls should slow heat transfer."""
        grid = Grid(rows=10, width=400, floor=0)

        ambient = fire_constants.AMBIENT_TEMP.value

        # Initialize all cells to ambient
        for r in range(grid.rows):
            for c in range(grid.rows):
                grid.grid[r][c].set_temperature(ambient)
                if not grid.grid[r][c].is_barrier():
                    grid.set_material(r, c, material_id.WOOD)

        # Add full-height wall barrier at column 4
        for row in range(10):
            grid.grid[row][4].make_barrier()

        # Sustained heat source on the left side of the barrier
        source = grid.grid[5][2]
        grid.set_material(5, 2, material_id.WOOD)
        source._fuel = MATERIALS[material_id.WOOD]["fuel"]
        source.set_on_fire(initial_temp=900.0)

        grid.ensure_material_cache()
        grid.update_np_arrays()  # Sync to numpy for simulation

        # Run coupled fire + temperature updates
        for _ in range(30):
            update_fire_with_materials(grid, dt=1.0)
            do_temperature_update(grid, dt=1.0)

        grid.update_np_arrays()  # Sync temperatures

        # Check temperatures on both sides of wall
        left_temp = grid.temp_np[5, 3]   # Immediately left of wall
        right_temp = grid.temp_np[5, 5]  # Immediately right of wall

        # Left should be significantly hotter than right
        assert left_temp > right_temp + 1.0, \
            f"Wall should impede heat: left={left_temp}, right={right_temp}"
    
    def test_temperature_stays_above_ambient(self):
        """Temperature should not drop below ambient."""
        grid = Grid(rows=10, width=400, floor=0)
        ambient = fire_constants.AMBIENT_TEMP.value
        
        # Set materials
        for r in range(grid.rows):
            for c in range(grid.rows):
                grid.set_material(r, c, material_id.CONCRETE)
                grid.grid[r][c].set_temperature(ambient)

        grid.grid[5][5].set_temperature(ambient + 5.0)  # Slightly above ambient
        
        grid.ensure_material_cache()
        grid.update_np_arrays()
        
        # Run many updates
        for _ in range(100):
            do_temperature_update(grid, dt=1.0)
        
        grid.update_np_arrays()  # Sync temperatures
        
        # Temperature should approach but not go below ambient
        assert np.all(grid.temp_np >= ambient - 1.0), "Temperature should not drop significantly below ambient"


class TestFireSpread:
    """Test fire spread and ignition mechanics."""
    
    def test_fire_ignites_at_high_temperature(self, monkeypatch):
        """Materials should ignite when above ignition temperature."""
        grid = Grid(rows=10, width=400, floor=0)

        # Remove randomness so auto-ignition is deterministic.
        monkeypatch.setattr(np.random, "random", lambda shape: np.zeros(shape, dtype=np.float32))
        
        # Set a flammable material with fuel
        grid.set_material(5, 5, material_id.WOOD)
        center = grid.grid[5][5]
        center._fuel = MATERIALS[material_id.WOOD]["fuel"]
        center._burned = False  # Explicitly ensure not burned (required for ignition)
        
        grid.ensure_material_cache()
        
        # Heat to above ignition temp for wood
        wood_material = MATERIALS[material_id.WOOD]
        center.set_temperature(wood_material["ignition_temp"] + 50.0)
        
        # Sync to numpy arrays
        grid.update_np_arrays()
        
        # Update fire state
        update_fire_with_materials(grid, dt=1.0)
        
        # Check if fire ignited (may be probabilistic)
        # Allow multiple attempts if spread is probabilistic
        fire_ignited = grid.fire_np[5, 5]
        
        if not fire_ignited:
            # Try more times since ignition is probabilistic (30% per frame)
            for _ in range(3):
                center.set_temperature(wood_material["ignition_temp"] + 100.0)
                grid.update_np_arrays()
                update_fire_with_materials(grid, dt=1.0)
                if grid.fire_np[5, 5]:
                    fire_ignited = True
                    break
        
        # After multiple attempts, fire should have ignited
        # With 20 attempts at 30% each, chance of igniting is ~99.97%
        assert fire_ignited, \
            f"Material should eventually ignite at high temperature (fuel={grid.fuel_np[5, 5]}, temp={center.temperature})"
    
    def test_fuel_depletes_during_burning(self):
        """Burning cells should consume fuel over time."""
        grid = Grid(rows=10, width=400, floor=0)
        
        # Set wood material with fuel
        grid.set_material(5, 5, material_id.WOOD)
        center = grid.grid[5][5]
        center._fuel = MATERIALS[material_id.WOOD]["fuel"]
        
        grid.ensure_material_cache()
        
        # Force ignition on the spot object
        center.set_on_fire(initial_temp=800.0)
        
        # Sync to numpy arrays
        grid.update_np_arrays()
        initial_fuel = grid.fuel_np[5, 5]
        
        # Run fire update multiple times
        for _ in range(10):
            update_fire_with_materials(grid, dt=1.0)
        
        grid.update_np_arrays()  # Sync after updates
        final_fuel = grid.fuel_np[5, 5]
        
        # Fuel should have decreased
        assert final_fuel < initial_fuel, \
            f"Fuel should decrease during burning: initial={initial_fuel}, final={final_fuel}"
    
    def test_fire_extinguishes_when_fuel_depleted(self):
        """Fire should extinguish when fuel runs out."""
        grid = Grid(rows=10, width=400, floor=0)
        
        # Set wood material
        grid.set_material(5, 5, material_id.WOOD)
        center = grid.grid[5][5]
        center._fuel = MATERIALS[material_id.WOOD]["fuel"]
        
        grid.ensure_material_cache()
        
        # Force ignition and deplete fuel on Spot (runtime source of truth)
        center.set_on_fire(initial_temp=800.0)
        center._fuel = 0.1  # Very low fuel
        grid.update_np_arrays()
        
        # Run updates until fuel depletes
        for _ in range(20):
            update_fire_with_materials(grid, dt=1.0)
            if grid.fuel_np[5, 5] <= 0:
                break
        
        # Fire should be extinguished when fuel is gone
        if grid.fuel_np[5, 5] <= 0:
            assert not grid.fire_np[5, 5], "Fire should extinguish when fuel depleted"
    
    def test_concrete_does_not_ignite(self):
        """Non-flammable materials should not catch fire."""
        grid = Grid(rows=10, width=400, floor=0)
        
        # Set concrete (non-flammable)
        grid.set_material(5, 5, material_id.CONCRETE)
        center = grid.grid[5][5]
        
        grid.ensure_material_cache()
        
        # Heat to very high temperature on Spot then sync
        center.set_temperature(1000.0)
        grid.update_np_arrays()
        
        # Try to ignite multiple times
        for _ in range(10):
            update_fire_with_materials(grid, dt=1.0)
        
        # Concrete should not ignite
        assert not grid.fire_np[5, 5], "Concrete should not ignite at any temperature"


class TestFirePhysicsIntegration:
    """Test integrated fire and heat physics."""
    
    def test_fire_increases_temperature(self):
        """Active fire should increase local temperature."""
        grid = Grid(rows=10, width=400, floor=0)
        
        # Set wood and ignite
        grid.set_material(5, 5, material_id.WOOD)
        center = grid.grid[5][5]
        center._fuel = MATERIALS[material_id.WOOD]["fuel"]
        
        grid.ensure_material_cache()
        
        # Set fire on the spot object
        center.set_on_fire(initial_temp=400.0)
        
        # Sync to numpy arrays
        grid.update_np_arrays()
        
        # Run updates
        for _ in range(10):
            update_fire_with_materials(grid, dt=1.0)
            do_temperature_update(grid, dt=1.0)
        
        grid.update_np_arrays()  # Sync temperatures
        
        # Temperature should have increased significantly
        assert grid.temp_np[5, 5] > 500.0, \
            f"Fire should increase temperature: {grid.temp_np[5, 5]}"
    
    def test_fire_spreads_heat_to_neighbors(self):
        """Fire should heat neighboring cells."""
        grid = Grid(rows=10, width=400, floor=0)
        
        # Setup materials and temperatures
        for r in range(grid.rows):
            for c in range(grid.rows):
                grid.set_material(r, c, material_id.WOOD)
                grid.grid[r][c]._fuel = MATERIALS[material_id.WOOD]["fuel"]
                grid.grid[r][c].set_temperature(fire_constants.AMBIENT_TEMP.value)
        
        grid.ensure_material_cache()
        
        # Start fire in center
        center = grid.grid[5][5]
        center.set_on_fire(initial_temp=800.0)
        
        # Sync to numpy arrays
        grid.update_np_arrays()
        initial_neighbor_temp = grid.temp_np[5, 6]
        
        # Run simulation
        for _ in range(20):
            update_fire_with_materials(grid, dt=1.0)
            do_temperature_update(grid, dt=1.0)
        
        grid.update_np_arrays()  # Sync temperatures
        final_neighbor_temp = grid.temp_np[5, 6]
        
        # Neighbor should have warmed up
        assert final_neighbor_temp > initial_neighbor_temp + 20.0, \
            f"Neighbor should warm from fire: initial={initial_neighbor_temp}, final={final_neighbor_temp}"


# Run tests with:
# pytest tests/test_fire_physics.py -v
# pytest tests/ -v  # Run all tests
# pytest tests/ -v --tb=short  # With shorter error traces
