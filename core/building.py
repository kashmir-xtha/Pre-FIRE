from typing import List, Optional, TYPE_CHECKING
import numpy as np
from core.grid import Grid
from core.spot import Spot
from environment.smoke import spread_smoke
from environment.fire import do_temperature_update
from environment.fire import update_fire_with_materials
from utils.utilities import StairwellIDGenerator

if TYPE_CHECKING:
    from core.agent.agent import Agent

class Building:
    """Multi-floor building composed of Grid layers.

    Manages floor switching, inter-floor agent movement via stairwells,
    and aggregated per-floor / building-wide simulation metrics.
    """

    def __init__(self, num_of_floors: int, rows: int, width: int) -> None:
        self.num_floors = num_of_floors
        self.rows = rows
        self.width = width
        self.floors: List[Grid] = [
            Grid(rows, width, floor=f) for f in range(num_of_floors)
        ]
        self.current_floor = 0
        
        # Metrics
        self.metrics = {
            'elapsed_time': 0,
            'agent_health': 0,
            'fire_cells': 0,               # building-wide total
            'fire_cells_per_floor': [],    # [floor_0, floor_1, ...]
            'avg_smoke': 0,                # building-wide average
            'avg_smoke_per_floor': [],     # [floor_0, floor_1, ...]
            'avg_temp': 20,                # building-wide average
            'avg_temp_per_floor': [],      # [floor_0, floor_1, ...]
            'path_length': 0
        }

    def get_floor(self, floor_num: int) -> Grid:
        if 0 <= floor_num < self.num_floors:
            return self.floors[floor_num]
        else:
            raise ValueError("Invalid floor number")
        
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
        self._transfer_inter_floor(update_dt)
    
    def compute_metrics(self, agents: Optional[List['Agent']] = None) -> None:
        """Compute and aggregate metrics across all floors."""
        # Agent health and path length (building-wide averages)
        if agents:
            self.metrics['agent_health'] = sum(a.health for a in agents) / len(agents)
            # Average path length across all agents (building-wide)
            total_path_length = sum(len(a.path) for a in agents)
            self.metrics['path_length'] = total_path_length // len(agents) if agents else 0
        
        # Aggregate metrics across all floors
        total_fire_cells = 0
        total_temps = []
        total_smokes = []
        fire_per_floor = []
        temp_per_floor = []
        smoke_per_floor = []
        
        cells_per_floor = self.rows * self.rows
        
        for floor in self.floors:
            # Count fire cells per floor
            if hasattr(floor, "fire_np"):
                fire_count = int(np.count_nonzero(floor.fire_np))
                avg_temp = float(np.mean(floor.temp_np))
                avg_smoke = float(np.mean(floor.smoke_np))
            else:
                fire_count = 0
                total_temp = 0
                total_smoke = 0
                for r in range(self.rows):
                    for c in range(self.rows):
                        if floor.grid[r][c].is_fire():
                            fire_count += 1
                        total_temp += floor.grid[r][c].temperature
                        total_smoke += floor.grid[r][c].smoke
                avg_temp = total_temp / cells_per_floor
                avg_smoke = total_smoke / cells_per_floor
            
            total_fire_cells += fire_count
            total_temps.append(avg_temp)
            total_smokes.append(avg_smoke)
            fire_per_floor.append(fire_count)
            temp_per_floor.append(avg_temp)
            smoke_per_floor.append(avg_smoke)
        
        # Aggregate building-wide metrics
        self.metrics['fire_cells'] = total_fire_cells
        self.metrics['fire_cells_per_floor'] = fire_per_floor
        self.metrics['avg_temp'] = float(np.mean(total_temps)) if total_temps else 20.0
        self.metrics['avg_temp_per_floor'] = temp_per_floor
        self.metrics['avg_smoke'] = float(np.mean(total_smokes)) if total_smokes else 0.0
        self.metrics['avg_smoke_per_floor'] = smoke_per_floor 

    def _transfer_inter_floor(self, dt: float) -> None:
        """
        Transfer smoke and heat between floors via stairwell spots.
        Uses gradient-driven diffusion (like Fick's law) so smoke is conserved — what leaves one floor arrives on the other.
        Smoke is biased upward (buoyancy), but the net flow is always driven by the concentration difference, preventing recycling.
        """
        from utils.helpers import get_neighbors

        # Upward bias: smoke rises, so upward diffusion coefficient is stronger
        SMOKE_DIFFUSION_UP   = 0.25   # drives flow from lower → upper when lower > upper
        SMOKE_DIFFUSION_DOWN = 0.1   # drives flow from upper → lower when upper > lower
        HEAT_TRANSFER_UP     = 0.05
        HEAT_TRANSFER_DOWN   = 0.02
        NEIGHBOR_BLEED       = 0.3

        for stair_id, floor_spots in StairwellIDGenerator.stairs.items():
            floor_nums = sorted(floor_spots.keys())

            for i in range(len(floor_nums) - 1):
                lower_floor_num = floor_nums[i]
                upper_floor_num = floor_nums[i + 1]

                lower_spot = floor_spots[lower_floor_num]
                upper_spot = floor_spots[upper_floor_num]
                lower_floor = self.floors[lower_floor_num]
                upper_floor = self.floors[upper_floor_num]

                lr, lc = lower_spot.row, lower_spot.col
                ur, uc = upper_spot.row, upper_spot.col

                lower_smoke = float(lower_floor.smoke_np[lr, lc])
                upper_smoke = float(upper_floor.smoke_np[ur, uc])

                # Gradient-driven: only transfer in the direction of the gradient, biased upward 
                # Net transfer is conserved (what leaves one floor arrives on the other — no recycling)
                smoke_diff = lower_smoke - upper_smoke

                if smoke_diff > 0:
                    # Lower has more smoke — flows upward (buoyancy + gradient)
                    transfer = smoke_diff * SMOKE_DIFFUSION_UP * dt
                else:
                    # Upper has more smoke — small downward flow (gravity/backdraft)
                    transfer = smoke_diff * SMOKE_DIFFUSION_DOWN * dt  # negative * negative = positive going down

                # Conserved transfer: lower loses exactly what upper gains
                new_lower = float(np.clip(lower_smoke - transfer, 0.0, 1.0))
                new_upper = float(np.clip(upper_smoke + transfer, 0.0, 1.0))

                lower_floor.smoke_np[lr, lc] = new_lower
                upper_floor.smoke_np[ur, uc] = new_upper
                lower_floor.grid[lr][lc]._smoke = new_lower
                upper_floor.grid[ur][uc]._smoke = new_upper

                # Bleed arriving smoke into neighbors on the upper floor
                if transfer > 0.001:
                    neighbors = get_neighbors(ur, uc, upper_floor.rows, upper_floor.rows)
                    passable = [
                        (nr, nc) for nr, nc in neighbors
                        if not upper_floor.is_barrier_np[nr, nc]
                    ]
                    if passable:
                        bleed_each = (transfer * NEIGHBOR_BLEED) / len(passable)
                        for nr, nc in passable:
                            val = float(np.clip(upper_floor.smoke_np[nr, nc] + bleed_each, 0.0, 1.0))
                            upper_floor.smoke_np[nr, nc] = val
                            upper_floor.grid[nr][nc]._smoke = val

                # Heat transfer 
                temp_diff = lower_spot.temperature - upper_spot.temperature
                if temp_diff > 0:
                    heat_up = temp_diff * HEAT_TRANSFER_UP * dt
                    lower_spot.add_temperature(-heat_up)
                    upper_spot.add_temperature(heat_up)
                else:
                    heat_down = abs(temp_diff) * HEAT_TRANSFER_DOWN * dt
                    upper_spot.add_temperature(-heat_down)
                    lower_spot.add_temperature(heat_down)