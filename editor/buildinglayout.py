import pygame
import pygame_gui
import csv
import sys
from utils.utilities import ToolType, Color
from environment.materials import MATERIALS
from PIL import Image
from editor.tools import ToolsPanel
from utils.utilities import load_layout, save_layout, pick_csv_file, pick_save_csv_file

# ------------------ EDITOR CLASS ------------------
class Editor:
    def __init__(self, win, rows, width, bg_image=None, filename="layout_csv\\layout_1.csv"):
        from core.grid import Grid
        
        self.win = win
        self.rows = rows
        self.original_width = width  # Original grid width 
        self.current_width = width   # Current grid width to allow resizing
        self.bg_image_path = bg_image  # Store the path instead of loading
        self.filename = filename
        
        self.bg_image = None  # No image loaded initially
        self.bg_image_loaded = False
        
        # Grid and state
        self.grid_obj = Grid(rows, width)
        self.tools_panel_width = 200 # fixed width for tools panel
        self.tools_panel = ToolsPanel(self.current_width, 0, self.tools_panel_width, self.current_width) # dynamic sized tool panel
        self.current_tool = "MATERIAL"
        self.current_filename = filename
        
        # Mouse dragging state
        self.mouse_dragging = False
        self.drag_action = None  # 'place' or 'erase'
        self.last_cell = None
        
        # Initialize GUI
        self.manager = pygame_gui.UIManager((self.current_width + self.tools_panel_width, self.current_width)) # dynamic gui button positions
        self._setup_ui_buttons()

        self.window_resized = False
        
        # Try to load existing layout
        # self._load_initial_layout()
    
    def _load_background_image(self, bg_image):
        """Load and prepare background image"""
        try:
            if isinstance(bg_image, str):
                # Load from file path
                import os
                if os.path.exists(bg_image):
                    img = pygame.image.load(bg_image).convert_alpha()
                    # Scale to initial size
                    self.bg_image = pygame.transform.scale(img, (self.current_width, self.current_width))
                    self.bg_image.set_alpha(0)  # Start hidden
                    print(f"Background image loaded: {bg_image}")
                else:
                    print(f"Background image not found: {bg_image}")
                    
            elif isinstance(bg_image, pygame.Surface):
                # Already a PyGame surface
                self.bg_image = pygame.transform.scale(bg_image, (self.current_width, self.current_width))
                self.bg_image.set_alpha(0)  # Start hidden
                #print("Background image (surface) loaded")
            else:
                print(f"Unsupported background image type: {type(bg_image)}")
        except Exception as e:
            self.bg_image = None # Failed to load

    def _setup_ui_buttons(self):
        """Initialize UI buttons (Save/Load)"""
        win_width, win_height = self.win.get_size()
        available_width = win_width - self.tools_panel_width
        grid_size = min(available_width, win_height)
        if grid_size < 400:
            grid_size = 400
        
        grid_x = (available_width - grid_size) // 2
        grid_y = (win_height - grid_size) // 2
        
        # Position buttons at bottom of grid area (centered horizontally)
        button_y = grid_y + grid_size - 40  # Bottom of the grid area
        button_width = 80
        button_height = 30
        button_gap = 10
        
        # Calculate X positions relative to grid area
        load_button_x = grid_x + grid_size - (2 * button_width) - (2 * button_gap)
        save_button_x = grid_x + grid_size - button_width - button_gap
        
        self.save_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((save_button_x, button_y), (button_width, button_height)),
            text="Save",
            manager=self.manager
        )
        
        self.load_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((load_button_x, button_y), (button_width, button_height)),
            text="Load",
            manager=self.manager
        )

    def resize_window(self, new_width, new_height):
        """Resize the window and adjust UI elements"""
        # Keep grid as square, use the smaller dimension to maintain square grid
        grid_size = min(new_width - self.tools_panel_width, new_height)
        
        if grid_size < 400:  # Minimum grid size
            grid_size = 400
        
        # Update current width to reflect new grid size
        self.current_width = grid_size

        # Calculate centered position for tools panel
        available_width = new_width - self.tools_panel_width
        grid_x = (available_width - grid_size) // 2
        grid_y = (new_height - grid_size) // 2

        # Update window size first so _setup_ui_buttons can get correct size
        self.win = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        
        # Resize background image if it exists
        if self.bg_image:
            # Store original alpha value before scaling
            current_alpha = self.bg_image.get_alpha() if hasattr(self.bg_image, 'get_alpha') else 255
            self.bg_image = pygame.transform.scale(self.bg_image, (grid_size, grid_size))
            # Restore alpha state
            if self.bg_image_loaded:
                self.bg_image.set_alpha(150)
            else:
                self.bg_image.set_alpha(0)

        self.tools_panel = ToolsPanel(new_width - self.tools_panel_width, grid_y, self.tools_panel_width, grid_size)
        
        self.save_button.kill() # Remove old buttons
        self.load_button.kill()

        # Recreate buttons at new positions (bottom right of grid)
        # Now self.win.get_size() will return the correct new dimensions
        self._setup_ui_buttons()

        self.manager.set_window_resolution((new_width, new_height))

        self.window_resized = True
    
    def _load_initial_layout(self):
        """Load initial layout if file exists"""
        try:
            start, exits = load_layout(self.grid_obj.grid, self.filename)
            if start:
                self.grid_obj.start = start
            if bool(exits):
                self.grid_obj.exits = exits
        except FileNotFoundError:
            pass  # Start with empty grid
    
    def _handle_ui_events(self, event):
        """Handle UI button events"""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.save_button:
                self._save_layout_dialog()
            elif event.ui_element == self.load_button:
                self._load_layout_dialog()
    
    def _handle_tools_panel_events(self, event):
        """Handle tools panel selection events"""
        win_width, win_height = self.win.get_size()
        available_width = win_width - self.tools_panel_width
        grid_size = min(available_width, win_height)
        if grid_size < 400:
            grid_size = 400
        
        grid_x = (available_width - grid_size) // 2
        grid_y = (win_height - grid_size) // 2
        
        tools_panel_x = win_width - self.tools_panel_width
        
        # Check if click is in tools panel area at the right edge of the grid area
        if event.pos[0] >= tools_panel_x and event.pos[1] >= grid_y and event.pos[1] < grid_y + grid_size:
            tool_type, selected_material = self.tools_panel.handle_event(event)
            if tool_type is not None:
                self._process_tool_selection(tool_type, selected_material)
    
    def _process_tool_selection(self, tool_type, selected_material):
        """Process tool selection from tools panel"""
        if tool_type == ToolType.MATERIAL:
            self.current_tool = "MATERIAL"
            self.tools_panel.current_material = selected_material
        elif tool_type == ToolType.START:
            self.current_tool = "START"
            print("Start position mode - click on grid to place start")
        elif tool_type == ToolType.END:
            self.current_tool = "END"
            print("End position mode - click on grid to place end")
    
    def _handle_grid_click(self, event):
        """Handle mouse clicks in the grid area"""
        # Calculate grid position and size
        win_width, win_height = self.win.get_size()
        available_width = win_width - self.tools_panel_width
        grid_size = min(available_width, win_height)
        if grid_size < 400:
            grid_size = 400
        
        grid_x = (available_width - grid_size) // 2
        grid_y = (win_height - grid_size) // 2
        
        gap = grid_size // self.rows
        x, y = event.pos
        
        # Check if click is within centered grid area
        if grid_x <= x < grid_x + grid_size and grid_y <= y < grid_y + grid_size:
            # Adjust coordinates relative to grid top-left
            rel_x = x - grid_x
            rel_y = y - grid_y
            row = rel_y // gap
            col = rel_x // gap
            
            if row is not None and col is not None and self.grid_obj.in_bounds(row, col):
                spot = self.grid_obj.get_spot(row, col)
                
                if event.button == 1:  # Left click - place
                    self.mouse_dragging = True
                    self.drag_action = 'place'
                    self._place_on_grid(row, col, spot)
                    self.last_cell = (row, col)
                
                elif event.button == 3:  # Right click - erase
                    self.mouse_dragging = True
                    self.drag_action = 'erase'
                    self._erase_from_grid(spot)
                    self.last_cell = (row, col)
    
    def _place_on_grid(self, row, col, spot):
        """Place items on the grid based on current tool"""
        if self.current_tool == "START":
            if self.grid_obj.start:
                self.grid_obj.start.reset()
                print("Previous start position removed")
            self.grid_obj.start = spot
            spot.make_start()
        
        elif self.current_tool == "END":
            self.grid_obj.add_exit(spot)
            spot.make_end()
        
        elif self.current_tool == "MATERIAL":
            material_id = self.tools_panel.get_current_material()
            self.grid_obj.set_material(row, col, material_id)
            color = MATERIALS[material_id]["color"]
            self.grid_obj.grid[row][col].color = color
    
    def _erase_from_grid(self, spot):
        """Erase items from the grid"""
        spot.reset()
        if spot == self.grid_obj.start:
            self.grid_obj.start = None
        if self.grid_obj.is_exit(spot):
            self.grid_obj.remove_exit(spot)
    
    def _handle_mouse_drag(self, event):
        """Handle mouse dragging for continuous drawing/erasing"""
        # Calculate grid position and size
        win_width, win_height = self.win.get_size()
        available_width = win_width - self.tools_panel_width
        grid_size = min(available_width, win_height)
        if grid_size < 400:
            grid_size = 400
        
        grid_x = (available_width - grid_size) // 2
        grid_y = (win_height - grid_size) // 2
        
        x, y = event.pos
        
        # Check if drag is within centered grid area
        if grid_x <= x < grid_x + grid_size and grid_y <= y < grid_y + grid_size:
            gap = grid_size // self.rows
            rel_x = x - grid_x
            rel_y = y - grid_y
            row = rel_y // gap
            col = rel_x // gap
            
            if row is not None and col is not None and self.grid_obj.in_bounds(row, col):
                if self.last_cell != (row, col):
                    spot = self.grid_obj.get_spot(row, col)
                    
                    if self.drag_action == 'place':
                        if self.current_tool == "MATERIAL":
                            material_id = self.tools_panel.get_current_material()
                            self.grid_obj.set_material(row, col, material_id)
                            color = MATERIALS[material_id]["color"]
                            self.grid_obj.grid[row][col].color = color
                    
                    elif self.drag_action == 'erase':
                        spot.reset()
                        if spot == self.grid_obj.start:
                            self.grid_obj.start = None
                        if spot in self.grid_obj.exits:
                            self.grid_obj.exits.remove(spot)
                    
                    self.last_cell = (row, col)
    
    def _handle_keyboard_events(self, event):
        """Handle keyboard shortcuts"""
        if event.key == pygame.K_i:  # Toggle background image
            self._toggle_background_image()
        
        elif event.key == pygame.K_m:  # Back to material mode
            self.current_tool = "MATERIAL"
            print("Material mode")
        
        elif event.key == pygame.K_s:  # Save layout
            save_layout(self.grid_obj.grid, self.current_filename)
            print("Layout saved")
        
        elif event.key == pygame.K_l:  # Load layout
            self._load_from_file(self.filename)
        
        elif event.key == pygame.K_SPACE and self.grid_obj.start and bool(self.grid_obj.exits):
            print("Starting simulation...")
            return True  # Signal to exit editor
        
        elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
            pygame.quit()
            sys.exit()
        
        return False
    
    def _toggle_background_image(self):
        """Toggle background image visibility - loads on first press if not loaded"""
        # load image if not already loaded
        if self.bg_image is None and self.bg_image_path is not None:
            self._load_background_image(self.bg_image_path)
        
        if self.bg_image is None:
            print("No background image available to toggle")
            return
        
        self.bg_image_loaded = not self.bg_image_loaded
        
        if self.bg_image_loaded:
            self.bg_image.set_alpha(150)
            print("Background image shown (150 alpha)")
        else:
            self.bg_image.set_alpha(0)
            print("Background image hidden")
    
    def _save_layout_dialog(self):
        """Open save dialog and save layout"""
        save_filename = pick_save_csv_file()
        if save_filename:
            save_layout(self.grid_obj.grid, filename=save_filename)
            self.current_filename = save_filename
    
    def _load_layout_dialog(self):
        """Open load dialog and load layout"""
        load_filename = pick_csv_file()
        if load_filename:
            self._load_from_file(load_filename)
            self.current_filename = load_filename
    
    def _load_from_file(self, filename):
        """Load layout from a specific file"""
        # Clear old state
        self.grid_obj.start = None
        self.grid_obj.exits.clear()
        
        # Reset all spots
        for r in range(self.rows):
            for c in range(self.current_width // self.rows):
                self.grid_obj.grid[r][c].reset()
        
        # Load from file
        start, exits = load_layout(self.grid_obj.grid, filename)
        
        if start:
            self.grid_obj.start = start
        if exits:
            self.grid_obj.exits = exits
        
        # Hide background image during load
        self.bg_image_loaded = False
        if self.bg_image:
            self.bg_image.set_alpha(0)
        
        print(f"Layout loaded from {filename}")
    
    def _import_layout(self):
        """Import layout from CSV file"""
        csv_filename = pick_csv_file()
        if csv_filename:
            self._load_from_file(csv_filename)
            print("Layout imported")
    
    def _export_layout(self):
        """Export layout to CSV file"""
        save_filename = pick_save_csv_file()
        if save_filename:
            save_layout(self.grid_obj.grid, save_filename)
            print("Layout exported")
    
    def draw(self): # draw for dynamic resizing
        """Draw the entire editor interface with dynamic sizing"""
        # Clear the window
        self.win.fill(Color.WHITE.value)
        
        win_width, win_height = self.win.get_size() #centered location of grid
        available_width = win_width - self.tools_panel_width # available width for grid area

        grid_size = min(available_width, win_height) # Keep grid square based on available space
        
        if grid_size < 400:# Ensure minimum size
            grid_size = 400
        
        
        if self.current_width != grid_size: # Update current width if it changed
            self.current_width = grid_size
        
        # centering offsets
        grid_x = (available_width - grid_size) // 2  # Center horizontally in left area
        grid_y = (win_height - grid_size) // 2       # Center vertically
        
        grid_rect = pygame.Rect(grid_x, grid_y, grid_size, grid_size)# draw grid at centered position
        pygame.draw.rect(self.win, Color.WHITE.value, grid_rect)
        
        if self.bg_image and self.bg_image_loaded:# draw background image
            # scale background image to current grid size when resized
            scaled_bg = pygame.transform.scale(self.bg_image, (grid_size, grid_size))
            self.win.blit(scaled_bg, (grid_x, grid_y))
        
        gap = grid_size // self.rows # Draw grid cells with dynamic sizing
        for r in range(self.rows):
            for c in range(self.rows):
                spot = self.grid_obj.grid[r][c]
                # cell position with centering offset
                x = grid_x + c * gap
                y = grid_y + r * gap
                
                pygame.draw.rect(self.win, spot.color, (x, y, gap, gap)) # Draw cell with dynamic size
        
                pygame.draw.rect(self.win, Color.GREY.value, (x, y, gap, gap), 1) # Cell border
        
        tools_panel_x = win_width - self.tools_panel_width  # Always at right edge of window
        self.tools_panel.x = tools_panel_x  
        self.tools_panel.y = grid_y
        self.tools_panel.height = grid_size
        self.tools_panel.draw(self.win)
        
        for i in range(self.rows + 1): # Draw grid lines with dynamic spacing
            pygame.draw.line(self.win, Color.GREY.value, # Horizontal lines
                           (grid_x, grid_y + i * gap), 
                           (grid_x + grid_size, grid_y + i * gap))
            
            pygame.draw.line(self.win, Color.GREY.value, # Vertical lines
                           (grid_x + i * gap, grid_y), 
                           (grid_x + i * gap, grid_y + grid_size))

    def run(self):
        """Main editor loop"""
        clock = pygame.time.Clock()
        
        while True:
            time_delta = clock.tick(60) / 1000.0

            # Check for window resize events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                
                elif event.type == pygame.VIDEORESIZE:
                    # Resize the PyGame window
                    self.win = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE) #w, h = An integer for the new width and height of the window
                    # Handle the resize in our editor
                    self.resize_window(event.w, event.h)

                elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                    self._handle_ui_events(event)  

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.pos[0] >= self.current_width: # event.pos[0] is x coordinate of click
                        self._handle_tools_panel_events(event)
                    else:
                        self._handle_grid_click(event)
                elif event.type == pygame.MOUSEMOTION and self.mouse_dragging:
                    self._handle_mouse_drag(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.mouse_dragging = False
                    self.drag_action = None
                    self.last_cell = None
                elif event.type == pygame.KEYDOWN:
                    if self._handle_keyboard_events(event):
                        return self.grid_obj
                self.manager.process_events(event)
            
            self.draw() #use of dynamic draw method
            self.manager.update(time_delta) #update ui
            self.manager.draw_ui(self.win)

            pygame.display.update()
        
        return self.grid_obj

# ------------------ CONVERSION FUNCTION ------------------
def floor_image_to_csv(image_path, csv_path, rows=60, cols=60, wall_color=(0, 0, 0), end_color=(255, 0, 0)):
    """
    Converts a floor layout image into a 60x60 CSV grid.
    """
    img = Image.open(image_path).convert("RGB")
    img = img.resize((cols, rows), Image.NEAREST)
    pixels = img.load()
    
    grid = []
    
    for r in range(rows):
        row = []
        for c in range(cols):
            color = pixels[c, r]
            
            if color == wall_color:
                row.append(1)
            elif color == end_color:
                row.append(3)
            else:
                row.append(0)
        
        grid.append(row)
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(grid)

# ------------------ LEGACY FUNCTION (for compatibility) ------------------
def run_editor(win, rows, width, bg_image=None, filename="layout_csv\\layout_1.csv"):
    """Legacy function - creates an Editor instance and runs it"""
    editor = Editor(win, rows, width, bg_image, filename)
    return editor.run()