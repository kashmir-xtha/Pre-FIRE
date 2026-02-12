from typing import Any, List, Optional, TYPE_CHECKING, Tuple

import numpy as np
import pygame

from utils.utilities import Color, get_neighbors

if TYPE_CHECKING:
    from core.spot import Spot

# Global constant for grid color - accessed once at import time
GRID_COLOR = Color.GREY.value

class Grid:
    def __init__(self, rows: int, width: int) -> None:
        self.rows = rows
        self.width = width
        self.cell_size = width // rows

        self.grid = self._make_grid()
        
        # OPTIMIZATION: Precompute neighbor references
        self.neighbor_map = self._precompute_neighbors()
        
        self.fire_sources = set()
        self.start = None
        self.exits = set()

        # Numpy Arrays
        self.temp_np = np.zeros((rows, rows), dtype=np.float32)
        self.smoke_np = np.zeros((rows, rows), dtype=np.float32)
        self.fuel_np = np.zeros((rows, rows), dtype=np.float32)
        self.fire_np = np.zeros((rows, rows), dtype=np.bool_)

        # Material caches (rebuild on edit/reset)
        self.material_cache_dirty = True
        self.heat_transfer_np = np.zeros((rows, rows), dtype=np.float32)
        self.cooling_rate_np = np.zeros((rows, rows), dtype=np.float32)
        self.heat_capacity_np = np.ones((rows, rows), dtype=np.float32)
        self.ignition_temp_np = np.full((rows, rows), float("inf"), dtype=np.float32)
        self.is_barrier_np = np.zeros((rows, rows), dtype=np.bool_)
        self.is_start_np = np.zeros((rows, rows), dtype=np.bool_)
        self.is_end_np = np.zeros((rows, rows), dtype=np.bool_)

        self.ensure_material_cache()

    def add_exit(self, spot: "Spot") -> None:
        self.exits.add(spot)

    def remove_exit(self, spot: "Spot") -> None:
        self.exits.discard(spot)

    def clear_exits(self) -> None:
        self.exits.clear()

    def is_exit(self, spot: "Spot") -> bool:
        return spot in self.exits

    def _make_grid(self) -> List[List["Spot"]]:
        from core.spot import Spot
        grid = []
        for r in range(self.rows):
            grid.append([])
            for c in range(self.rows):
                grid[r].append(Spot(r, c, self.cell_size))
        return grid

    def _precompute_neighbors(self) -> List[List[List["Spot"]]]:
        """
        Optimization: Store direct references to neighbor Spot objects.
        This avoids calling get_neighbors() and doing grid[r][c] lookups 
        every single frame for every single cell.
        """
        map_data = []
        rows = self.rows
        # Localize grid for speed
        grid = self.grid
        
        for r in range(rows):
            row_map = []
            for c in range(rows):
                neighbors = []
                # Use the utility to get coords, but store the OBJECTS
                for nr, nc in get_neighbors(r, c, rows, rows):
                    neighbors.append(grid[nr][nc])
                row_map.append(neighbors)
            map_data.append(row_map)
        return map_data

    def update_np_arrays(self) -> None:
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid[r][c]
                self.temp_np[r, c] = spot.temperature
                self.smoke_np[r, c] = spot.smoke
                self.fuel_np[r, c] = spot.fuel
                self.fire_np[r, c] = spot.is_fire()
                
    def get_spot(self, r: int, c: int) -> Optional["Spot"]:
        if self.in_bounds(r, c):
            return self.grid[r][c]
        return None

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.rows
    
    def set_material(self, r: int, c: int, material_id) -> None:
        spot = self.get_spot(r, c)
        if spot:
            spot.set_material(material_id)
            self.mark_material_cache_dirty()

    def mark_material_cache_dirty(self) -> None:
        self.material_cache_dirty = True

    def ensure_material_cache(self) -> None:
        if self.material_cache_dirty:
            self._rebuild_material_cache()

    def _rebuild_material_cache(self) -> None:
        rows = self.rows
        grid = self.grid

        for r in range(rows):
            row_spots = grid[r]
            for c in range(rows):
                spot = row_spots[c]
                props = spot.get_material_properties()

                self.heat_transfer_np[r, c] = props.get("heat_transfer", 0.5)
                self.cooling_rate_np[r, c] = props.get("cooling_rate", 0.01)
                self.heat_capacity_np[r, c] = props.get("heat_capacity", 1.0)
                self.ignition_temp_np[r, c] = props.get("ignition_temp", float("inf"))
                self.is_barrier_np[r, c] = spot.is_barrier()
                self.is_start_np[r, c] = spot.is_start()
                self.is_end_np[r, c] = spot.is_end()

        self.material_cache_dirty = False
    
    def clear_simulation_visuals(self) -> None:
        for row in self.grid:
            for spot in row:
                if spot.is_fire():
                    spot.extinguish_fire()
                    spot.remove_fire_source()
        self.fire_sources.clear()
    
    def draw_grid(self, win: pygame.Surface) -> None:
        gap = self.cell_size
        width = self.width
        # Optimization: Use pre-resolved global color constant
        color = GRID_COLOR
        for i in range(self.rows):
            pygame.draw.line(win, color, (0, i * gap), (width, i * gap))
            pygame.draw.line(win, color, (i * gap, 0), (i * gap, width))
    
    def draw(
        self,
        win: pygame.Surface,
        tools_panel: Optional[Any] = None,
        bg_image: Optional[pygame.Surface] = None,
    ) -> None:
        if bg_image:
            win.blit(bg_image, (0, 0))
        for row in self.grid:
            for spot in row:
                spot.draw(win)
        self.draw_grid(win)
        
        if tools_panel:
            tools_panel.draw(win)
    
    def get_clicked_pos(self, pos: Tuple[int, int]) -> Tuple[Optional[int], Optional[int]]:
        gap = self.cell_size
        x, y = pos
        if x < self.width:
            row = y // gap
            col = x // gap
            return row, col
        return None, None
    
    def update_geometry(self, cell_size: int) -> None:
        self.cell_size = cell_size
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid[r][c]
                spot.x = c * cell_size
                spot.y = r * cell_size
                spot.width = cell_size