from typing import Dict, Optional, Sequence, Tuple

from utils.utilities import Color, TempConstants, state_value, material_id, fire_constants, rTemp
import pygame

WHITE = Color.WHITE.value
BLACK = Color.BLACK.value
GREEN = Color.GREEN.value
RED = Color.RED.value
FIRE_COLOR = Color.FIRE_COLOR.value

EMPTY = state_value.EMPTY.value
WALL = state_value.WALL.value
FIRE = state_value.FIRE.value
START = state_value.START.value
END =  state_value.END.value

AMBIENT_TEMP = fire_constants.AMBIENT_TEMP.value

ColorTuple = Tuple[int, int, int]
MaterialProps = Dict[str, object]


class Spot:
    _material_props_cache: Optional[Dict[material_id, MaterialProps]] = None

    @classmethod
    def _material_props(cls) -> Dict[material_id, MaterialProps]:
        if cls._material_props_cache is None:
            from environment.materials import MATERIALS
            cls._material_props_cache = MATERIALS
        return cls._material_props_cache

    def __init__(self, row: int, col: int, width: int) -> None:
        self.row = row
        self.col = col
        self.x = col * width
        self.y = row * width
        self.width = width
        
        # Private attributes with controlled access
        self._color = WHITE
        self._state = EMPTY
        self._temperature = AMBIENT_TEMP
        self._smoke = 0.0
        self._fuel = self._material_props().get(material_id.AIR, {}).get("fuel", 1.0)
        self._material = material_id.AIR  # Store as enum, not integer
        self._is_fire_source = False
        
    # --- Property getters for safe access ---
    @property
    def color(self) -> ColorTuple:
        return self._color
    
    @property
    def state(self) -> int:
        return self._state
    
    @property
    def temperature(self) -> float:
        return self._temperature
    
    @property
    def smoke(self) -> float:
        return self._smoke
    
    @property
    def fuel(self) -> float:
        return self._fuel
    
    @property
    def material(self) -> material_id:
        return self._material  # Returns enum
    
    @property
    def is_fire_source(self) -> bool:
        return self._is_fire_source
    
    # --- State-changing methods with validation ---
    def reset(self) -> None:
        """Reset spot to default state"""
        self._color = WHITE
        self._state = EMPTY
        self._temperature = AMBIENT_TEMP
        self._smoke = 0.0
        self._fuel = self._material_props().get(material_id.AIR, {}).get("fuel", 1.0)
        self._material = material_id.AIR
        self._is_fire_source = False
    
    def make_barrier(self) -> None:
        """Make this spot a barrier/wall"""
        self._color = BLACK
        self._state = WALL
        self._material = material_id.CONCRETE
        self._fuel = 0.0  # Walls don't burn
    
    def make_start(self) -> None:
        """Make this spot the starting position"""
        self._color = GREEN
        self._state = START
        self._material = material_id.AIR  # Start spot should be air
    
    def make_end(self) -> None:
        """Make this spot an exit"""
        self._color = RED
        self._state = END
        self._material = material_id.AIR  # End spot should be air
    
    def set_color(self, color: ColorTuple) -> None:
        """Set the color of the spot (used for path visualization)"""
        self._color = color
    
    def set_material(self, material: material_id) -> None:
        """Set material with proper initialization"""
        self._material = material
        props = self._material_props()
        self._fuel = props[material]["fuel"]
        self._state = props[material]["default_state"]
        # Only update color if not special state
        if not self.is_start() and not self.is_end():
            self._update_color_from_material()

    def set_on_fire(self, initial_temp: float = 600.0) -> None:
        """Set this spot on fire"""
        self._state = FIRE
        self._color = FIRE_COLOR
        self._temperature = max(self._temperature, initial_temp)
    
    def extinguish_fire(self) -> None:
        """Extinguish fire and reset to material"""
        if self.is_fire():
            self._state = EMPTY
            self._update_color_from_material()
            if self._is_fire_source:
                self._is_fire_source = False
    
    def set_as_fire_source(self, temp: float = 1200.0) -> None:
        """Mark this spot as a persistent fire source"""
        self._is_fire_source = True
        self.set_on_fire(temp)
    
    def remove_fire_source(self) -> None:
        """Remove fire source marking"""
        self._is_fire_source = False
    
    def add_smoke(self, amount: float) -> None:
        """Add smoke with bounds checking"""
        self._smoke = max(0.0, min(1.0, self._smoke + amount))
    
    def set_smoke(self, amount: float) -> None:
        """Set smoke amount with bounds checking"""
        self._smoke = max(0.0, min(1.0, amount))
    
    def add_temperature(self, amount: float) -> None:
        """Add temperature with bounds checking"""
        self._temperature = max(AMBIENT_TEMP, 
                              min(1200.0, self._temperature + amount))
    
    def set_temperature(self, temp: float) -> None:
        """Set temperature with bounds checking"""
        self._temperature = max(AMBIENT_TEMP, min(1200.0, temp))
    
    def consume_fuel(self, amount: float) -> None:
        """Consume fuel with bounds checking"""
        self._fuel = max(0.0, self._fuel - amount)
        if self._fuel <= 0 and self._state == FIRE:
            self.extinguish_fire()
    
    # --- Query methods ---
    def is_barrier(self) -> bool: 
        return self._state == WALL
    
    def is_start(self) -> bool: 
        return self._state == START
    
    def is_end(self) -> bool: 
        return self._state == END
    
    def is_fire(self) -> bool: 
        return self._state == FIRE
    
    def is_empty(self) -> bool: 
        return self._state == EMPTY
    
    def is_flammable(self) -> bool:
        """Check if this spot can catch fire"""
        return self._material_props()[self._material]["fuel"] > 0
    
    def is_hot_enough_to_ignite(self) -> bool:
        """Check if temperature is above ignition point"""
        ignition_temp = self._material_props()[self._material]["ignition_temp"]
        return self._temperature >= ignition_temp
    
    # --- Helper methods ---
    def _update_color_from_material(self) -> None:
        """Update color based on current material"""
        self._color = self._material_props()[self._material]["color"]
    
    def get_material_properties(self) -> MaterialProps:
        """Get material properties dictionary"""
        return self._material_props()[self._material]
    
    def to_dict(self) -> Dict[str, object]:
        """Convert spot to dictionary for debugging/serialization"""
        return {
            'row': self.row,
            'col': self.col,
            'state': self._state,
            'temperature': self._temperature,
            'smoke': self._smoke,
            'fuel': self._fuel,
            'material': self._material,  # Store value for serialization
            'is_fire_source': self._is_fire_source
        }
    
    def draw(self, win: pygame.Surface) -> None:
        """Draw the spot on the window"""
        if self._color != WHITE:
            pygame.draw.rect(win, self._color,
                            (self.x, self.y, self.width, self.width))

    def update_temperature_from_flux(
        self,
        heat_flux: float,
        tempConstant: TempConstants,
        dt: float,
    ) -> None:
        """
        Apply net heat flux (from grid diffusion) and local effects
        such as combustion and temperature clamping.
        """
        # Precompute dt factor for special cells
        dt_factor_special = 0.02 * dt

        # Cached boolean flag for special cells
        if getattr(self, 'is_special', None) is None:
            self.is_special = self.is_barrier() or self.is_start() or self.is_end()

        if self.is_special:
            ambient = tempConstant.AMBIENT_TEMP
            self._temperature += (ambient - self._temperature) * dt_factor_special
            return

        # Apply diffusion + cooling contribution
        self._temperature += heat_flux * dt
    
        # Check if currently on fire (don't use cached flag since fire state can change)
        if self.is_fire() and self.fuel > 0:

            # Cache material properties per cell
            if getattr(self, 'material_props', None) is None:
                self.material_props = self.get_material_properties()
            
            props = self.material_props
            heat_release = props.get("heat_release_rate", 500.0)  # °C/s equivalent
            fuel_burn_rate = props.get("fuel_burn_rate", 0.01)    # kg/s

            # Apply combustion heat
            #print(f"Applying combustion heat: {heat_release * dt:.2f}°C for fuel burn: {fuel_burn_rate * dt:.4f}kg")
            self._temperature += heat_release * dt

            # Fuel consumption
            self._fuel -= fuel_burn_rate * dt
            if self._fuel <= 0:
                self._fuel = 0.0
                self.extinguish_fire()  # only call if fuel depleted

        # Clamp temperature to physical bounds
        ambient = tempConstant.AMBIENT_TEMP
        self._temperature = max(ambient, min(self._temperature, 5000))

    def update_fire_state(
        self,
        neighbor_fire_states: Sequence[Tuple[bool, float]],
        tempConstants: TempConstants,
        dt: float,
    ) -> bool:
        """
        Update fire state based on neighbor information
        
        :param neighbor_fire_states: List of (has_fire, temperature) tuples
        :param dt: Delta time
        :return: True if caught fire, False otherwise
        """
        # Can't catch fire if already on fire, not flammable, or special cell
        if (not self.is_flammable() or 
            self.is_barrier() or self.is_start() or self.is_end()):
            return False
        
        if (self.is_fire() and self.fuel <= 0):
            self.extinguish_fire()
            return False
        
        # Auto-ignition from high temperature
        if self.is_hot_enough_to_ignite():
            import random
            if random.random() < 0.3 * dt:  # 30% chance per second
                self.set_on_fire()
                return True
        
        # Check for fire spread from neighbors
        import random
        
        for has_fire, neighbor_temp in neighbor_fire_states:
            if has_fire:
                # Direct flame contact
                if random.random() < tempConstants.FIRE_SPREAD_PROBABILITY * dt:
                    self.set_on_fire()
                    return True
        
        return False
    
    def update_smoke_level(
        self,
        neighbor_smoke_levels: Sequence[float],
        dt: float,
    ) -> None:
        """
        Update smoke level based on neighbors
        
        :param neighbor_smoke_levels: list of neighbor smoke value
        :param dt: Delta time
        """
        temp_constants = rTemp()
        # Walls block smoke
        if self.is_barrier():
            self.set_smoke(0.0)
            return
        
        # Fire produces smoke
        if self.is_fire():
            smoke_production = 3 * temp_constants.SMOKE_PRODUCTION * dt
            self.add_smoke(min(1.0, smoke_production))
            # Clamp to max
            if self._smoke > temp_constants.MAX_SMOKE:
                self._smoke = temp_constants.MAX_SMOKE
            return
        
        # Calculate diffusion from neighbors
        if neighbor_smoke_levels:
            for n_smoke in neighbor_smoke_levels:
                smoke_diff = n_smoke - self._smoke
                if smoke_diff > 0:
                    diffusion = temp_constants.SMOKE_DIFFUSION * smoke_diff
                    self.add_smoke(diffusion)
        
        # Apply natural decay
        decay_factor = 1.0 - (temp_constants.SMOKE_DECAY * dt)
        self._smoke *= decay_factor
        
        # Clamp to valid range
        self._smoke = max(0.0, min(temp_constants.MAX_SMOKE, self._smoke))
    
    def consume_fuel_update(self, dt: float) -> bool:
        """
        Consume fuel if on fire
        
        :param dt: Delta time
        :return: True if fuel ran out, False otherwise
        """
        if self.is_fire() and self._fuel > 0:
            self.consume_fuel(0.1 * dt)
            if self._fuel <= 0:
                self.extinguish_fire()
                return True
        return False