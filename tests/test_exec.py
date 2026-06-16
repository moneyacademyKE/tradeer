import pytest
from src.core import WorldState, Ticker
from src.main import execute_strategy_code, validate_strategy_code

def test_validate_safe_code():
    valid_code = """
def calculate_dynamic_signals(state, history):
    symbol = "BTC/USDT"
    rsi_2 = state.signals.get(f"{symbol}_rsi_2", 50.0)
    return {"gemini_buy": 1.0} if rsi_2 < 20.0 else {}
"""
    assert validate_strategy_code(valid_code) is True

def test_validate_rejects_import():
    unsafe_code = """
def calculate_dynamic_signals(state, history):
    import os
    return {}
"""
    assert validate_strategy_code(unsafe_code) is False

    unsafe_code_2 = """
from os import system
def calculate_dynamic_signals(state, history):
    return {}
"""
    assert validate_strategy_code(unsafe_code_2) is False

def test_validate_rejects_dunder_attributes():
    unsafe_code = """
def calculate_dynamic_signals(state, history):
    cls = state.__class__
    return {}
"""
    assert validate_strategy_code(unsafe_code) is False

def test_validate_rejects_dunder_names():
    unsafe_code = """
def calculate_dynamic_signals(state, history):
    __builtins__ = None
    return {}
"""
    assert validate_strategy_code(unsafe_code) is False

def test_validate_rejects_dangerous_builtins():
    for name in ["eval", "exec", "open", "compile", "globals", "locals", "__import__", "setattr", "delattr"]:
        unsafe_code = f"""
def calculate_dynamic_signals(state, history):
    {name}("1+1")
    return {{}}
"""
        assert validate_strategy_code(unsafe_code) is False

def test_safe_getattr_at_runtime():
    # Enforce that getattr blocks __class__ access at runtime
    unsafe_code = """
def calculate_dynamic_signals(state, history):
    # This might bypass AST Attribute checks if stored in a variable
    attr_name = "__class__"
    cls = getattr(state, attr_name)
    return {"ok": True}
"""
    # Even if AST validation was bypassed somehow, the runtime getattr should fail
    # resulting in execute_strategy_code returning {} instead of {"ok": True}
    state = WorldState(timestamp=0)
    res = execute_strategy_code(unsafe_code, state, {})
    assert res == {}
