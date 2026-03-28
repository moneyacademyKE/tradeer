import threading
from typing import Callable, Optional
from src.core import WorldState

# The "Atom" - identity container for an immutable value
class StateAtom:
    def __init__(self):
        self._value: WorldState = WorldState(timestamp=0)
        self._lock = threading.Lock()
        
    def swap(self, f: Callable[[WorldState, Any], WorldState], *args, **kwargs) -> WorldState:
        """
        Atomically swaps the state by applying the function `f` to the current state.
        This ensures the identity is updated through a consistent transformation.
        """
        with self._lock:
            # Apply transformation function to the current immutable value
            new_value = f(self._value, *args, **kwargs)
            self._value = new_value
            return self._value
            
    def reset(self, new_value: WorldState) -> WorldState:
        """Explicitly reset state to a new value."""
        with self._lock:
            self._value = new_value
            return self._value
            
    def deref(self) -> WorldState:
        """Read the current immutable snapshot."""
        with self._lock:
            return self._value

from typing import Any # Added for swap type hint

# Global singleton representing the Identity of the Quant Lab
SHARED_STATE = StateAtom()
