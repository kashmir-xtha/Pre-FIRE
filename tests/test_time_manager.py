"""Tests for TimeManager state machine."""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

# TimeManager uses pygame.time.Clock, so we need pygame initialized minimally
import pygame
pygame.init()

from utils.time_manager import TimeManager


@pytest.fixture
def tm():
    return TimeManager(fps=60, step_size=1)


class TestTimeManagerInit:
    '''TimeManager should initialize with expected default state.'''
    def test_starts_unpaused(self, tm):
        assert tm.paused is False

    def test_starts_not_step_mode(self, tm):
        assert tm.step_by_step is False

    def test_initial_total_time_zero(self, tm):
        assert tm.get_total_time() == 0.0

    def test_initial_step_zero(self, tm):
        assert tm.get_simulation_step() == 0


class TestPauseToggle:
    def test_toggle_pause_on(self, tm):
        result = tm.toggle_pause()
        assert result is True
        assert tm.is_paused() is True

    def test_toggle_pause_off(self, tm):
        tm.toggle_pause()  # on
        result = tm.toggle_pause()  # off
        assert result is False
        assert tm.is_paused() is False

    def test_set_paused(self, tm):
        tm.set_paused(True)
        assert tm.paused is True
        tm.set_paused(False)
        assert tm.paused is False

    def test_paused_blocks_update(self, tm):
        tm.set_paused(True)
        result = tm.update()
        assert result is False
        # Step counter should NOT advance
        assert tm.get_simulation_step() == 0


class TestStepMode:
    def test_toggle_step_mode_on(self, tm):
        result = tm.toggle_step_mode()
        assert result is True
        assert tm.is_step_mode() is True

    def test_step_mode_unpauses(self, tm):
        tm.set_paused(True)
        tm.toggle_step_mode()
        assert tm.paused is False

    def test_step_mode_blocks_without_request(self, tm):
        tm.toggle_step_mode()
        result = tm.update()
        assert result is False

    def test_step_mode_advances_on_request(self, tm):
        tm.toggle_step_mode()
        tm.request_next_step()
        result = tm.update()
        assert result is True
        assert tm.get_simulation_step() == 1

    def test_step_request_consumed(self, tm):
        tm.toggle_step_mode()
        tm.request_next_step()
        tm.update()  # consume
        # Next update should block again
        result = tm.update()
        assert result is False

    def test_double_request_rejected(self, tm):
        tm.toggle_step_mode()
        assert tm.request_next_step() is True
        assert tm.request_next_step() is False  # already pending

    def test_request_outside_step_mode_rejected(self, tm):
        assert tm.request_next_step() is False

    def test_get_update_count_step_mode(self, tm):
        tm.toggle_step_mode()
        assert tm.get_update_count() == 1


class TestSpeedMultiplier:
    def test_set_speed_2x(self, tm):
        result = tm.set_speed(2.0)
        assert result == 2
        assert tm.get_step_size() == 2

    def test_set_speed_floor_1(self, tm):
        result = tm.set_speed(0.1)
        assert result == 1  # minimum 1

    def test_get_update_count_normal(self, tm):
        tm.set_speed(3.0)
        assert tm.get_update_count() == 3


class TestResetTimer:
    def test_reset_zeroes_counters(self, tm):
        # Advance the timer
        tm.total_time = 42.0
        tm.simulation_step = 100
        tm.frame_count = 50
        tm.reset_timer()
        assert tm.get_total_time() == 0.0
        assert tm.get_simulation_step() == 0
        assert tm.frame_count == 0


class TestNormalUpdate:
    def test_update_advances_step(self, tm):
        tm.update()
        assert tm.get_simulation_step() == 1

    def test_update_returns_true(self, tm):
        assert tm.update() is True

    def test_total_time_increases(self, tm):
        import time
        time.sleep(0.02)  # ensure measurable delta
        tm.update()
        assert tm.get_total_time() > 0.0
