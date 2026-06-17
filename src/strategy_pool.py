import json
import os
import threading
import uuid
import tempfile
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("tradeer")
STRATEGY_POOL_FILE = "strategy_pool.json"

def _validate_code(code: str) -> bool:
    """Basic structural validation: must be non-empty, must contain the expected function."""
    if not code or not isinstance(code, str):
        return False
    if "def calculate_dynamic_signals" not in code:
        return False
    return True

def _validate_name(name: str) -> str:
    """Sanitize name: max 100 chars, strip dangerous chars."""
    if not name or not isinstance(name, str):
        return "Unnamed Strategy"
    return name.strip()[:100]

def _validate_explanation(explanation: str) -> str:
    """Sanitize explanation: max 500 chars."""
    if not explanation or not isinstance(explanation, str):
        return ""
    return explanation.strip()[:500]

class StrategyMetadata:
    def __init__(self, id: str, code: str, name: str, explanation: str = "", parent_id: str = None):
        self.id = id
        self.code = code
        self.name = name
        self.explanation = explanation
        self.parent_id = parent_id

class StrategyPool:
    def __init__(self):
        self.strategies: Dict[str, StrategyMetadata] = {}
        self._lock = threading.Lock()
        self.load()

    def add_strategy(self, code: str, name: str, explanation: str = "", parent_id: str = None) -> Optional[str]:
        if not _validate_code(code):
            logger.warning("Strategy pool rejected invalid code (missing calculate_dynamic_signals)")
            return None

        sanitized_name = _validate_name(name)
        sanitized_explanation = _validate_explanation(explanation)

        strategy_id = str(uuid.uuid4())[:8]
        with self._lock:
            self.strategies[strategy_id] = StrategyMetadata(
                strategy_id, code, sanitized_name, sanitized_explanation, parent_id
            )
        self.save()
        return strategy_id

    def remove_strategy(self, strategy_id: str):
        with self._lock:
            if strategy_id in self.strategies:
                del self.strategies[strategy_id]
        self.save()

    def get_all(self) -> List[StrategyMetadata]:
        with self._lock:
            return list(self.strategies.values())

    def save(self):
        with self._lock:
            data = {
                s_id: {
                    "id": s.id,
                    "code": s.code,
                    "name": s.name,
                    "explanation": s.explanation,
                    "parent_id": s.parent_id
                } for s_id, s in self.strategies.items()
            }
        # Atomic write via tempfile + rename (outside the lock to avoid I/O under lock)
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(STRATEGY_POOL_FILE) or ".")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, STRATEGY_POOL_FILE)
        except Exception:
            os.unlink(tmp_path)
            raise

    def load(self):
        if os.path.exists(STRATEGY_POOL_FILE):
            try:
                with open(STRATEGY_POOL_FILE, "r") as f:
                    data = json.load(f)
                    with self._lock:
                        for s_id, s in data.items():
                            self.strategies[s_id] = StrategyMetadata(
                                s["id"], s["code"], s["name"], s.get("explanation", ""), s.get("parent_id")
                            )
            except Exception as e:
                logger.error(f"Failed to load strategy pool from {STRATEGY_POOL_FILE}: {e}")
                with self._lock:
                    self.strategies = {}

# Singleton instance
POOL = StrategyPool()
