# grid.py
# Import from the corrected firespread module
from firespread import EMPTY, WALL, START, END, FIRE, FIRE_COLOR

class Grid:
    def __init__(self, rows, width):
        self.rows = rows
        self.width = width
        self.cell_size = width // rows

        self.grid = self._make_grid()
        self.smoke = [[0.0 for _ in range(rows)] for _ in range(rows)]
        self.state = [[EMPTY for _ in range(rows)] for _ in range(rows)]

        self.start = None
        self.end = None

    def _make_grid(self):
        # Import here to avoid circular import
        from buildinglayout import Spot
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
                    self.state[r][c] = WALL
                elif spot.is_start():
                    self.state[r][c] = START
                elif spot.is_end():
                    self.state[r][c] = END
                else:
                    self.state[r][c] = EMPTY

    def apply_fire_to_spots(self):
        for r in range(self.rows):
            for c in range(self.rows):
                if self.state[r][c] == FIRE:
                    self.grid[r][c].color = FIRE_COLOR

    def get_spot(self, r, c):
        if 0 <= r < self.rows and 0 <= c < self.rows:
            return self.grid[r][c]
        return None

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.rows
    
    def clear_path_visualization(self):
        """Clear path visualization (purple cells)"""
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid[r][c]
                # Reset purple path cells to white
                if spot.color == (128, 0, 128):  # Purple
                    spot.color = (255, 255, 255)  # White
    
    def clear_simulation_visuals(self):
        """Clear all simulation visuals (fire, smoke, path) but keep walls, start, end"""
        # Clear smoke
        self.smoke = [[0.0 for _ in range(self.rows)] for _ in range(self.rows)]
        
        # Clear fire from state and visual
        for r in range(self.rows):
            for c in range(self.rows):
                if self.state[r][c] == FIRE:
                    self.state[r][c] = EMPTY
                    # Only reset color if not wall, start, or end
                    if not self.grid[r][c].is_barrier() and not self.grid[r][c].is_start() and not self.grid[r][c].is_end():
                        self.grid[r][c].color = (255, 255, 255)
        
        # Clear path visualization
        self.clear_path_visualization()
