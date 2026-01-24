import pygame
import pygame_gui
import csv
import sys
from utilities import ToolType, state_value, Color, material_id
from materials import MATERIALS
from PIL import Image
from tools import ToolsPanel
import tkinter as tk
from tkinter import filedialog

# ------------------ GRID UTILS ------------------
def draw_grid(win, rows, width):
    gap = width // rows
    for i in range(rows):
        pygame.draw.line(win, Color.GREY.value, (0, i * gap), (width, i * gap))
        pygame.draw.line(win, Color.GREY.value, (i * gap, 0), (i * gap, width))

def draw(win, grid, rows, width, tools_panel=None, bg_image=None):
    if bg_image:
        win.blit(bg_image, (0, 0))
    for row in grid:
        for spot in row:
            spot.draw(win)
    draw_grid(win, rows, width)
    
    if tools_panel:
        tools_panel.draw(win)
    
    #pygame.display.update()

def get_clicked_pos(pos, rows, width):
    gap = width // rows
    x, y = pos
    
    # Only process clicks within grid area
    if x < width:
        row = y // gap
        col = x // gap
        return row, col
    return None, None

# ------------------ SAVE / LOAD ------------------
def spot_to_value(spot):
    if spot.is_barrier(): return state_value.WALL.value
    if spot.is_start(): return state_value.START.value
    if spot.is_end(): return state_value.END.value
    return state_value.EMPTY.value

def save_layout(grid, filename="layout_csv\\layout_1.csv"):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        for row in grid:
            writer.writerow([spot_to_value(s) for s in row])

def load_layout(grid, filename="layout_csv\\layout_1.csv"):
    start = None
    end = set()
    try:
        with open(filename, "r") as f:
            reader = csv.reader(f)
            for r, row in enumerate(reader):
                for c, val in enumerate(row):
                    spot = grid[r][c]
                    spot.reset()
                    if int(val) == state_value.WALL.value:
                        spot.make_barrier()
                    elif int(val) == state_value.START.value:
                        spot.make_start()
                        start = spot
                    elif int(val) == state_value.END.value:
                        spot.make_end()
                        end.add(spot)
    except FileNotFoundError:
        print(f"Layout file {filename} not found. Starting with empty grid.")
    return start, end

def pick_csv_file():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(
        filetypes=[("CSV files", "*.csv")]
    )

def pick_save_csv_file(default_name="layout.csv"):
    root = tk.Tk()
    root.withdraw()  # hide tk window

    filename = filedialog.asksaveasfilename(
        title="Export layout as CSV",
        defaultextension=".csv",
        initialfile=default_name,
        filetypes=[("CSV Files", "*.csv")]
    )

    root.destroy()
    return filename

