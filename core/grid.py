import pygame
from utils.utilities import Color, get_neighbors

class Grid:
    def __init__(self, rows, width):
        self.rows = rows
        self.width = width
        self.cell_size = width // rows

        self.grid = self._make_grid()
        
        # OPTIMIZATION: Precompute neighbor references
        self.neighbor_map = self._precompute_neighbors()
        
        self.fire_sources = set()
        self.start = None
        self.exits = set()

    def add_exit(self, spot):
        self.exits.add(spot)

    def remove_exit(self, spot):
        self.exits.discard(spot)

    def clear_exits(self):
        self.exits.clear()

    def is_exit(self, spot):
        return spot in self.exits

    def _make_grid(self):
        from core.spot import Spot
        grid = []
        for r in range(self.rows):
            grid.append([])
            for c in range(self.rows):
                grid[r].append(Spot(r, c, self.cell_size))
        return grid

    def _precompute_neighbors(self):
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

    def get_spot(self, r, c):
        if self.in_bounds(r, c):
            return self.grid[r][c]
        return None

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.rows
    
    def set_material(self, r, c, material_id):
        spot = self.get_spot(r, c)
        if spot:
            spot.set_material(material_id)
    
    def clear_simulation_visuals(self):
        for row in self.grid:
            for spot in row:
                if spot.is_fire():
                    spot.extinguish_fire()
                    spot.remove_fire_source()
        self.fire_sources.clear()
    
    def draw_grid(self, win):
        gap = self.cell_size
        width = self.width
        # Optimization: Don't recreate color tuple every line
        color = Color.GREY.value
        for i in range(self.rows):
            pygame.draw.line(win, color, (0, i * gap), (width, i * gap))
            pygame.draw.line(win, color, (i * gap, 0), (i * gap, width))
    
    def draw(self, win, tools_panel=None, bg_image=None):
        if bg_image:
            win.blit(bg_image, (0, 0))
        for row in self.grid:
            for spot in row:
                spot.draw(win)
        self.draw_grid(win)
        
        if tools_panel:
            tools_panel.draw(win)
    
    def get_clicked_pos(self, pos):
        gap = self.cell_size
        x, y = pos
        if x < self.width:
            row = y // gap
            col = x // gap
            return row, col
        return None, None
    
    def update_geometry(self, cell_size):
        self.cell_size = cell_size
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid[r][c]
                spot.x = c * cell_size
                spot.y = r * cell_size
                spot.width = cell_size