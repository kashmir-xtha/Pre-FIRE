from typing import List, Optional, TYPE_CHECKING
from core.grid import Grid
from core.spot import Spot

if TYPE_CHECKING:
    from core.agent import Agent

class Building:
    def __init__(self, num_of_floors: int, rows: int, width: int) -> None:
        self.num_floors = num_of_floors
        self.rows = rows
        self.width = width
        self.floors: List[Grid] = [
            Grid(rows, width, floor=f) for f in range(num_of_floors)
        ]
        self.current_floor = 0

    def get_floor(self, floor_num: int):
        if 0 <= floor_num < self.num_floors:
            return self.floors[floor_num]
        else:
            raise ValueError("Invalid floor number")
        
    def find_stairwell(self, floor_num: int) -> Optional[tuple]:
        pass

    def move_agent_between_floors(self, agent: 'Agent', from_floor: int, to_floor: int) -> bool:
        pass

    def update_all_floor(self) -> None:
        for floor in self.floors:
            floor.update()
    
    def reset_all_floors(self) -> None:
        for floor in self.floors:
            floor.reset()