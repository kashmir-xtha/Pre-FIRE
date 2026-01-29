import pygame
from environment.materials import MATERIALS
from utils.utilities import state_value, Color, fire_constants, material_id

class Grid:
    def __init__(self, rows, width):
        self.rows = rows
        self.width = width
        self.cell_size = width // rows

        self.grid = self._make_grid()
        
        self.fire_sources = set()  # Set of (r, c) tuples for fire source spots
        self.start = None
        self.exits = set() # Set of exit spots

    def add_exit(self, spot):
        self.exits.add(spot)

    def remove_exit(self, spot):
        self.exits.discard(spot)

    def clear_exits(self):
        self.exits.clear()

    def is_exit(self, spot):
        return spot in self.exits

    def _make_grid(self):
        # Import here to avoid circular import
        from core.spot import Spot
        grid = []
        for r in range(self.rows):
            grid.append([])
            for c in range(self.rows):
                grid[r].append(Spot(r, c, self.cell_size))
        return grid

    def get_spot(self, r, c):
        if self.in_bounds(r, c):
            return self.grid[r][c]
        return None

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.rows
    
    def set_material(self, r, c, material_id):
        """Set material for a specific spot"""
        spot = self.get_spot(r, c)
        if spot:
            spot.set_material(material_id)
    
    def clear_simulation_visuals(self):
        """Clear all simulation visuals (fire, smoke, path) but keep walls, start, end"""
        for row in self.grid:
            for spot in row:
                if spot.is_fire():
                    spot.extinguish_fire()
                    spot.remove_fire_source()
        self.fire_sources.clear()
    
    def draw_grid(self, win):
        gap = self.cell_size
        for i in range(self.rows):
            pygame.draw.line(win, Color.GREY.value, (0, i * gap), (self.width, i * gap))
            pygame.draw.line(win, Color.GREY.value, (i * gap, 0), (i * gap, self.width))
    
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
        '''
        Docstring for get_clicked_pos
        
        :param pos: This is the event.pos from pygame
        :return: (row, col) tuple corresponding to grid cell clicked
        '''
        gap = self.cell_size
        x, y = pos
        
        # Only process clicks within grid area
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
