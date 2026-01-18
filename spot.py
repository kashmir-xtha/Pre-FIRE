from utilities import Color
import pygame

class Spot:
    def __init__(self, row, col, width):
        self.row = row
        self.col = col
        self.x = col * width
        self.y = row * width
        self.color = Color.WHITE.value
        self.width = width
        
    def reset(self): self.color = Color.WHITE.value
    def make_barrier(self): self.color = Color.BLACK.value
    def make_start(self): self.color = Color.GREEN.value
    def make_end(self): self.color = Color.RED.value

    def is_barrier(self): return self.color == Color.BLACK.value
    def is_start(self): return self.color == Color.GREEN.value
    def is_end(self): return self.color == Color.RED.value

    def draw(self, win):
        if self.color != Color.WHITE.value:
            pygame.draw.rect(win, self.color,
                            (self.x, self.y, self.width, self.width))