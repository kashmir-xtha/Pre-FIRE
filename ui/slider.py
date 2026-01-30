import pygame_gui
import pygame


class Slider:
    def __init__(self, label, getter, setter, manager,
                 x, y, width=180, min_val=0.0, max_val=1.0):

        self.label = label
        self._getter = getter
        self._setter = setter

        # Label
        self.label_element = pygame_gui.elements.UILabel(
            pygame.Rect(x, y, width, 25),
            text=label,
            manager=manager
        )

        # Slider
        self.slider = pygame_gui.elements.UIHorizontalSlider(
            pygame.Rect(x, y + 25, width, 30),
            start_value=self._getter(),
            value_range=(min_val, max_val),
            manager=manager
        )

        # Value display
        self.value_label = pygame_gui.elements.UILabel(
            pygame.Rect(x, y + 60, width, 20),
            text=f"{self._getter():.3f}",
            manager=manager
        )

    def update(self, event):
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if event.ui_element == self.slider:
                self._setter(event.value)
                self.value_label.set_text(f"{event.value:.3f}")
                return True
        return False

    def destroy(self):
        self.label_element.kill()
        self.slider.kill()
        self.value_label.kill()


class SliderGroup:
    def __init__(self, manager):
        self.manager = manager
        self.sliders = []

    def add_slider(self, slider):
        self.sliders.append(slider)

    def handle_event(self, event):
        for slider in self.sliders:
            slider.update(event)

    def clear(self):
        for slider in self.sliders:
            slider.destroy()
        self.sliders.clear()


def create_fire_control_sliders(manager, x, start_y, temp_obj, spacing=80):
    group = SliderGroup(manager)

    group.add_slider(
        Slider(
            "Fire Spread Probability",
            lambda: temp_obj.FIRE_SPREAD_PROBABILITY,
            lambda v: setattr(temp_obj, "FIRE_SPREAD_PROBABILITY", v),
            manager,
            x, start_y,
            min_val=0.0, max_val=1.0
        )
    )

    start_y += spacing

    group.add_slider(
        Slider(
            "Smoke Decay",
            lambda: temp_obj.SMOKE_DECAY,
            lambda v: setattr(temp_obj, "SMOKE_DECAY", v),
            manager,
            x, start_y,
            min_val=0.0, max_val=1.0
        )
    )

    start_y += spacing

    group.add_slider(
        Slider(
            "Smoke Diffusion",
            lambda: temp_obj.SMOKE_DIFFUSION,
            lambda v: setattr(temp_obj, "SMOKE_DIFFUSION", v),
            manager,
            x, start_y,
            min_val=0.0, max_val=0.2
        )
    )

    return group
