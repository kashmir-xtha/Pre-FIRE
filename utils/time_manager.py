# time_manager.py
import pygame
import time

class TimeManager:
    def __init__(self, fps=60, step_size=1):
        self.clock = pygame.time.Clock()
        self.fps = fps
        
        self.paused = False
        self.simulation_running = True
        self.step_by_step = False
        self.next_step_requested = False
        
        self.delta_time = 0
        self.total_time = 0
        self.frame_count = 0
        self.simulation_step = 0
        self.step_size = step_size
        
        self.last_time = time.time()
        self.avg_fps = 0
        
    def update(self):
        current_time = time.time()
        self.delta_time = current_time - self.last_time
        self.last_time = current_time

        # Update FPS smoothing
        if self.delta_time > 0:
            current_fps = 1 / self.delta_time
            self.avg_fps = self.avg_fps * 0.9 + current_fps * 0.1

        # Respect pygame tick
        self.clock.tick(self.fps)

        # Step-by-step mode takes priority and should be able to advance one step
        if self.step_by_step:
            if self.next_step_requested:
                # consume the request and count this as a step
                self.next_step_requested = False
                self.total_time += self.delta_time
                self.simulation_step += 1
                return True
            return False

        # Normal running/paused logic
        if not self.paused:
            self.total_time += self.delta_time
            self.simulation_step += 1
            return True

        return False
    
    def should_update_simulation(self):
        if self.paused:
            return False
        
        if self.step_by_step:
            if self.next_step_requested:
                self.next_step_requested = False
                return True
            return False
        
        return True
    
    def get_update_count(self):
        if self.step_by_step:
            return 1
        return self.step_size
    
    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused
    
    def set_paused(self, paused):
        self.paused = paused
    
    def toggle_step_mode(self):
        self.step_by_step = not self.step_by_step
        if self.step_by_step:
            self.paused = False
        return self.step_by_step
    
    def request_next_step(self):
        if self.step_by_step and not self.next_step_requested:
            self.next_step_requested = True
            return True
        return False
    
    def set_speed(self, multiplier):
        self.step_size = max(1, int(multiplier))
        return self.step_size
    
    def reset_timer(self):
        self.total_time = 0
        self.simulation_step = 0
        self.frame_count = 0
        self.last_time = time.time()
    
    def get_delta_time(self):
        return self.delta_time
    
    def get_total_time(self):
        return self.total_time
    
    def get_simulation_step(self):
        return self.simulation_step
    
    def get_fps(self):
        return self.avg_fps
    
    def is_paused(self):
        return self.paused
    
    def is_step_mode(self):
        return self.step_by_step
    
    def get_step_size(self):
        return self.step_size