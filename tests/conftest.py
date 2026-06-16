# tests/conftest.py
# Fixtures and configuration for pytest
import sys
import os

# Ensure src directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
