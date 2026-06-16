import json
import os
import uuid
import logging
from typing import Dict, Any, List

logger = logging.getLogger("tradeer")
STRATEGY_POOL_FILE = "strategy_pool.json"

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
        self.load()

    def add_strategy(self, code: str, name: str, explanation: str = "", parent_id: str = None) -> str:
        strategy_id = str(uuid.uuid4())[:8]
        self.strategies[strategy_id] = StrategyMetadata(strategy_id, code, name, explanation, parent_id)
        self.save()
        return strategy_id

    def remove_strategy(self, strategy_id: str):
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            self.save()

    def get_all(self) -> List[StrategyMetadata]:
        return list(self.strategies.values())

    def save(self):
        data = {
            s_id: {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "explanation": s.explanation,
                "parent_id": s.parent_id
            } for s_id, s in self.strategies.items()
        }
        with open(STRATEGY_POOL_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        if os.path.exists(STRATEGY_POOL_FILE):
            try:
                with open(STRATEGY_POOL_FILE, "r") as f:
                    data = json.load(f)
                    for s_id, s in data.items():
                        self.strategies[s_id] = StrategyMetadata(
                            s["id"], s["code"], s["name"], s.get("explanation", ""), s.get("parent_id")
                        )
            except Exception as e:
                logger.error(f"Failed to load strategy pool from {STRATEGY_POOL_FILE}: {e}")
                self.strategies = {}

# Singleton instance
POOL = StrategyPool()
