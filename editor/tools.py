from typing import Optional, Tuple

import pygame

from environment.materials import MATERIALS
from utils.utilities import Color, ToolType, material_id as MaterialID

GREEN = Color.GREEN.value
FIRE_COLOR = Color.FIRE_COLOR.value
RED = Color.RED.value

class ToolButton:
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        material_id,
        name: str,
        color: Tuple[int, int, int],
        tool_type: ToolType,
    ) -> None:
        self.rect = pygame.Rect(x, y, width, height)
        self.tool_type = tool_type
        self.material_id = material_id
        self.name = name
        self.color = color
        self.selected = False
        self.font = pygame.font.SysFont(None, 18)
    
    def draw(self, surface: pygame.Surface) -> None:
        # Draw button background
        bg_color = (100, 100, 100) if self.selected else (70, 70, 70)
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, (120, 120, 120) if self.selected else (90, 90, 90), 
                        self.rect, width=2, border_radius=8)
        
        # Draw material color preview
        preview_rect = pygame.Rect(
            self.rect.x + 10,
            self.rect.y + 10,
            self.rect.width - 20,
            self.rect.height - 40
        )
        pygame.draw.rect(surface, self.color, preview_rect, border_radius=4)
        pygame.draw.rect(surface, (200, 200, 200), preview_rect, width=1, border_radius=4)
        
        # Draw material name
        text_surface = self.font.render(self.name, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(self.rect.centerx, self.rect.bottom - 15))
        surface.blit(text_surface, text_rect)
    
    def is_clicked(self, pos: Tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

class ToolsPanel:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.rect = pygame.Rect(x, y, width, height)
        self.buttons = []
        self.current_material = MaterialID.AIR
        self.font_large = pygame.font.SysFont(None, 24)
        self.font_small = pygame.font.SysFont(None, 18)
        self._init_buttons()
    
    def _init_buttons(self) -> None:
        button_width = 80
        button_height = 80
        padding = 10
        
        tools = []
        for value in MaterialID:
            if value == MaterialID.FIRE or value == MaterialID.AIR:
                continue # Skip FIRE and AIR as material tools
            tools.append((ToolType.MATERIAL, value, MATERIALS[value]["name"], MATERIALS[value]["color"]))

        # Special tools
        tools.append((ToolType.FIRE_SOURCE, None, "Fire", FIRE_COLOR))
        tools.append((ToolType.START, None, "Start", GREEN))
        tools.append((ToolType.END, None, "End", RED))
        
        self.buttons.clear()
        for i, (tool_type, material_id, name, color) in enumerate(tools):
            col = i % 2
            row = i // 2

            x = self.rect.x + padding + col * (button_width + padding)
            y = self.rect.y + 50 + row * (button_height + padding)

            button = ToolButton(x, y, button_width, button_height, material_id, name, color, tool_type)

            if tool_type == ToolType.MATERIAL and material_id == self.current_material:
                button.selected = True

            self.buttons.append(button)
    
    def handle_event(self, event: pygame.event.Event) -> Tuple[Optional[ToolType], Optional[MaterialID]]:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button.is_clicked(event.pos):
                    # Deselect all buttons
                    for btn in self.buttons:
                        btn.selected = False
                    # Select clicked button
                    button.selected = True
                    # Return both tool type and material id
                    return button.tool_type, button.material_id
        return None, None
    
    def draw(self, surface: pygame.Surface) -> None:
        # Draw panel background
        pygame.draw.rect(surface, (50, 50, 60), self.rect)
        pygame.draw.rect(surface, (80, 80, 90), self.rect, width=2)
        
        # Draw title
        title_surface = self.font_large.render("MATERIALS", True, (255, 255, 255))
        surface.blit(title_surface, (self.rect.centerx - title_surface.get_width() // 2, self.rect.y + 15))
        
        # Draw instructions
        instructions = [
            "Click material to select",
            "Hold Left-click to place",
            "Hold Right-click to erase"
        ]
        
        for i, instruction in enumerate(instructions):
            text_surface = self.font_small.render(instruction, True, (200, 200, 200))
            surface.blit(text_surface, (self.rect.x + 10, self.rect.bottom - 130 + i * 20))
        
        # Draw selected material info
        # selected_mat = MATERIALS[self.current_material]
        # info_text = f"Selected: {selected_mat['name']}"
        # info_surface = self.font_small.render(info_text, True, (255, 255, 200))
        # surface.blit(info_surface, (self.rect.x + 10, self.rect.bottom - 30))
        
        # Draw all buttons
        for button in self.buttons:
            button.draw(surface)
    
    def get_current_material(self) -> MaterialID:
        return self.current_material