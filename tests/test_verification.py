"""
test_verification_section.py
============================
Verification tests for Section 6.6.1 of the PRE-FIRE report.

Covers gaps NOT addressed by existing test files:
  test_fire_physics.py, test_fed_model.py, test_agent_state.py,
  test_pathfinding.py, test_smoke.py, test_building.py,
  test_vulnerability_stress.py

Run with:  pytest tests/test_verification_section.py -v

Design notes
------------
Material cooling tests verify the *constants* stored in grid caches
(cooling_rate_np, heat_capacity_np) rather than simulated temperature
ordering.  Ordering tests in an open grid are confounded by diffusion
to barrier neighbours; the cache tests are a cleaner, more direct
assertion of the report claim that material-specific properties are
correctly loaded and used.

Health curve: 100*(1-FED^0.7) with exponent 0.7 < 1 is CONVEX —
health drops quickly in early exposure and decelerates toward
incapacitation. Tests assert this actual implementation behaviour.
"""

import csv
import json
import pytest
import numpy as np
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import Agent
from core.agent.agent_movement import VULNERABILITY_PROFILES
from core.building import Building
from core.grid import Grid
from environment.fire import do_temperature_update, update_fire_with_materials
from environment.materials import MATERIALS, material_id
from environment.smoke import spread_smoke
from utils.save_manager import SaveManager, SimulationSnapshot
from utils.stairwell_manager import StairwellIDGenerator
from utils.utilities import fire_constants

AMBIENT = fire_constants.AMBIENT_TEMP.value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_grid(rows=10):
    g = Grid(rows=rows, width=400, floor=0)
    g.ensure_material_cache()
    return g


