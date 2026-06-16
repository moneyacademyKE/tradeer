import threading
from typing import Any, Callable, Dict
from src.core import WorldState
import logging

logger = logging.getLogger("tradeer")

# The "Atom" - identity container for an immutable value
class StateAtom:
    def __init__(self):
        self._value: WorldState = WorldState(timestamp=0)
        self._lock = threading.Lock()
        self._watchers: Dict[str, Callable[[str, WorldState, WorldState], None]] = {}
        
    def add_watch(self, key: str, f: Callable[[str, WorldState, WorldState], None]):
        """
        Adds a watcher function to the atom.
        The watcher must accept 3 arguments: (key, old_state, new_state).
        """
        with self._lock:
            self._watchers[key] = f
            
    def remove_watch(self, key: str):
        """Removes a watcher from the atom."""
        with self._lock:
            if key in self._watchers:
                del self._watchers[key]
                
    def _run_watchers(self, old_value: WorldState, new_value: WorldState):
        """Runs all registered watchers outside the mutation lock to avoid deadlocks."""
        with self._lock:
            watchers = list(self._watchers.items())
            
        for key, f in watchers:
            try:
                f(key, old_value, new_value)
            except Exception as e:
                logger.error(f"Atom Watcher Error on key '{key}': {e}")

    def swap(self, f: Callable[[WorldState, Any], WorldState], *args, **kwargs) -> WorldState:
        """
        Atomically swaps the state by applying the function `f` to the current state.
        This ensures the identity is updated through a consistent transformation.
        """
        old_value = None
        with self._lock:
            old_value = self._value
            # Apply transformation function to the current immutable value
            new_value = f(self._value, *args, **kwargs)
            self._value = new_value
            
        self._run_watchers(old_value, new_value)
        return new_value
            
    def reset(self, new_value: WorldState) -> WorldState:
        """Explicitly reset state to a new value."""
        old_value = None
        with self._lock:
            old_value = self._value
            self._value = new_value
            
        self._run_watchers(old_value, new_value)
        return new_value
            
    def deref(self) -> WorldState:
        """
        Read the current immutable snapshot.
        This operation is completely lock-free and returns immediately.
        """
        return self._value


# Global singleton representing the Identity of the Quant Lab
SHARED_STATE = StateAtom()
