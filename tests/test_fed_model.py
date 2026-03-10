"""Tests for Fractional Effective Dose (FED) constants and damage mechanics."""
import math
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import Agent
from core.agent.agent_movement import (
    AgentMovement,
    FED_TOXIC_RATE_PER_SMOKE,
    FED_THERMAL_THRESH_C,
    FED_THERMAL_SCALE_C,
    FED_THERMAL_REF_S,
)
from core.grid import Grid

@pytest.fixture
def agent():
    """Create an agent with 'adult_fit' profile (fed_scale=1.0) for clean math."""
    grid = Grid(rows=10, width=400, floor=0)
    exit_spot = grid.grid[9][9]
    exit_spot.make_end()
    grid.add_exit(exit_spot)
    grid.ensure_material_cache()
    agent = Agent(grid, grid.grid[5][5], floor=0)
    # Use adult_fit so fed_scale == 1.0 (no multiplier noise)
    agent.movement.fed_scale = 1.0
    return agent


class TestFEDToxic:
    """Smoke / CO toxic-dose accumulation."""

    def test_no_smoke_no_accumulation(self, agent):
        """FED_toxic stays 0 when there is no smoke."""
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(25.0)
        agent.movement.apply_damage(dt=1.0)
        assert agent.movement.fed_toxic == 0.0

    def test_full_smoke_incapacitates_in_180s(self, agent):
        """At smoke=1.0, FED_toxic should reach 1.0 after exactly 180 s."""
        agent.spot.set_smoke(1.0)
        agent.spot.set_temperature(25.0)
        dt = 1.0
        for _ in range(180):
            agent.movement.apply_damage(dt=dt)
        assert agent.movement.fed_toxic == pytest.approx(1.0, abs=1e-9)

    def test_half_smoke_takes_360s(self, agent):
        """At smoke=0.5, half the rate -> 360 s to FED_toxic == 1.0."""
        agent.spot.set_smoke(0.5)
        agent.spot.set_temperature(25.0)
        dt = 1.0
        for _ in range(360):
            agent.movement.apply_damage(dt=dt)
        assert agent.movement.fed_toxic == pytest.approx(1.0, abs=1e-9)

    def test_incapacitated_flag_set(self, agent):
        """Agent should be incapacitated once fed_toxic >= 1.0."""
        agent.spot.set_smoke(1.0)
        agent.spot.set_temperature(25.0)
        # 181 steps to guarantee floating-point sum exceeds 1.0
        for _ in range(181):
            agent.movement.apply_damage(dt=1.0)
        assert agent.movement.incapacitated is True


class TestFEDThermal:
    """Convective-heat thermal-dose accumulation."""

    def test_below_threshold_no_accumulation(self, agent):
        """No thermal dose below 60 °C."""
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(59.0)
        agent.movement.apply_damage(dt=1.0)
        assert agent.movement.fed_thermal == 0.0

    def test_at_threshold_no_accumulation(self, agent):
        """At exactly 60 °C (threshold), no thermal dose (code uses strict >)."""
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(60.0)
        agent.movement.apply_damage(dt=1.0)
        assert agent.movement.fed_thermal == 0.0

    def test_just_above_threshold_accumulates(self, agent):
        """Just above 60 °C, thermal FED starts accumulating."""
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(60.01)
        agent.movement.apply_damage(dt=1.0)
        assert agent.movement.fed_thermal > 0.0

    def test_90c_rate_matches_formula(self, agent):
        """At 90 °C (30 °C above threshold), rate = e^1 / 240 ≈ 0.01133."""
        expected_rate = math.exp(30.0 / FED_THERMAL_SCALE_C) / FED_THERMAL_REF_S
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(90.0)
        agent.movement.apply_damage(dt=1.0)
        assert agent.movement.fed_thermal == pytest.approx(expected_rate, rel=1e-6)

    def test_120c_rate_matches_formula(self, agent):
        """At 120 °C (60 °C above threshold), rate = e^2 / 240 ≈ 0.03076."""
        expected_rate = math.exp(60.0 / FED_THERMAL_SCALE_C) / FED_THERMAL_REF_S
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(120.0)
        agent.movement.apply_damage(dt=1.0)
        assert agent.movement.fed_thermal == pytest.approx(expected_rate, rel=1e-6)

    def test_incapacitated_flag_set_thermal(self, agent):
        """Agent incapacitated once fed_thermal >= 1.0."""
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(90.0)  # well above threshold
        rate = math.exp(30.0 / FED_THERMAL_SCALE_C) / FED_THERMAL_REF_S
        steps = int(1.0 / rate) + 2  # enough to exceed 1.0
        for _ in range(steps):
            agent.movement.apply_damage(dt=1.0)
        assert agent.movement.incapacitated is True


class TestFEDHealth:
    """Verify health derivation from FED values."""

    def test_zero_fed_full_health(self, agent):
        """No exposure -> 100 HP."""
        agent.spot.set_smoke(0.0)
        agent.spot.set_temperature(25.0)
        agent.movement.apply_damage(dt=1.0)
        assert agent.health == pytest.approx(100.0)

    def test_incapacitated_zero_health(self, agent):
        """Health drops to 0 once incapacitated."""
        agent.spot.set_smoke(1.0)
        agent.spot.set_temperature(25.0)
        for _ in range(181):
            agent.movement.apply_damage(dt=1.0)
        assert agent.movement.incapacitated is True
        assert agent.health == 0.0

    def test_direct_fire_instant_death(self, agent):
        """Standing in fire -> immediate health=0, FED maxed, incapacitated."""
        agent.spot.set_on_fire()
        agent.movement.apply_damage(dt=1.0)
        assert agent.health == 0.0
        assert agent.movement.fed_toxic == 1.0
        assert agent.movement.fed_thermal == 1.0
        assert agent.movement.incapacitated is True
