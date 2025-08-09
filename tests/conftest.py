"""
Pytest configuration for Invoice Hawk tests.

This conftest ensures the repository root is added to ``sys.path`` so that
modules such as ``app.match_po`` can be imported by test files. Without
adjusting ``sys.path``, running ``pytest`` from the project root may
result in ``ModuleNotFoundError`` for the ``app`` package because the
current working directory might not be included in Python's import search
path when using certain pytest import modes.
"""

import os
import sys

# Compute the repository root relative to this file (tests directory is one level deep)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Prepend the root directory to sys.path if it's not already present
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)