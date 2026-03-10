"""Tests for agent vision, perception, and memory systems."""
import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import Agent
from core.grid import Grid


@pytest.fixture
def agent():
    """Agent at (5,5) on a 10x10 grid."""
    grid = Grid(rows=10, width=400, floor=0)
    exit_spot = grid.grid[9][9]
    exit_spot.make_end()
    grid.add_exit(exit_spot)
    grid.ensure_material_cache()
    return Agent(grid, grid.grid[5][5], floor=0)


class TestVisibilityRadius:
    """compute_visibility_radius responds to smoke at agent's position."""

    def test_clear_air_max_radius(self, agent):
        """No smoke -> full base radius."""
        radius = agent.vision.compute_visibility_radius()
        cell = agent.grid.cell_size
        expected = 20 * cell  # base radius
        assert radius == pytest.approx(expected)

    def test_full_smoke_min_radius(self, agent):
        """Smoke=1.0 -> 30 % of base, but clamped to 3-cell minimum."""
        agent.spot.set_smoke(1.0)
        radius = agent.vision.compute_visibility_radius()
        cell = agent.grid.cell_size
        min_radius = 3 * cell
        assert radius == pytest.approx(max(min_radius, 20 * cell * 0.3))

    def test_half_smoke_intermediate(self, agent):
        """Smoke=0.5 -> 65 % of base."""
        agent.spot.set_smoke(0.5)
        radius = agent.vision.compute_visibility_radius()
        cell = agent.grid.cell_size
        expected = 20 * cell * (1.0 - 0.5 * 0.7)
        assert radius == pytest.approx(expected)

    def test_radius_never_below_minimum(self, agent):
        """Even extreme smoke can't go below 3-cell radius."""
        agent.spot.set_smoke(1.0)
        radius = agent.vision.compute_visibility_radius()
        cell = agent.grid.cell_size
        assert radius >= 3 * cell


class TestSmokeDetection:
    """detect_smoke relies on the smoke_detected flag."""

    def test_no_smoke_not_detected(self, agent):
        agent.smoke_detected = False
        assert agent.vision.detect_smoke() is False

    def test_flag_set_detected(self, agent):
        agent.smoke_detected = True
        assert agent.vision.detect_smoke() is True


class TestFireDetection:
    """detect_fire relies on known_fire sparse grid."""

    def test_no_known_fire(self, agent):
        assert agent.vision.detect_fire() is False

    def test_known_fire_detected(self, agent):
        agent.known_fire[3, 3] = True
        assert agent.vision.detect_fire() is True


class TestImminentDanger:
    """detect_imminent_danger checks nearby hazards."""

    def test_no_hazard_safe(self, agent):
        assert agent.vision.detect_imminent_danger() is False

    def test_fire_at_current_spot(self, agent):
        agent.spot.set_on_fire()
        assert agent.vision.detect_imminent_danger() is True

    def test_high_smoke_at_spot(self, agent):
        agent.spot.set_smoke(0.5)
        assert agent.vision.detect_imminent_danger() is True

    def test_high_temp_at_spot(self, agent):
        agent.spot.set_temperature(150.0)
        assert agent.vision.detect_imminent_danger() is True

    def test_nearby_known_fire(self, agent):
        """Known fire 2 cells away (within default radius of 3) triggers danger."""
        agent.known_fire[5, 7] = True
        assert agent.vision.detect_imminent_danger(max_distance_cells=3) is True

    def test_distant_fire_not_imminent(self, agent):
        """Known fire at (0,0), far from agent at (5,5), not imminent."""
        agent.known_fire[0, 0] = True
        assert agent.vision.detect_imminent_danger(max_distance_cells=3) is False

    def test_nearby_known_smoke(self, agent):
        """Known smoke > 0.1 within radius triggers danger."""
        agent.known_smoke[5, 7] = 0.5
        assert agent.vision.detect_imminent_danger(max_distance_cells=3) is True

    def test_nearby_known_high_temp(self, agent):
        """Known temp > 100 within radius triggers danger."""
        agent.known_temp[5, 7] = 150.0
        assert agent.vision.detect_imminent_danger(max_distance_cells=3) is True


class TestPositionSafety:
    """is_position_safe checks current spot."""

    def test_normal_spot_safe(self, agent):
        assert agent.vision.is_position_safe() is True

    def test_fire_spot_unsafe(self, agent):
        agent.spot.set_on_fire()
        assert agent.vision.is_position_safe() is False

    def test_heavy_smoke_unsafe(self, agent):
        agent.spot.set_smoke(0.9)
        assert agent.vision.is_position_safe() is False

    def test_high_temp_unsafe(self, agent):
        agent.spot.set_temperature(150.0)
        assert agent.vision.is_position_safe() is False

    def test_moderate_smoke_safe(self, agent):
        agent.spot.set_smoke(0.5)
        assert agent.vision.is_position_safe() is True


class TestMemoryUpdate:
    """update_memory scans visible area and updates knowledge arrays."""

    def test_memory_updates_smoke(self, agent):
        """Nearby smoke should be reflected in known_smoke after update."""
        agent.grid.grid[5][6].set_smoke(0.7)
        # Force immediate update by resetting timer
        agent.vision.update_timer = agent.vision.update_interval
        agent.vision.update_memory(dt=agent.vision.update_interval)
        assert agent.known_smoke[5, 6] == pytest.approx(0.7)

    def test_memory_starts_unknown(self, agent):
        """Before update, known_smoke should be -1.0 (unknown)."""
        assert agent.known_smoke[0, 0] == -1.0

    def test_smoke_detection_flag_set(self, agent):
        """Visible smoke should set smoke_detected flag."""
        agent.grid.grid[5][6].set_smoke(0.7)
        agent.vision.update_timer = agent.vision.update_interval
        agent.vision.update_memory(dt=agent.vision.update_interval)
        assert agent.smoke_detected is True