# ------------------ EDITOR LOOP ------------------
def run_editor(win, rows, width, bg_image=None, filename="layout_csv\\layout_1.csv"):
    """
    Layout editor window.
    - Draw walls, start, and end points
    - Save layout to CSV
    - Load layout from CSV
    - Finish editing and return grid, start, end
    """
    from grid import Grid

    grid_obj = Grid(rows, width)
    start = end = None
    clock = pygame.time.Clock()

    manager = pygame_gui.UIManager((width+200, width)) # Initialize GUI button manager including tools panel area
    # Position buttons to just left of the tools panel
    button_y = width - 40  # Bottom of the window
    button_width = 80
    button_height = 30
    button_gap = 10  # Gap between buttons
    
    # Calculate X positions: place buttons right before the tools panel starts
    # Tools panel starts at X = width, so we place buttons to the left of it
    load_button_x = width - (2 * button_width) - (2 * button_gap)
    save_button_x = width - button_width - button_gap

    save_button = pygame_gui.elements.UIButton( 
        relative_rect=pygame.Rect((save_button_x, button_y), (button_width, button_height)),
        text="Save",
        manager=manager
    )

    load_button = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((load_button_x, button_y), (button_width, button_height)),
        text="Load",
        manager=manager
    )


    # Create tools panel
    tools_panel = ToolsPanel(width, 0, 200, width)
    current_tool = "MATERIAL"  # Can be "MATERIAL", "START", "END", "WOOD", etc.

    # Variables for mouse dragging
    mouse_dragging = False
    drag_action = None  # 'place' or 'erase'
    last_cell = None  # Last cell we processed during drag
    
    current_filename = filename
    # Try to load existing layout
    bg_image_loaded = False
    run = True
    
    while run:
        time_delta = clock.tick(60) / 1000.0
        win.fill(Color.WHITE.value)
        
        # Draw everything
        draw(win, grid_obj.grid, rows, width, tools_panel, bg_image)

        for event in pygame.event.get():
            
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # Handle button clicks- UI button events
            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                if event.ui_element == save_button:
                    save_filename = pick_save_csv_file()
                    if save_filename:
                        save_layout(grid_obj.grid, filename=save_filename)
                        current_filename = save_filename  # Update current filename
                        #print(f"Layout saved to {save_filename}")
                    
                elif event.ui_element == load_button:
                    # Clear old start/exits before loading
                    load_filename = pick_csv_file()
                    if load_filename:
                        # Reset current layout before loading
                        grid_obj.start = None
                        grid_obj.exits.clear()
                        
                        # Reset all spots in grid
                        for r in range(rows):
                            for c in range(width // rows):
                                grid_obj.grid[r][c].reset()
                        
                        # Load from selected file
                        start, exits = load_layout(grid_obj.grid, load_filename)
                        
                        if start:
                            grid_obj.start = start
                            #print(f"Start position loaded at ({start.row}, {start.col})")
                        if exits:
                            grid_obj.exits = exits
                            #print(f"{len(exits)} exit(s) loaded")
                        
                        current_filename = load_filename  # Update current filename
                        #print(f"Layout loaded from {load_filename}")
            

            # Handle tools panel clicks
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.pos[0] >= width:  # Click in tools panel
                    tool_type, selected_material = tools_panel.handle_event(event)
                    if tool_type is not None:
                        if tool_type == ToolType.MATERIAL:
                            current_tool = "MATERIAL"
                            tools_panel.current_material = selected_material
                        elif tool_type == ToolType.START:
                            current_tool = "START"
                            print("Start position mode - click on grid to place start")
                        elif tool_type == ToolType.END:
                            current_tool = "END"
                            print("End position mode - click on grid to place end")
                        elif tool_type == ToolType.IMPORT:
                            csv_filename = pick_csv_file()
                            if csv_filename:
                                grid_obj.start = None
                                grid_obj.exits.clear()

                                start, exits = load_layout(grid_obj.grid, csv_filename)

                                if start:
                                    grid_obj.start = start
                                if exits:
                                    grid_obj.exits = exits
                                print("Layout loaded")
                        elif tool_type == ToolType.EXPORT:
                            save_filename = pick_save_csv_file()
                            if save_filename:
                                save_layout(grid_obj.grid, save_filename)
                                print("Layout saved")
                            
                else:  # Click in grid area
                    row, col = get_clicked_pos(event.pos, rows, width)
                    
                    if row is not None and col is not None and grid_obj.in_bounds(row, col):
                        spot = grid_obj.get_spot(row, col)
                        
                        if event.button == 1:  # Left click - place
                            mouse_dragging = True
                            drag_action = 'place'
                            
                            if current_tool == "START":
                                if grid_obj.start:
                                    grid_obj.start.reset()
                                grid_obj.start = spot
                                spot.make_start()
                            
                            elif current_tool == "END":
                                grid_obj.add_exit(spot)
                                # if grid_obj.end:
                                #     grid_obj.end.reset()
                                # grid_obj.end = spot
                                spot.make_end()
                            
                            elif current_tool == "MATERIAL":  # MATERIAL mode
                                material_id = tools_panel.get_current_material() #naming conflict doesnt matter here due to use of getter function
                                grid_obj.set_material(row, col, material_id)
                                color = MATERIALS[material_id]["color"]
                                grid_obj.grid[row][col].color = color
                            
                            last_cell = (row, col)
                        
                        elif event.button == 3:  # Right click - erase
                            mouse_dragging = True
                            drag_action = 'erase'
                            spot.reset()
                            if spot == grid_obj.start:
                                grid_obj.start = None
                            if grid_obj.is_exit(spot):
                                grid_obj.remove_exit(spot)
                            # if spot == grid_obj.end:
                            #     grid_obj.end = None
                            last_cell = (row, col)
                
            # Handle mouse motion for dragging
            elif event.type == pygame.MOUSEMOTION and mouse_dragging:
                if event.pos[0] < width:  # Only process if in grid area
                    row, col = get_clicked_pos(event.pos, rows, width)
                    
                    if row is not None and col is not None and grid_obj.in_bounds(row, col):
                        # Check if we're moving to a new cell (avoid duplicate processing)
                        if last_cell != (row, col):
                            spot = grid_obj.get_spot(row, col)
                            
                            if drag_action == 'place':
                                if current_tool == "MATERIAL":
                                    material_id = tools_panel.get_current_material()
                                    grid_obj.set_material(row, col, material_id)
                                    color = MATERIALS[material_id]["color"]
                                    grid_obj.grid[row][col].color = color
                            elif drag_action == 'erase':
                                spot.reset()
                                if spot == grid_obj.start:
                                    grid_obj.start = None
                                if spot == grid_obj.exits:
                                    grid_obj.exits = None
                            
                            last_cell = (row, col)
            
            # Handle mouse button release
            elif event.type == pygame.MOUSEBUTTONUP:
                mouse_dragging = False
                drag_action = None
                last_cell = None
            
            # Keyboard shortcuts
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_i:  # Toggle background image
                    if bg_image_loaded == False:
                        bg_image_loaded = True
                        if bg_image:
                            bg_image.set_alpha(150)
                    else:
                        bg_image_loaded = False
                        if bg_image:
                            bg_image.set_alpha(0)
                
                elif event.key == pygame.K_m:  # Back to material mode
                    current_tool = "MATERIAL"
                    print("Material mode")
                
                elif event.key == pygame.K_s:  # Save layout
                    save_layout(grid_obj.grid)
                    print("Layout saved")
                
                elif event.key == pygame.K_l:  # Load layout
                    bg_image_loaded = False
                    if bg_image:
                        bg_image.set_alpha(0)
                    grid_obj.start = None
                    grid_obj.exits.clear()
                    start, exits = load_layout(grid_obj.grid, filename)
                    if start:
                        grid_obj.start = start
                    if bool(exits):
                       grid_obj.exits = exits
                    print("Layout loaded")
                
                elif event.key == pygame.K_SPACE and grid_obj.start and bool(grid_obj.exits):
                    print("Starting simulation...")
                    return grid_obj
                
                elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()
        
        manager.process_events(event)
        manager.update(time_delta)
        manager.draw_ui(win)
        pygame.display.update()
    return grid_obj

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