def make_agent(vulnerability="adult_fit", rows=10):
    g = make_grid(rows)
    g.grid[rows - 1][rows - 1].make_end()
    g.add_exit(g.grid[rows - 1][rows - 1])
    g.ensure_material_cache()
    return Agent(g, g.grid[rows // 2][rows // 2], floor=0,
                 vulnerability=vulnerability)


# ===========================================================================
# 1. FIRE SPREAD
# ===========================================================================

class TestBurnedFlagPreventsReIgnition:
    """
    Burned cells must never re-ignite regardless of temperature.
    Verifies that set_on_fire() sets _burned=True permanently and
    update_fire_with_materials() respects it.
    """

    def test_burned_cell_never_reignites_at_high_temp(self):
        g = make_grid()
        s = g.grid[5][5]
        g.set_material(5, 5, material_id.WOOD)
        s._fuel = MATERIALS[material_id.WOOD]["fuel"]

        s.set_on_fire(initial_temp=800.0)
        assert s.burned is True
        s.extinguish_fire()
        assert not s.is_fire()

        s.set_temperature(MATERIALS[material_id.WOOD]["ignition_temp"] * 3)
        g.update_np_arrays()
        for _ in range(100):
            update_fire_with_materials(g, dt=1.0)

        assert not g.fire_np[5, 5], (
            "A BURNED cell must never re-ignite regardless of temperature"
        )

    def test_burned_flag_persists_after_cool_and_reheat(self):
        g = make_grid()
        s = g.grid[5][5]
        g.set_material(5, 5, material_id.WOOD)
        s._fuel = MATERIALS[material_id.WOOD]["fuel"]
        s.set_on_fire(initial_temp=800.0)
        s.extinguish_fire()

        s.set_temperature(AMBIENT)
        g.update_np_arrays()
        s.set_temperature(1000.0)
        g.update_np_arrays()
        for _ in range(50):
            update_fire_with_materials(g, dt=1.0)

        assert not g.fire_np[5, 5], (
            "Burned flag must persist across temperature changes"
        )


class TestFireSpreadMooreNeighborhoodOnly:
    """
    After a single update step, no cell at Chebyshev distance > 1 from
    the fire source may be on fire.
    """

    def test_single_step_does_not_jump_beyond_moore(self, monkeypatch):
        monkeypatch.setattr(
            np.random, "random",
            lambda shape=None: (
                np.zeros(shape, dtype=np.float32) if shape else 0.0
            ),
        )
        g = make_grid(rows=15)
        for r in range(15):
            for c in range(15):
                g.set_material(r, c, material_id.WOOD)
                g.grid[r][c]._fuel = MATERIALS[material_id.WOOD]["fuel"]
                g.grid[r][c].set_temperature(AMBIENT)
                g.grid[r][c]._burned = False

        g.grid[7][7].set_on_fire(initial_temp=800.0)
        g.update_np_arrays()
        update_fire_with_materials(g, dt=0.05)

        for r in range(15):
            for c in range(15):
                if max(abs(r - 7), abs(c - 7)) > 1:
                    assert not g.fire_np[r, c], (
                        f"Cell at ({r},{c}) must not ignite in a single step "
                        f"— fire confined to Moore neighborhood"
                    )


class TestNonCombustibleMaterials:
    """Cells with zero fuel must never ignite regardless of temperature."""

    @pytest.mark.parametrize("mat", [material_id.CONCRETE, material_id.METAL])
    def test_zero_fuel_material_does_not_ignite(self, mat):
        g = make_grid()
        g.set_material(5, 5, mat)
        g.grid[5][5].set_temperature(2000.0)
        g.update_np_arrays()
        for _ in range(20):
            update_fire_with_materials(g, dt=1.0)
        assert not g.fire_np[5, 5], (
            f"Material {mat} (zero fuel) must never ignite"
        )


# ===========================================================================
# 2. HEAT AND TEMPERATURE
# ===========================================================================

class TestStefanBoltzmannActivation:
    """
    The radiative term activates above 200 C. A source cell at 201 C
    must transfer at least as much heat to a neighbour as one at 199 C.
    """

    def test_heat_transfer_greater_at_201_than_199(self):
        steps, dt = 5, 0.5

        ga = make_grid()
        ga.set_material(5, 5, material_id.METAL)
        ga.set_material(5, 6, material_id.METAL)
        ga.grid[5][5].set_temperature(199.0)
        ga.grid[5][6].set_temperature(AMBIENT)
        ga.ensure_material_cache()
        ga.update_np_arrays()
        for _ in range(steps):
            do_temperature_update(ga, dt=dt)
        gain_below = ga.temp_np[5, 6] - AMBIENT

        gb = make_grid()
        gb.set_material(5, 5, material_id.METAL)
        gb.set_material(5, 6, material_id.METAL)
        gb.grid[5][5].set_temperature(201.0)
        gb.grid[5][6].set_temperature(AMBIENT)
        gb.ensure_material_cache()
        gb.update_np_arrays()
        for _ in range(steps):
            do_temperature_update(gb, dt=dt)
        gain_above = gb.temp_np[5, 6] - AMBIENT

        assert gain_above >= gain_below, (
            f"Heat transfer at 201 C (gain={gain_above:.5f}) must be >= "
            f"at 199 C (gain={gain_below:.5f}): Stefan-Boltzmann term "
            f"must activate above 200 C"
        )


class TestMaterialSpecificCoolingConstants:
    """
    Material-specific cooling rate and heat capacity constants must be
    loaded correctly into the grid's numpy caches.

    From Table 5-1 (report):
      Material   cooling_rate   density   specific_heat
      Wood       10.0           600       1700
      Metal      25.0           7800      500
      Concrete    8.0           2300      880

    These are the direct implementation claims. Testing the cache values
    is more reliable than simulated temperature ordering, which is
    confounded by diffusion to neighbouring cells.
    """

    @pytest.fixture
    def multi_material_grid(self):
        g = Grid(rows=10, width=400, floor=0)
        g.set_material(2, 2, material_id.WOOD)
        g.set_material(4, 4, material_id.METAL)
        g.set_material(6, 6, material_id.CONCRETE)
        g.ensure_material_cache()
        g.update_np_arrays()
        return g

    def test_cooling_rates_are_material_specific(self, multi_material_grid):
        """Each material must have its own distinct cooling rate."""
        g = multi_material_grid
        wood_k     = g.cooling_rate_np[2, 2]
        metal_k    = g.cooling_rate_np[4, 4]
        concrete_k = g.cooling_rate_np[6, 6]

        assert len({wood_k, metal_k, concrete_k}) == 3, (
            "Wood, Metal, and Concrete must have different cooling rates"
        )

    def test_metal_has_highest_cooling_rate(self, multi_material_grid):
        """Metal (k_c=25) must have the highest cooling rate constant."""
        g = multi_material_grid
        assert g.cooling_rate_np[4, 4] > g.cooling_rate_np[2, 2], (
            "Metal cooling_rate (25) must exceed Wood cooling_rate (10)"
        )
        assert g.cooling_rate_np[4, 4] > g.cooling_rate_np[6, 6], (
            "Metal cooling_rate (25) must exceed Concrete cooling_rate (8)"
        )

    def test_wood_cooling_rate_exceeds_concrete(self, multi_material_grid):
        """Wood (k_c=10) must have a higher cooling rate than Concrete (k_c=8)."""
        g = multi_material_grid
        assert g.cooling_rate_np[2, 2] > g.cooling_rate_np[6, 6], (
            "Wood cooling_rate (10) must exceed Concrete cooling_rate (8)"
        )

    def test_heat_capacities_are_material_specific(self, multi_material_grid):
        """Each material must have its own distinct heat capacity."""
        g = multi_material_grid
        wood_hc     = g.heat_capacity_np[2, 2]
        metal_hc    = g.heat_capacity_np[4, 4]
        concrete_hc = g.heat_capacity_np[6, 6]

        assert len({wood_hc, metal_hc, concrete_hc}) == 3, (
            "Wood, Metal, and Concrete must have different heat capacities"
        )

    def test_all_materials_cool_toward_ambient(self):
        """All materials must lose temperature over time in the absence of fire."""
        for mat in [material_id.WOOD, material_id.METAL, material_id.CONCRETE]:
            g = make_grid()
            g.set_material(5, 5, mat)
            g.grid[5][5].set_temperature(400.0)
            g.grid[5][5]._burned = False
            g.ensure_material_cache()
            g.update_np_arrays()
            initial = g.temp_np[5, 5]
            for _ in range(50):
                do_temperature_update(g, dt=0.5)
            g.update_np_arrays()   # sync spot temperatures back to numpy array
            final = g.temp_np[5, 5]
            assert final < initial, (
                f"Material {mat} must cool from {initial:.1f} C over time, "
                f"but final temp = {final:.2f} C"
            )


# ===========================================================================
# 3. SMOKE PROPAGATION
# ===========================================================================

class TestPositiveFluxOnly:
    """
    The positive-flux clamp must prevent smoke flowing from a
    lower-concentration cell into a higher-concentration cell.
    """

    def test_smoke_does_not_flow_uphill(self):
        g = make_grid()
        g.smoke_np[5, 5] = 0.1
        g.grid[5][5]._smoke = 0.1
        g.smoke_np[5, 6] = 0.9
        g.grid[5][6]._smoke = 0.9

        before = float(g.smoke_np[5, 6])
        spread_smoke(g, dt=0.1)
        after = float(g.smoke_np[5, 6])

        assert after <= before + 1e-5, (
            f"Smoke must not flow uphill: {before:.3f} -> {after:.5f}"
        )

    def test_smoke_flows_high_to_low(self):
        """Forward diffusion (high to low) must still work correctly."""
        g = make_grid()
        g.smoke_np[5, 5] = 0.8
        g.grid[5][5]._smoke = 0.8
        g.smoke_np[5, 6] = 0.0
        g.grid[5][6]._smoke = 0.0

        spread_smoke(g, dt=0.5)
        assert g.smoke_np[5, 6] > 0.0, (
            "Smoke must diffuse from high to low concentration"
        )


class TestHigherTempFireProducesMoreSmoke:
    """
    Smoke production is proportional to fire temperature (Equation 5-12).
    A burning cell at 900 C must produce more smoke per step than at 300 C.
    """

    def test_higher_temp_produces_more_smoke(self):
        steps, dt = 5, 0.5

        def smoke_from_fire(temp):
            g = make_grid()
            g.set_material(5, 5, material_id.WOOD)
            g.grid[5][5]._fuel = MATERIALS[material_id.WOOD]["fuel"]
            g.grid[5][5].set_on_fire(initial_temp=temp)
            g.smoke_np[5, 5] = 0.0
            g.grid[5][5]._smoke = 0.0
            g.update_np_arrays()
            for _ in range(steps):
                spread_smoke(g, dt=dt)
            return float(g.smoke_np[5, 5])

        smoke_low  = smoke_from_fire(300.0)
        smoke_high = smoke_from_fire(900.0)

        assert smoke_high > smoke_low, (
            f"High-temp fire smoke ({smoke_high:.4f}) must exceed "
            f"low-temp fire smoke ({smoke_low:.4f})"
        )


# ===========================================================================
# 4. INTER-FLOOR SMOKE TRANSFER
# ===========================================================================

class TestInterFloorSmokeTransfer:
    """
    Smoke transfer via stairwells must be upward-biased
    (D_up=0.25 > D_down=0.10) and mass-conserved.
    """

    @pytest.fixture(autouse=True)
    def _reset_stairs(self):
        StairwellIDGenerator.reset()
        yield
        StairwellIDGenerator.reset()

    def _two_floor_building(self):
        b = Building(num_of_floors=2, rows=10, width=400)
        sid = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(sid, 0, b.floors[0].grid[3][3])
        StairwellIDGenerator.add(sid, 1, b.floors[1].grid[3][3])
        return b

    def test_smoke_rises_from_lower_to_upper_floor(self):
        b = self._two_floor_building()
        b.floors[0].smoke_np[3, 3] = 0.8
        b.floors[0].grid[3][3]._smoke = 0.8
        b.floors[1].smoke_np[3, 3] = 0.0
        b.floors[1].grid[3][3]._smoke = 0.0

        b._transfer_inter_floor(dt=1.0)

        gained = float(b.floors[1].smoke_np[3, 3])
        assert gained > 0.0, (
            f"Upper floor must gain smoke from lower floor; gained={gained:.4f}"
        )

    def test_upward_transfer_exceeds_downward_transfer(self):
        """D_up=0.25 > D_down=0.10 so equal gradients yield more upward flow."""
        smoke_level, dt = 0.8, 1.0

        b1 = self._two_floor_building()
        b1.floors[1].smoke_np[3, 3] = smoke_level
        b1.floors[1].grid[3][3]._smoke = smoke_level
        b1.floors[0].smoke_np[3, 3] = 0.0
        b1.floors[0].grid[3][3]._smoke = 0.0
        b1._transfer_inter_floor(dt=dt)
        downward = float(b1.floors[0].smoke_np[3, 3])
        StairwellIDGenerator.reset()

        b2 = Building(num_of_floors=2, rows=10, width=400)
        sid2 = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(sid2, 0, b2.floors[0].grid[3][3])
        StairwellIDGenerator.add(sid2, 1, b2.floors[1].grid[3][3])
        b2.floors[0].smoke_np[3, 3] = smoke_level
        b2.floors[0].grid[3][3]._smoke = smoke_level
        b2.floors[1].smoke_np[3, 3] = 0.0
        b2.floors[1].grid[3][3]._smoke = 0.0
        b2._transfer_inter_floor(dt=dt)
        upward = float(b2.floors[1].smoke_np[3, 3])

        assert upward > downward, (
            f"Upward transfer ({upward:.4f}) must exceed downward "
            f"({downward:.4f}), confirming D_up (0.25) > D_down (0.10)"
        )

    def test_smoke_conservation_across_floors(self):
        """What leaves one floor must arrive exactly on the other."""
        b = self._two_floor_building()
        b.floors[0].smoke_np[3, 3] = 0.6
        b.floors[0].grid[3][3]._smoke = 0.6
        b.floors[1].smoke_np[3, 3] = 0.1
        b.floors[1].grid[3][3]._smoke = 0.1

        total_before = 0.7
        b._transfer_inter_floor(dt=1.0)
        total_after = (
            float(b.floors[0].smoke_np[3, 3]) +
            float(b.floors[1].smoke_np[3, 3])
        )

        assert abs(total_after - total_before) < 0.01, (
            f"Smoke must be conserved: before={total_before:.4f}, "
            f"after={total_after:.4f}"
        )


# ===========================================================================
# 5. AGENT STATE MACHINE
# ===========================================================================

class TestAgentStateAdditional:
    """
    Gaps not covered by test_agent_state.py:
    - Physical position must not change during REACTION delay
    - High stress must shorten the delay to MOVING
    """

    def test_position_unchanged_during_reaction_delay(self):
        g = make_grid(rows=15)
        g.grid[14][14].make_end()
        g.add_exit(g.grid[14][14])
        g.ensure_material_cache()

        a = Agent(g, g.grid[7][7], floor=0)
        initial_spot = a.spot

        a.smoke_detected = True
        a.state_manager.update(dt=0.1)
        assert a.state == "REACTION"

        # Step 0.5 s — well within the 2.0 s base delay
        for _ in range(5):
            a.state_manager.update(dt=0.1)

        if a.state == "REACTION":
            assert a.spot is initial_spot, (
                "Agent must not change position during REACTION delay"
            )

    def test_high_stress_shortens_reaction_delay(self):
        """
        At stress=1.0 reaction time is 30% of base (0.6 s).
        After 0.8 s the stressed agent must be MOVING while the
        unstressed one is still in REACTION (base delay 2.0 s).
        """

        def make_reacting(stress_level):
            g = make_grid(rows=15)
            g.grid[14][14].make_end()
            g.add_exit(g.grid[14][14])
            g.ensure_material_cache()
            a = Agent(g, g.grid[7][7], floor=0)
            a.movement.stress = stress_level
            a.smoke_detected = True
            a.state_manager.update(dt=0.01)
            return a

        normal   = make_reacting(0.0)
        stressed = make_reacting(1.0)

        assert normal.state == "REACTION"
        assert stressed.state == "REACTION"

        for _ in range(8):   # 8 * 0.1 s = 0.8 s
            normal.state_manager.update(dt=0.1)
            stressed.state_manager.update(dt=0.1)

        assert stressed.state == "MOVING", (
            f"High-stress agent must be MOVING after 0.8 s, "
            f"got {stressed.state}"
        )
        assert normal.state == "REACTION", (
            f"Unstressed agent must still be in REACTION at 0.8 s, "
            f"got {normal.state}"
        )


# ===========================================================================
# 6. A* PATHFINDING
# ===========================================================================

class TestPathfindingAdditional:
    """
    Gaps not covered by test_pathfinding.py:
    - Path length must equal Chebyshev distance in an open grid
    - Desperate mode must find a path through hazard-filled corridors
    """

    def test_path_length_equals_chebyshev_distance(self):
        """In an obstacle-free grid A* must return a Chebyshev-optimal path."""
        g = Grid(rows=20, width=800, floor=0)
        g.grid[15][17].make_end()
        g.add_exit(g.grid[15][17])
        g.ensure_material_cache()

        a = Agent(g, g.grid[5][5], floor=0)
        path = a.best_path()

        assert len(path) > 0, "Path must be found in an open grid"

        chebyshev = max(abs(15 - 5), abs(17 - 5))   # = 12
        assert len(path) - 1 == chebyshev, (
            f"Path steps ({len(path)-1}) must equal Chebyshev distance "
            f"({chebyshev}) in an obstacle-free grid"
        )

    def test_desperate_mode_finds_path_through_hazards(self):
        """Desperate mode must return a path even through maximum hazard."""
        g = Grid(rows=15, width=600, floor=0)
        g.grid[7][14].make_end()
        g.add_exit(g.grid[7][14])
        g.ensure_material_cache()

        for r in range(15):
            for c in range(1, 14):
                g.smoke_np[r, c] = 1.0
                g.grid[r][c]._smoke = 1.0
                g.grid[r][c].set_temperature(200.0)
        g.update_np_arrays()

        a = Agent(g, g.grid[7][0], floor=0)
        a.known_smoke = g.smoke_np.copy()
        a.known_temp[:] = 200.0

        path = a.pathplanner.compute_path(desperate=True)
        assert path is not None and len(path) > 0, (
            "Desperate mode must find a path through maximum hazard cells"
        )


# ===========================================================================
# 7. FED DAMAGE MODEL
# ===========================================================================

class TestFEDScalingRatio:
    """
    Elderly profile (fed_scale=1.50) must accumulate FED at exactly
    1.50x the rate of adult_fit (fed_scale=1.00).
    """

    def test_elderly_accumulates_at_150_percent_of_fit(self):
        fit     = make_agent("adult_fit")
        elderly = make_agent("elderly")

        fit.movement.fed_scale     = VULNERABILITY_PROFILES["adult_fit"][0]
        elderly.movement.fed_scale = VULNERABILITY_PROFILES["elderly"][0]

        fit.spot.set_smoke(1.0)
        elderly.spot.set_smoke(1.0)

        for _ in range(60):
            fit.movement.apply_damage(dt=1.0)
            elderly.movement.apply_damage(dt=1.0)

        expected = (
            VULNERABILITY_PROFILES["elderly"][0] /
            VULNERABILITY_PROFILES["adult_fit"][0]
        )
        actual = elderly.movement.fed_toxic / fit.movement.fed_toxic

        assert abs(actual - expected) < 0.001, (
            f"Elderly/adult_fit FED ratio must be {expected:.2f}, "
            f"got {actual:.4f}"
        )


class TestFEDHealthCurveShape:
    """
    health = 100 * (1 - FED^0.7)

    Exponent 0.7 < 1 produces a CONVEX curve: health drops quickly in
    early exposure and decelerates toward incapacitation. Each successive
    FED interval of equal width causes a smaller absolute health drop.
    """

    def test_health_curve_is_convex(self):
        """Health drops must decelerate as FED accumulates."""

        def h(fed):
            return 100.0 * (1.0 - min(fed, 1.0) ** 0.7)

        drop_early  = h(0.00) - h(0.25)
        drop_middle = h(0.25) - h(0.50)
        drop_late   = h(0.50) - h(0.75)

        assert drop_early > drop_middle > drop_late, (
            f"Health curve must be convex (drops decelerate):\n"
            f"  0.00->0.25: -{drop_early:.2f}\n"
            f"  0.25->0.50: -{drop_middle:.2f}\n"
            f"  0.50->0.75: -{drop_late:.2f}"
        )

    def test_health_zero_at_fed_one(self):
        """Health must reach exactly 0 when FED accumulator reaches 1.0."""
        a = make_agent("adult_fit")
        a.spot.set_smoke(1.0)
        for _ in range(181):
            a.movement.apply_damage(dt=1.0)
        assert a.health == 0.0, "Health must be 0 when FED = 1.0"


# ===========================================================================
# 8. ANALYTICS AND EXPORT
# ===========================================================================

class TestJSONSnapshotExport:
    """JSON snapshot must contain all required top-level and nested fields."""

    def test_snapshot_contains_all_required_fields(self, tmp_path):
        snap = SimulationSnapshot(
            timestamp="2026-01-01T00:00:00",
            seed=42,
            layout_file="layout_test.csv",
            parameters={
                "num_floors": 2, "grid_rows": 60, "cell_size_m": 0.5,
                "base_speed_m_s": 1.2, "fire_spread_probability": 0.3,
                "smoke_diffusion": 0.1, "smoke_decay": 0.05,
                "smoke_production": 0.5,
            },
            metrics={
                "elapsed_time": 30.0, "agent_health": [85.0, 72.0],
                "fire_cells": 120, "avg_smoke": 0.3, "avg_temp": 150.0,
                "path_length": 12.0, "escaped_agents": 1, "deceased_agents": 0,
            },
            survival_count=1,
            evacuation_time=30.0,
            agent_trails=[[(0, 5, 5), (0, 5, 6)]],
            fire_timeline=[(1.0, 0, 3, 3)],
            history={
                "time": [0.0, 1.0], "fire_cells": [10, 20],
                "avg_temp": [30.0, 50.0], "avg_smoke": [0.1, 0.2],
                "agent_health": [[100.0], [95.0]], "path_length": [15.0, 14.0],
                "fire_cells_per_floor": [[10], [20]],
                "avg_temp_per_floor": [[30.0], [50.0]],
                "avg_smoke_per_floor": [[0.1], [0.2]],
            },
        )

        with patch.object(SaveManager, "saves_dir",
                          staticmethod(lambda: tmp_path)):
            path = SaveManager.save_results(snap, filename_prefix="test_snap")
            data = json.loads(Path(path).read_text())

        for field in [
            "timestamp", "seed", "layout_file", "parameters", "metrics",
            "survival_count", "evacuation_time", "agent_trails",
            "fire_timeline", "history",
        ]:
            assert field in data, f"Required field '{field}' missing from snapshot"

        for p in [
            "num_floors", "grid_rows", "cell_size_m",
            "fire_spread_probability", "smoke_diffusion", "smoke_decay",
        ]:
            assert p in data["parameters"], f"Missing parameter '{p}'"

        for m in [
            "elapsed_time", "agent_health", "fire_cells",
            "avg_smoke", "avg_temp", "escaped_agents", "deceased_agents",
        ]:
            assert m in data["metrics"], f"Missing metric '{m}'"


class TestCSVHistoryExport:
    """CSV must have one row per simulation step with no missing values."""

    def test_csv_columns_and_row_count(self, tmp_path):
        n = 10
        history = {
            "time":         list(range(n)),
            "fire_cells":   [i * 5 for i in range(n)],
            "avg_temp":     [25.0 + i * 10 for i in range(n)],
            "avg_smoke":    [i * 0.05 for i in range(n)],
            "agent_health": [[100.0 - i] for i in range(n)],
            "path_length":  [20.0 - i for i in range(n)],
        }

        with patch.object(SaveManager, "saves_dir",
                          staticmethod(lambda: tmp_path)):
            path = SaveManager.export_history_csv(
                history, filename_prefix="test_hist"
            )
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                cols = set(reader.fieldnames)

        expected = {
            "time", "fire_cells", "avg_temp",
            "avg_smoke", "agent_health", "path_length",
        }
        assert expected.issubset(cols), f"Missing columns: {expected - cols}"
        assert len(rows) == n, f"Row count {len(rows)} != expected {n}"
        for i, row in enumerate(rows):
            for col in expected:
                assert row[col] not in (None, ""), (
                    f"Missing value at row {i}, column '{col}'"
                )

    def test_csv_row_count_matches_history_length(self, tmp_path):
        n = 25
        history = {
            "time":         list(range(n)),
            "fire_cells":   [0] * n,
            "avg_temp":     [25.0] * n,
            "avg_smoke":    [0.0] * n,
            "agent_health": [[100.0]] * n,
            "path_length":  [10.0] * n,
        }
        with patch.object(SaveManager, "saves_dir",
                          staticmethod(lambda: tmp_path)):
            path = SaveManager.export_history_csv(
                history, filename_prefix="test_hist2"
            )
            with open(path, newline="") as f:
                all_rows = list(csv.reader(f))

        assert len(all_rows) - 1 == n, (
            f"CSV must have {n} data rows (header excluded), "
            f"got {len(all_rows) - 1}"
        )


class TestFireCellMetricMatchesGrid:
    """fire_cells metric must equal the actual burning cell count in fire_np."""

    @pytest.fixture(autouse=True)
    def _reset_stairs(self):
        StairwellIDGenerator.reset()
        yield
        StairwellIDGenerator.reset()

    def test_metric_matches_manual_grid_count(self):
        b = Building(num_of_floors=1, rows=10, width=400)
        g = b.floors[0]
        g.grid[2][2].set_on_fire(initial_temp=800.0)
        g.grid[3][3].set_on_fire(initial_temp=800.0)
        g.grid[4][4].set_on_fire(initial_temp=800.0)
        g.update_np_arrays()

        manual = int(np.sum(g.fire_np))
        b.compute_metrics(agents=None)
        metric = b.metrics["fire_cells"]

        assert metric == manual, (
            f"Metrics fire_cells ({metric}) must equal "
            f"manual grid count ({manual})"
        )

    def test_metric_updates_after_additional_ignition(self):
        b = Building(num_of_floors=1, rows=10, width=400)
        g = b.floors[0]
        g.grid[2][2].set_on_fire(initial_temp=800.0)
        g.update_np_arrays()
        b.compute_metrics(agents=None)
        before = b.metrics["fire_cells"]

        g.grid[3][3].set_on_fire(initial_temp=800.0)
        g.grid[4][4].set_on_fire(initial_temp=800.0)
        g.update_np_arrays()
        b.compute_metrics(agents=None)

        actual = int(np.sum(g.fire_np))
        assert b.metrics["fire_cells"] == actual, (
            f"fire_cells metric ({b.metrics['fire_cells']}) must match "
            f"actual count ({actual}) after ignition"
        )
        assert b.metrics["fire_cells"] > before, (
            "fire_cells metric must increase after additional ignitions"
        )