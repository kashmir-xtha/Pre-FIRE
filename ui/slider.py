from typing import Callable

import pygame
import pygame_gui

class Slider:
    def __init__(
        self,
        label: str,
        getter: Callable[[], float],
        setter: Callable[[float], None],
        manager: pygame_gui.UIManager,
        x: int,
        y: int,
        width: int = 180,
        min_val: float = 0.0,
        max_val: float = 1.0,
        scale: float = 1.0,
    ) -> None:

        self.manager = manager
        self.label = label
        self._getter = getter
        self._setter = setter
        self.min_val = min_val
        self.max_val = max_val
        # x, y and width are expected to already be physical (scaled)
        self.x = x
        self.y = y
        self.width = width
        self.scale = scale

        self._build()

    def _build(self) -> None:
        # self.x , y, width are already in pixels.  we only need ``scale`` for the heights of the individual components and for font sizing.
        s = self.scale
        x = self.x
        y = self.y
        w = self.width

        self.label_element = pygame_gui.elements.UILabel(
            pygame.Rect(x, y, w, int(25 * s)),
            text=self.label,
            manager=self.manager
        )

        self.slider = pygame_gui.elements.UIHorizontalSlider(
            pygame.Rect(x, y + int(25 * s), w, int(30 * s)),
            start_value=self._getter(),
            value_range=(self.min_val, self.max_val),
            manager=self.manager
        )

        self.value_label = pygame_gui.elements.UILabel(
            pygame.Rect(x, y + int(60 * s), w, int(20 * s)),
            text=f"{self._getter():.3f}",
            manager=self.manager
        )

    def rebind(
        self,
        label: str,
        getter: Callable[[], float],
        setter: Callable[[float], None],
        min_val: float,
        max_val: float,
    ) -> None:
        self.destroy()

        self.label = label
        self._getter = getter
        self._setter = setter
        self.min_val = min_val
        self.max_val = max_val

        self._build()

    def update(self, event: pygame.event.Event) -> bool:
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if event.ui_element == self.slider:
                self._setter(event.value)
                self.value_label.set_text(f"{event.value:.3f}")
                return True
        return False

    def destroy(self) -> None:
        self.label_element.kill()
        self.slider.kill()
        self.value_label.kill()

class ControlPanel:
    def __init__(self, manager: pygame_gui.UIManager, x: int, y: int, temp_obj, scale: float = 1.0) -> None:
        self.manager = manager
        self.x = x
        self.y = y
        self.temp = temp_obj
        self.scale = scale

        self.label_to_param = {
            meta["label"]: name
            for name, meta in self.temp.PARAMS.items()
        }
        self.param_names = list(self.label_to_param.values())

        # dropdown dimensions should scale with DPI
        dropdown_w = int(180 * self.scale)
        dropdown_h = int(30 * self.scale)
        self.dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=list(self.label_to_param.keys()),
            starting_option=list(self.label_to_param.keys())[0],
            relative_rect=pygame.Rect(self.x, self.y, dropdown_w, dropdown_h),
            manager=manager
        )

        self.slider = None
        self._create_slider(self.param_names[0])

    def _create_slider(self, param_name: str) -> None:
        meta = self.temp.PARAMS[param_name]

        getter = lambda p=param_name: getattr(self.temp, p)
        setter = lambda v, p=param_name: setattr(self.temp, p, v)

        if self.slider:
            self.slider.rebind(
                meta["label"],
                getter,
                setter,
                meta["min"],
                meta["max"]
            )
        else:
            # position slider below dropdown; use pixel values
            slider_x = self.x
            slider_y = self.y + int(40 * self.scale)
            slider_w = int(180 * self.scale)
            self.slider = Slider(
                meta["label"],
                getter,
                setter,
                self.manager,
                slider_x,
                slider_y,
                width=slider_w,
                min_val=meta["min"],
                max_val=meta["max"],
                scale=self.scale,
            )

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.slider:
            self.slider.update(event)

        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self.dropdown:
                param_name = self.label_to_param[event.text]
                self._create_slider(param_name)

    def clear(self) -> None:
        self.dropdown.kill()
        if self.slider:
            self.slider.destroy()

def create_control_panel(
    manager: pygame_gui.UIManager,
    x: int,
    y: int,
    temp_obj,
    scale: float = 1.0,
) -> ControlPanel:
    return ControlPanel(manager, x, y, temp_obj, scale)
