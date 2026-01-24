import pygame
from environment.materials import MATERIALS
from utils.utilities import state_value, Color, fire_constants, material_id

class Grid:
    def __init__(self, rows, width):
        self.rows = rows
        self.width = width
        self.cell_size = width // rows

        self.grid = self._make_grid()
        self.smoke = [[0.0 for _ in range(rows)] for _ in range(rows)]
        self.state = [[state_value.EMPTY.value for _ in range(rows)] for _ in range(rows)]
        self.temperature = [[fire_constants.AMBIENT_TEMP.value for _ in range(rows)] for _ in range(rows)]  # Default temp 20C
        self.fuel = [[1.0 for _ in range(rows)] for _ in range(rows)]
        self.material = [[0 for _ in range(rows)] for _ in range(rows)]

        self.fire_sources = set()  # Set of (r, c) tuples for fire source spots
        self.start = None
        #self.end = None
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

    def update_state_from_spots(self):
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid[r][c]
                if spot.is_barrier():
                    self.state[r][c] = state_value.WALL.value
                    self.material[r][c] = material_id.CONCRETE.value  # Walls default to concrete
                elif spot.is_start():
                    self.state[r][c] = state_value.START.value
                elif spot.is_end():
                    self.state[r][c] = state_value.END.value
                elif self.state[r][c] != state_value.FIRE.value:  # Don't change material if it's on fire
                # Update material based on color
                    color = spot.color
                    if color == Color.BLACK.value:
                        self.material[r][c] = material_id.CONCRETE.value
                    elif color == MATERIALS[material_id.WOOD]["color"]:
                        self.material[r][c] = material_id.WOOD.value
                    elif color == MATERIALS[material_id.CONCRETE]["color"]:
                        self.material[r][c] = material_id.CONCRETE.value
                    elif color == MATERIALS[material_id.METAL]["color"]:
                        self.material[r][c] = material_id.METAL.value
                    else:
                        self.material[r][c] = material_id.AIR.value

    def apply_fire_to_spots(self):
        """Update spot colors based on current state (fire, material, etc.)"""
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid[r][c]
                current_state = self.state[r][c]
                
                # Don't change start, end, or barrier colors
                if spot.is_start() or spot.is_end() or spot.is_barrier():
                    continue
                
                if (r, c) in self.fire_sources:
                    spot.color = Color.FIRE_COLOR.value
                    self.state[r][c] = state_value.FIRE.value
                    continue

                # If cell is on fire, set to fire color
                if current_state == state_value.FIRE.value:
                    spot.color = Color.FIRE_COLOR.value
                else:
                    mat_id = material_id(self.material[r][c])
                    spot.color = MATERIALS[mat_id]["color"]

    def get_spot(self, r, c):
        if self.in_bounds(r, c):
            return self.grid[r][c]
        return None

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.rows
    
    def set_material(self, r, c, material_id):
        """Set material and update related properties"""
        self.material[r][c] = material_id
        self.fuel[r][c] = MATERIALS[material_id]["fuel"]
        
        # Update visual color if not start/end/barrier
        spot = self.get_spot(r, c)
        if not spot.is_start() and not spot.is_end() and not spot.is_barrier():
            spot.color = MATERIALS[material_id]["color"]

    def apply_materials_to_visuals(self):
        """Update spot colors based on materials"""
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid[r][c]
                if not spot.is_start() and not spot.is_end() and not spot.is_barrier():
                    material = self.material[r][c]
                    spot.color = MATERIALS[material]["color"]
    
    def clear_simulation_visuals(self):
        """Clear all simulation visuals (fire, smoke, path) but keep walls, start, end"""
        # Clear fire from state and visual
        for r in range(self.rows):
            for c in range(self.rows):
                if self.state[r][c] == state_value.FIRE.value:
                    self.state[r][c] = state_value.EMPTY.value
                    # Only reset color if not wall, start, or end
                    if not self.grid[r][c].is_barrier() and not self.grid[r][c].is_start() and not self.grid[r][c].is_end():
                        self.grid[r][c].color = Color.WHITE.value
    
    def draw_grid(self, win):
        gap = self.width // self.rows
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
        gap = self.width // self.rows
        x, y = pos
        
        # Only process clicks within grid area
        if x < self.width:
            row = y // gap
            col = x // gap
            return row, col
        return None, None
