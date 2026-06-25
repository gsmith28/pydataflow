"""Shared fixtures for the PyDataFlow test suite."""

import os
import sys

import pandas as pd
import pytest

# Ensure root package is importable when pytest is run from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def simple_df() -> pd.DataFrame:
    """A small DataFrame used across many node tests."""
    return pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Carol", "Dave"],
            "dept": ["Eng", "HR", "Eng", "HR"],
            "salary": [90000, 55000, 95000, 60000],
            "years": [5, 3, 8, 2],
        }
    )


@pytest.fixture
def two_dfs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two DataFrames suitable for join tests."""
    left = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Carol"]})
    right = pd.DataFrame({"id": [2, 3, 4], "dept": ["HR", "Eng", "Finance"]})
    return left, right
