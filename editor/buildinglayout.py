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
        self.width = width
        self.bg_image = bg_image
        self.filename = filename
        
        # Grid and state
        self.grid_obj = Grid(rows, width)
        # Get current window size
        win_width, win_height = self.win.get_size()
        tools_panel_width = 200

        self.tools_panel = ToolsPanel(win_width - tools_panel_width, 0, 
                                      tools_panel_width, win_height) #with dynamic dimensions
        self.current_tool = "MATERIAL"
        self.current_filename = filename
        self.bg_image_loaded = False
        
        # Mouse dragging state
        self.mouse_dragging = False
        self.drag_action = None  # 'place' or 'erase'
        self.last_cell = None
        
        # Window resizing state
        self.window_size = (width + 200, width)
        self.original_width = width

        # Initialize GUI
        self.manager = pygame_gui.UIManager((win_width, win_height))
        self._setup_ui_buttons()
        
        # Try to load existing layout
        # self._load_initial_layout()
    
    def _setup_ui_buttons(self):
        """Initialize UI buttons (Save/Load)"""
        # Get current window size
        win_width, win_height = self.win.get_size()
        
        button_y = win_height - 40  # Bottom of the window
        button_width = 80
        button_height = 30
        button_gap = 16
        
        # Calculate X positions relative to tools panel
        load_button_x = win_width - (2 * button_width) - (2 * button_gap)
        save_button_x = win_width - button_width - button_gap
        
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

    def _handle_window_resize(self, event):
        """Handle window resize events"""
        if event.type == pygame.VIDEORESIZE:
            # Update window size
            self.window_size = event.size
            
            # Recreate UI manager with new size
            self.manager = pygame_gui.UIManager(event.size)
            
            # Recreate UI buttons at new positions
            self._setup_ui_buttons()
            
            # Update tools panel size
            win_width, win_height = event.size
            tools_panel_width = 200  # Fixed tools panel width
            

            self.tools_panel.rect.x = win_width - tools_panel_width
            self.tools_panel.rect.y = 0
            self.tools_panel.rect.width = tools_panel_width
            self.tools_panel.rect.height = win_height
            
            # Update grid width (main area is everything except tools panel)
            self.width = win_width - tools_panel_width
            
            self.tools_panel._init_buttons() # Reinitialization of tools panel buttons with new position

            self.grid_obj.cell_size = self.width // self.rows # Update grid's cell size based on new width

            return True
        return False
    
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
        if event.pos[0] >= self.width:  # Click in tools panel
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
        elif tool_type == ToolType.FIRE_SOURCE:
            self.current_tool = "FIRE_SOURCE"
            print("Fire source mode - click on grid to place fire source")
    def _handle_grid_click(self, event):
        """Handle mouse clicks in the grid area"""
        row, col = self.grid_obj.get_clicked_pos(event.pos)
        
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

        elif self.current_tool == "FIRE_SOURCE":
            self.grid_obj.fire_sources.add((row, col))
            self.grid_obj.grid[row][col].color = Color.FIRE_COLOR.value
            print("Fire source placed")

    def _erase_from_grid(self, spot):
        """Erase items from the grid"""
        spot.reset()
        if spot == self.grid_obj.start:
            self.grid_obj.start = None
        if self.grid_obj.is_exit(spot):
            self.grid_obj.remove_exit(spot)
    
    def _handle_mouse_drag(self, event):
        """Handle mouse dragging for continuous drawing/erasing"""
        if event.pos[0] < self.width:  # Only process if in grid area
            row, col = self.grid_obj.get_clicked_pos(event.pos)
            
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
        """Toggle background image visibility"""
        if not self.bg_image_loaded:
            self.bg_image_loaded = True
            if self.bg_image:
                self.bg_image.set_alpha(150)
        else:
            self.bg_image_loaded = False
            if self.bg_image:
                self.bg_image.set_alpha(0)
    
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
            for c in range(self.width // self.rows):
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
    
    def run(self):
        """Main editor loop"""
        clock = pygame.time.Clock()
        
        while True:
            time_delta = clock.tick(60) / 1000.0

            # Clear the entire window
            self.win.fill(Color.WHITE.value)

            # Draw everything (grid and tools panel)
            self.grid_obj.draw(self.win, self.tools_panel, self.bg_image)

            # Draw white separator bar between grid and tools
            win_width, win_height = self.win.get_size() #pygame method to get current window size
            separator_x = self.width #use current window width
            
            pygame.draw.rect(
                self.win, 
                Color.WHITE.value, 
                (separator_x, 0, 2, win_height)
            )# Draw white separator
            
            for event in pygame.event.get():
                if self._handle_window_resize(event):
                    continue
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                
                # Handle different event types
                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    self._handle_ui_events(event)
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    win_width, _ = self.win.get_size()
                    if event.pos[0] >= self.width:
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
            
            # Update UI
            self.manager.update(time_delta)
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