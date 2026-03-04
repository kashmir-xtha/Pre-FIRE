"""Stairwell ID generation and management for multi-floor buildings."""
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.spot import Spot


class StairwellIDGenerator:
    """Manages stairwell connections across multiple floors."""
    stairs = {}  # stair_id -> {floor_num: spot}
    _counter = 0

    @classmethod
    def new_stair(cls) -> int:
        """Create a new stairwell ID."""
        sid = cls._counter
        cls._counter += 1
        cls.stairs[sid] = {}
        return sid

    @classmethod
    def add(cls, stair_id: int, floor: int, spot: 'Spot') -> None:
        """Add a spot as part of a stairwell on a specific floor."""
        if stair_id not in cls.stairs:
            cls.stairs[stair_id] = {}
        spot.is_stairwell = True
        spot.stair_id = stair_id
        cls.stairs[stair_id][floor] = spot

    @classmethod
    def get_connected_spot(cls, stair_id: int, to_floor: int) -> Optional['Spot']:
        """Get stairwell spot on destination floor."""
        if stair_id in cls.stairs and to_floor in cls.stairs[stair_id]:
            return cls.stairs[stair_id][to_floor]
        return None

    @classmethod
    def get_connected_floors(cls, stair_id: int) -> List[int]:
        """Get all floors connected by a stairwell ID."""
        if stair_id not in cls.stairs:
            return []
        return list(cls.stairs[stair_id].keys())

    @classmethod
    def find_stair_at_cell(cls, row: int, col: int) -> int | None:
        """Return stair_id for a stairwell at a specific grid cell (row, col)."""
        for stair_id, floors in cls.stairs.items():
            for spot in floors.values():
                if spot.row == row and spot.col == col:
                    return stair_id
        return None

    @classmethod
    def get_floor_stair_ids(cls, floor: int) -> List[int]:
        """Return sorted stair IDs that already have a spot on the given floor."""
        return sorted([stair_id for stair_id, floors in cls.stairs.items() if floor in floors])

    @classmethod
    def next_link_target(cls, target_floor: int, anchor_floor: int = 0) -> int | None:
        """
        Return the next anchor stair_id to link onto target_floor.
        Picks the first stair that exists on anchor_floor but not yet on target_floor.
        """
        anchor_ids = cls.get_floor_stair_ids(anchor_floor)
        for stair_id in anchor_ids:
            floors = cls.stairs.get(stair_id, {})
            if target_floor not in floors:
                return stair_id
        return None
    
    @classmethod
    def reset(cls) -> None:
        """Clear all stairwell data for a new simulation."""
        cls.stairs = {}
        cls._counter = 0
