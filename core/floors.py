from typing import List, Optional, TYPE_CHECKING
from core.grid import Grid
from core.spot import Spot
from environment.smoke import spread_smoke
from environment.fire import do_temperature_update
from environment.fire import update_fire_with_materials
from utils.utilities import StairwellIDGenerator

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

    def move_agent_between_floors(self, agent: 'Agent', from_floor: int, to_floor: int, stair_id: int) -> bool:
        if not (0 <= from_floor < self.num_floors and 0 <= to_floor < self.num_floors):
            return False

        dest_spot = StairwellIDGenerator.get_connected_spot(stair_id, to_floor)
        if dest_spot is None:
            return False

        agent.current_floor = to_floor
        agent.grid = self.floors[to_floor]
        agent.spot = dest_spot
        agent.barrier_adjacent = agent._compute_barrier_adjacency()
        return True

    def update_all_floor(self, update_dt: float) -> None:
        for floor in self.floors:
            do_temperature_update(floor, update_dt)
            update_fire_with_materials(floor, update_dt)
            spread_smoke(floor, update_dt)
            floor.update_np_arrays() 
            floor.update()
    
    def reset_all_floors(self) -> None:
        for floor in self.floors:
            floor.reset()