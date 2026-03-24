import threading
from typing import Optional
from src.core import WorldState

# The "Atom" - a simple container for the latest value
class StateAtom:
    def __init__(self):
        self._value: WorldState = WorldState(timestamp=0)
        self._lock = threading.Lock()
        
    def swap(self, new_value: WorldState):
        with self._lock:
            self._value = new_value
            
    def deref(self) -> WorldState:
        with self._lock:
            return self._value

# Global singleton for the state
SHARED_STATE = StateAtom()
