import pytest
from src.strategy_pool import StrategyPool, StrategyMetadata

VALID_CODE = "def calculate_dynamic_signals(state, history): return {}"
INVALID_CODE = "def calc(): pass"


def test_add_strategy():
    pool = StrategyPool()
    pool.strategies.clear()
    sid = pool.add_strategy(VALID_CODE, "Test Strategy", "A test strategy")
    assert sid is not None
    assert len(pool.strategies) == 1
    assert sid in pool.strategies
    assert pool.strategies[sid].name == "Test Strategy"
    assert pool.strategies[sid].explanation == "A test strategy"


def test_add_strategy_generates_id():
    pool = StrategyPool()
    pool.strategies.clear()
    sid1 = pool.add_strategy(VALID_CODE, "S1")
    sid2 = pool.add_strategy(VALID_CODE, "S2")
    assert sid1 is not None
    assert sid2 is not None
    assert sid1 != sid2
    assert len(sid1) == 8
    assert len(sid2) == 8


def test_add_strategy_rejects_invalid_code():
    pool = StrategyPool()
    pool.strategies.clear()
    sid = pool.add_strategy(INVALID_CODE, "Bad Strategy")
    assert sid is None
    assert len(pool.strategies) == 0


def test_add_strategy_rejects_empty_code():
    pool = StrategyPool()
    pool.strategies.clear()
    sid = pool.add_strategy("", "Empty")
    assert sid is None


def test_add_strategy_sanitizes_name():
    pool = StrategyPool()
    pool.strategies.clear()
    sid = pool.add_strategy(VALID_CODE, "  Very Long Name " * 20)
    assert sid is not None
    assert len(pool.strategies[sid].name) <= 100


def test_remove_strategy():
    pool = StrategyPool()
    pool.strategies.clear()
    sid = pool.add_strategy(VALID_CODE, "Test Strategy")
    assert sid is not None
    pool.remove_strategy(sid)
    assert sid not in pool.strategies


def test_remove_nonexistent_strategy_does_not_error():
    pool = StrategyPool()
    pool.strategies.clear()
    pool.remove_strategy("nonexistent")


def test_get_all():
    pool = StrategyPool()
    pool.strategies.clear()
    pool.add_strategy(VALID_CODE, "S1")
    pool.add_strategy(VALID_CODE, "S2")
    all_strats = pool.get_all()
    assert len(all_strats) == 2
    assert all(isinstance(s, StrategyMetadata) for s in all_strats)


def test_get_all_empty():
    pool = StrategyPool()
    pool.strategies.clear()
    assert pool.get_all() == []


def test_strategy_metadata_defaults():
    sm = StrategyMetadata(id="abc12345", code=VALID_CODE, name="Test")
    assert sm.explanation == ""
    assert sm.parent_id is None
