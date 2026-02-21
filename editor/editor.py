import csv
import logging
from typing import Optional, Tuple, TYPE_CHECKING

import pygame
import pygame_gui
from PIL import Image

from editor.tools import ToolsPanel
from utils.utilities import Color, ToolType, load_layout, pick_csv_file, pick_save_csv_file, save_layout, get_dpi_scale

if TYPE_CHECKING:
    from core.grid import Grid
    from core.spot import Spot

logger = logging.getLogger(__name__)

# Global constant for white color - accessed once at import time
WHITE = Color.WHITE.value

# ------------------ EDITOR CLASS ------------------
class Editor:
    def __init__(
        self,
        win: pygame.Surface,
        rows: int,
        bg_image: Optional[pygame.Surface] = None,
        filename: str = "layout_csv\\layout_1.csv",
    ) -> None:
        from core.grid import Grid
        
        self.win = win
        self.rows = rows
        self.bg_image = bg_image
        self.filename = filename
        
        # compute DPI scaling factor to size UI elements
        self.scale = get_dpi_scale(pygame.display.get_wm_info()['window'])

        # Calculate width based on current window size
        win_width, win_height = win.get_size()
        tools_width = int(200 * self.scale)
        self.width = min(win_width - tools_width, win_height)
        self.width = max(self.width, int(200 * self.scale))  # minimum
        self.panel_x = win_width - tools_width
        
        # Grid and state
        self.grid_obj = Grid(rows, self.width)
        self.tools_panel = ToolsPanel(self.panel_x, 0, tools_width, win_height, scale=self.scale)
        self.current_tool = "MATERIAL"
        self.current_filename = filename
        self.bg_image_loaded = False
        
        # Mouse dragging state
        self.mouse_dragging = False
        self.drag_action = None  # 'place' or 'erase'
        self.last_cell = None
        
        # Initialize GUI
        self.manager = pygame_gui.UIManager((win_width, win_height))
        self._setup_ui_buttons()
    
    def _setup_ui_buttons(self) -> None:
        """Initialize UI buttons (Save/Load)"""
        # scale button dimensions as well
        button_y = self.win.get_size()[1] - int(40 * self.scale)  # Bottom of the window
        button_width = int(80 * self.scale)
        button_height = int(30 * self.scale)
        button_gap = int(16 * self.scale)
        offset = int(200 * self.scale)

        # Calculate X positions
        load_button_x = self.win.get_size()[0] - int(200 * self.scale) - (2 * button_width) - (2 * button_gap) + offset
        save_button_x = self.win.get_size()[0] - int(200 * self.scale) - button_width - button_gap + offset
        
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
    
    def _handle_window_resize(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.VIDEORESIZE:
            return False

        # Resize window
        self.win = pygame.display.set_mode(event.size, pygame.RESIZABLE)

        # DPI may have changed during the resize/move
        from utils.utilities import get_dpi_scale
        self.scale = get_dpi_scale(pygame.display.get_wm_info()['window'])

        win_width, win_height = event.size
        tools_width = int(200 * self.scale)

        # Grid takes remaining width, square aspect
        grid_pixel_width = min(win_width - tools_width, win_height)
        grid_pixel_width = max(grid_pixel_width, int(200 * self.scale))
        #grid_pixel_width = win_width - tools_width

        self.width = grid_pixel_width
        self.panel_x = win_width - tools_width

        # Resize grid geometry
        self.grid_obj.cell_size = self.width // self.rows
        self.grid_obj.update_geometry(self.grid_obj.cell_size)
        self.grid_obj.width = self.width

        # Move tools panel and update its scale in case DPI changed
        self.tools_panel.scale = self.scale
        self.tools_panel.rect.x = win_width - tools_width
        self.tools_panel.rect.height = win_height
        self.tools_panel._init_buttons()

        # Recreate UI manager for new size
        self.manager = pygame_gui.UIManager((win_width, win_height))
        self._setup_ui_buttons()
        return True

    def _load_initial_layout(self) -> None:
        """Load initial layout if file exists"""
        try:
            start, exits = load_layout(self.grid_obj.grid, self.filename)
            if start:
                self.grid_obj.start = start
            if bool(exits):
                self.grid_obj.exits = exits
            # remember the file so simulations can reload it on reset
            self.grid_obj.layout_filename = self.filename
            self.grid_obj.mark_material_cache_dirty()
        except FileNotFoundError:
            pass  # Start with empty grid
    
    def _handle_ui_events(self, event: pygame.event.Event) -> None:
        """Handle UI button events"""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.save_button:
                self._save_layout_dialog()
            elif event.ui_element == self.load_button:
                self._load_layout_dialog()
    
    def _handle_tools_panel_events(self, event: pygame.event.Event) -> None:
        """Handle tools panel selection events"""
        if event.pos[0] >= self.panel_x:  # Click in tools panel
            tool_type, selected_material = self.tools_panel.handle_event(event)
            if tool_type is not None:
                self._process_tool_selection(tool_type, selected_material)
    
    def _process_tool_selection(self, tool_type: ToolType, selected_material) -> None:
        """Process tool selection from tools panel"""
        
        if tool_type == ToolType.MATERIAL:
            self.current_tool = "MATERIAL"
            self.tools_panel.current_material = selected_material
        elif tool_type == ToolType.START:
            self.current_tool = "START"
            logger.info("Start position mode - click on grid to place start")
        elif tool_type == ToolType.END:
            self.current_tool = "END"
            logger.info("End position mode - click on grid to place end")
        elif tool_type == ToolType.FIRE_SOURCE:
            self.current_tool = "FIRE_SOURCE"
            logger.info("Fire source mode - click on grid to place fire source")

    def _handle_grid_click(self, event: pygame.event.Event) -> None:
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
    
    def _place_on_grid(self, row: int, col: int, spot: "Spot") -> None:
        """Place items on the grid based on current tool"""
        if self.current_tool == "START":
            if self.grid_obj.start:
                self.grid_obj.start.reset()
                logger.info("Previous start position removed")
            self.grid_obj.start = spot
            spot.make_start()
            self.grid_obj.mark_material_cache_dirty()
        
        elif self.current_tool == "END":
            self.grid_obj.add_exit(spot)
            spot.make_end()
            self.grid_obj.mark_material_cache_dirty()
        
        elif self.current_tool == "MATERIAL":
            material_id = self.tools_panel.get_current_material()
            self.grid_obj.set_material(row, col, material_id)

        elif self.current_tool == "FIRE_SOURCE":
            self.grid_obj.fire_sources.add((row, col))
            spot.set_as_fire_source()
            logger.info("Fire source placed")

    def _erase_from_grid(self, spot: "Spot") -> None:
        """Erase items from the grid"""
        spot.reset()
        if spot == self.grid_obj.start:
            self.grid_obj.start = None
        if self.grid_obj.is_exit(spot):
            self.grid_obj.remove_exit(spot)
        self.grid_obj.mark_material_cache_dirty()
    
    def _handle_mouse_drag(self, event: pygame.event.Event) -> None:
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
                    
                    elif self.drag_action == 'erase':
                        spot.reset()
                        if spot == self.grid_obj.start:
                            self.grid_obj.start = None
                        if spot in self.grid_obj.exits:
                            self.grid_obj.exits.remove(spot)
                        self.grid_obj.mark_material_cache_dirty()
                    
                    self.last_cell = (row, col)
    
    def _handle_keyboard_events(self, event: pygame.event.Event) -> Optional[bool]:
        """Handle keyboard shortcuts"""
        if event.key == pygame.K_i:  # Toggle background image
            self._toggle_background_image()
        
        elif event.key == pygame.K_m:  # Back to material mode
            self.current_tool = "MATERIAL"
            logger.info("Material mode")
        
        elif event.key == pygame.K_s:  # Save layout
            save_layout(self.grid_obj.grid, self.current_filename)
            logger.info("Layout saved")
        
        elif event.key == pygame.K_l:  # Load layout
            logger.info("Loading layout... %s", self.filename)
            self._load_from_file(self.filename)
        
        elif event.key == pygame.K_SPACE and self.grid_obj.start and bool(self.grid_obj.exits):
            logger.info("Starting simulation...")
            return True  # Signal to exit editor
        
        elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
            return False  # Signal to quit program
        
        return None
    
    def _toggle_background_image(self) -> None:
        """Toggle background image visibility"""
        if not self.bg_image_loaded:
            self.bg_image_loaded = True
            if self.bg_image:
                self.bg_image.set_alpha(150)
        else:
            self.bg_image_loaded = False
            if self.bg_image:
                self.bg_image.set_alpha(0)
    
    def _save_layout_dialog(self) -> None:
        """Open save dialog and save layout"""
        save_filename = pick_save_csv_file()
        if save_filename:
            save_layout(self.grid_obj.grid, filename=save_filename)
            self.current_filename = save_filename
            # if the user explicitly saved the layout, update the grid's
            # remembered filename so resets will use the new file
            self.grid_obj.layout_filename = save_filename
    
    def _load_layout_dialog(self) -> None:
        """Open load dialog and load layout"""
        load_filename = pick_csv_file()
        if load_filename:
            self._load_from_file(load_filename)
            self.current_filename = load_filename
    
    def _load_from_file(self, filename: str) -> None:
        """Load layout from a specific file"""
        # remember the source so resets can go back to it
        self.grid_obj.layout_filename = filename

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
        if exits and bool(exits):
            self.grid_obj.exits = exits

        self.grid_obj.mark_material_cache_dirty()
        
        # Hide background image during load
        self.bg_image_loaded = False
        if self.bg_image:
            self.bg_image.set_alpha(0)
        
        logger.info("Layout loaded from %s", filename)
    
    def _import_layout(self) -> None:
        """Import layout from CSV file"""
        csv_filename = pick_csv_file()
        if csv_filename:
            self._load_from_file(csv_filename)
            logger.info("Layout imported")
    
    def _export_layout(self) -> None:
        """Export layout to CSV file"""
        save_filename = pick_save_csv_file()
        if save_filename:
            save_layout(self.grid_obj.grid, save_filename)
            logger.info("Layout exported")
    
    def run(self) -> Optional["Grid"]:
        """Main editor loop"""
        clock = pygame.time.Clock()
        while True:
            time_delta = clock.tick(60) / 1000.0
            self.win.fill(WHITE)
            
            # Draw everything
            self.grid_obj.draw(self.win, self.tools_panel, self.bg_image)
            
            # Draw white separator bar between grid and tools
            win_width, win_height = self.win.get_size() #pygame method to get current window size
            separator_x = self.panel_x #use current window width
            
            pygame.draw.rect(
                self.win, 
                WHITE, 
                (separator_x, 0, 2, win_height)
            )# Draw white separator

            for event in pygame.event.get():
                if self._handle_window_resize(event):
                    continue  # Skip further processing if resized

                if event.type == pygame.QUIT:
                    return None
                
                # Handle different event types
                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    self._handle_ui_events(event)
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
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
                    result = self._handle_keyboard_events(event)
                    if result is True:
                        return self.grid_obj
                    elif result is False:
                        return None
                
                self.manager.process_events(event)
            
            # Update UI
            self.manager.update(time_delta)
            self.manager.draw_ui(self.win)
            pygame.display.update()

# CONVERSION FUNCTION
def floor_image_to_csv(
    image_path: str,
    csv_path: str,
    rows: int = 60,
    cols: int = 60,
    wall_color: Tuple[int, int, int] = (0, 0, 0),
    end_color: Tuple[int, int, int] = (255, 0, 0),
) -> None:
    """
    Converts a floor layout image into a 60x60 CSV grid.
    """
    grid = []
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img = img.resize((cols, rows), Image.NEAREST)
        pixels = img.load()

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

# LEGACY FUNCTION (for compatibility)
def run_editor(win, rows, bg_image=None, filename="layout_csv\\layout_2.csv"):
    """Legacy function - creates an Editor instance and runs it"""
    editor = Editor(win, rows, bg_image, filename)
    result = editor.run()
    return result