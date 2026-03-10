"""Tests for StairwellIDGenerator multi-floor stairwell management."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.grid import Grid
from utils.stairwell_manager import StairwellIDGenerator


@pytest.fixture(autouse=True)
def clean_stairwells():
    StairwellIDGenerator.reset()
    yield
    StairwellIDGenerator.reset()


@pytest.fixture
def grids():
    """Two 10x10 grids representing two floors."""
    return [Grid(rows=10, width=400, floor=f) for f in range(2)]


class TestStairCreation:
    def test_new_stair_returns_id(self):
        sid = StairwellIDGenerator.new_stair()
        assert isinstance(sid, int)

    def test_ids_increment(self):
        s0 = StairwellIDGenerator.new_stair()
        s1 = StairwellIDGenerator.new_stair()
        assert s1 == s0 + 1


class TestStairRegistration:
    def test_add_and_retrieve(self, grids):
        sid = StairwellIDGenerator.new_stair()
        spot0 = grids[0].grid[2][2]
        StairwellIDGenerator.add(sid, 0, spot0)
        assert StairwellIDGenerator.get_connected_spot(sid, 0) is spot0

    def test_get_nonexistent_returns_none(self):
        assert StairwellIDGenerator.get_connected_spot(99, 0) is None

    def test_connected_floors(self, grids):
        '''Floors connected to a stairwell are correctly tracked.'''
        sid = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(sid, 0, grids[0].grid[2][2])
        StairwellIDGenerator.add(sid, 1, grids[1].grid[2][2])
        floors = StairwellIDGenerator.get_connected_floors(sid)
        assert set(floors) == {0, 1}

    def test_spot_marked_as_stairwell(self, grids):
        sid = StairwellIDGenerator.new_stair()
        spot = grids[0].grid[3][3]
        StairwellIDGenerator.add(sid, 0, spot)
        assert spot.is_stairwell is True
        assert spot.stair_id == sid


class TestStairLookup:
    def test_find_stair_at_cell(self, grids):
        sid = StairwellIDGenerator.new_stair()
        spot = grids[0].grid[4][4]
        StairwellIDGenerator.add(sid, 0, spot)
        found = StairwellIDGenerator.find_stair_at_cell(4, 4)
        assert found == sid

    def test_find_stair_at_empty_cell(self):
        assert StairwellIDGenerator.find_stair_at_cell(0, 0) is None

    def test_get_floor_stair_ids(self, grids):
        s0 = StairwellIDGenerator.new_stair()
        s1 = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(s0, 0, grids[0].grid[1][1])
        StairwellIDGenerator.add(s1, 0, grids[0].grid[2][2])
        ids = StairwellIDGenerator.get_floor_stair_ids(0)
        assert ids == sorted([s0, s1])

    def test_next_link_target(self, grids):
        sid = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(sid, 0, grids[0].grid[1][1])
        # sid exists on floor 0 but not floor 1
        target = StairwellIDGenerator.next_link_target(target_floor=1, anchor_floor=0)
        assert target == sid

    def test_next_link_target_none_when_linked(self, grids):
        sid = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(sid, 0, grids[0].grid[1][1])
        StairwellIDGenerator.add(sid, 1, grids[1].grid[1][1])
        # All stairs already linked
        target = StairwellIDGenerator.next_link_target(target_floor=1, anchor_floor=0)
        assert target is None


class TestReset:
    def test_reset_clears_all(self, grids):
        sid = StairwellIDGenerator.new_stair()
        StairwellIDGenerator.add(sid, 0, grids[0].grid[1][1])
        StairwellIDGenerator.reset()
        assert StairwellIDGenerator.get_connected_spot(sid, 0) is None
        assert StairwellIDGenerator.get_floor_stair_ids(0) == []

    def test_ids_restart_after_reset(self):
        StairwellIDGenerator.new_stair()
        StairwellIDGenerator.new_stair()
        StairwellIDGenerator.reset()
        sid = StairwellIDGenerator.new_stair()
        assert sid == 0
