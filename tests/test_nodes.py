"""Tests for node execute() and to_code() methods."""

import pandas as pd
import pytest

from nodes import get_tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def exe(tool_type: str, params: dict, inputs: dict) -> dict:
    """Execute a tool and return its output dict."""
    logs = []
    tool = get_tool(tool_type)
    assert tool is not None, f"Unknown tool: {tool_type}"
    return tool.execute(params, inputs, lambda m, level="info": logs.append(m))


def code(
    tool_type: str, params: dict, input_vars: list, output_var: str = "df_out", connected_outs=None
) -> list[str]:
    tool = get_tool(tool_type)
    return tool.to_code(params, input_vars, output_var, connected_outs)


# ---------------------------------------------------------------------------
# SelectColumns
# ---------------------------------------------------------------------------


def test_select_columns_keeps_subset(simple_df):
    result = exe("select_columns", {"columns": ["name", "dept"]}, {"data": simple_df})
    assert list(result["data"].columns) == ["name", "dept"]


def test_select_columns_missing_col_returns_empty(simple_df):
    # SelectColumns silently drops columns that don't exist in the DataFrame
    result = exe("select_columns", {"columns": ["nonexistent"]}, {"data": simple_df})
    assert len(result["data"].columns) == 0


def test_select_columns_raises_on_no_input():
    with pytest.raises(ValueError):
        exe("select_columns", {"columns": ["name"]}, {})


# ---------------------------------------------------------------------------
# FilterRows
# ---------------------------------------------------------------------------


def test_filter_equals(simple_df):
    result = exe(
        "filter_rows",
        {"conditions": [{"column": "dept", "operator": "equals", "value": "Eng"}]},
        {"data": simple_df},
    )
    assert len(result["true"]) == 2
    assert len(result["false"]) == 2


def test_filter_greater_than(simple_df):
    result = exe(
        "filter_rows",
        {"conditions": [{"column": "salary", "operator": "greater_than", "value": "80000"}]},
        {"data": simple_df},
    )
    assert set(result["true"]["name"]) == {"Alice", "Carol"}


def test_filter_no_conditions_passes_all(simple_df):
    result = exe("filter_rows", {"conditions": []}, {"data": simple_df})
    assert len(result["true"]) == len(simple_df)
    assert len(result["false"]) == 0


def test_filter_and_logic(simple_df):
    result = exe(
        "filter_rows",
        {
            "conditions": [
                {"column": "dept", "operator": "equals", "value": "Eng"},
                {"column": "salary", "operator": "greater_than", "value": "92000"},
            ],
            "logic": "AND",
        },
        {"data": simple_df},
    )
    assert list(result["true"]["name"]) == ["Carol"]


def test_filter_or_logic(simple_df):
    result = exe(
        "filter_rows",
        {
            "conditions": [
                {"column": "dept", "operator": "equals", "value": "HR"},
                {"column": "salary", "operator": "greater_than", "value": "92000"},
            ],
            "logic": "OR",
        },
        {"data": simple_df},
    )
    assert len(result["true"]) == 3  # Bob, Carol, Dave


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


def test_sort_ascending(simple_df):
    result = exe(
        "sort", {"rules": [{"column": "salary", "order": "ascending"}]}, {"data": simple_df}
    )
    salaries = list(result["data"]["salary"])
    assert salaries == sorted(salaries)


def test_sort_descending(simple_df):
    result = exe(
        "sort", {"rules": [{"column": "salary", "order": "descending"}]}, {"data": simple_df}
    )
    salaries = list(result["data"]["salary"])
    assert salaries == sorted(salaries, reverse=True)


def test_sort_no_rules_passthrough(simple_df):
    result = exe("sort", {"rules": []}, {"data": simple_df})
    pd.testing.assert_frame_equal(result["data"], simple_df)


# ---------------------------------------------------------------------------
# HeadTail
# ---------------------------------------------------------------------------


def test_head_keeps_first_n(simple_df):
    result = exe("head_tail", {"mode": "head", "n": 2}, {"data": simple_df})
    assert len(result["data"]) == 2
    assert list(result["data"]["name"]) == ["Alice", "Bob"]


def test_tail_keeps_last_n(simple_df):
    result = exe("head_tail", {"mode": "tail", "n": 2}, {"data": simple_df})
    assert len(result["data"]) == 2
    assert list(result["data"]["name"]) == ["Carol", "Dave"]


# ---------------------------------------------------------------------------
# RenameColumns
# ---------------------------------------------------------------------------


def test_rename_columns(simple_df):
    result = exe(
        "rename_columns", {"renames": [{"from": "name", "to": "employee"}]}, {"data": simple_df}
    )
    assert "employee" in result["data"].columns
    assert "name" not in result["data"].columns


# ---------------------------------------------------------------------------
# GroupBy
# ---------------------------------------------------------------------------


def test_group_by_sum(simple_df):
    result = exe(
        "group_by",
        {
            "group_cols": ["dept"],
            "aggs": [{"column": "salary", "func": "sum", "alias": "total_salary"}],
        },
        {"data": simple_df},
    )
    df = result["data"].set_index("dept")
    assert df.loc["Eng", "total_salary"] == 90000 + 95000
    assert df.loc["HR", "total_salary"] == 55000 + 60000


def test_group_by_default_column_name(simple_df):
    # No alias supplied → column falls back to <col>_<func>
    result = exe(
        "group_by",
        {
            "group_cols": ["dept"],
            "aggs": [{"column": "salary", "func": "sum", "alias": ""}],
        },
        {"data": simple_df},
    )
    df = result["data"].set_index("dept")
    assert df.loc["Eng", "salary_sum"] == 90000 + 95000


def test_group_by_count(simple_df):
    result = exe(
        "group_by",
        {
            "group_cols": ["dept"],
            "aggs": [{"column": "name", "func": "count", "alias": "headcount"}],
        },
        {"data": simple_df},
    )
    df = result["data"].set_index("dept")
    assert df.loc["Eng", "headcount"] == 2
    assert df.loc["HR", "headcount"] == 2


# ---------------------------------------------------------------------------
# MergeJoin
# ---------------------------------------------------------------------------


def test_merge_inner_join(two_dfs):
    left, right = two_dfs
    result = exe(
        "merge_join",
        {
            "how": "inner",
            "key_pairs": [{"left_key": "id", "right_key": "id"}],
        },
        {"left": left, "right": right},
    )
    assert len(result["joined"]) == 2  # ids 2 and 3 match
    assert len(result["left_unmatched"]) == 1  # id 1
    assert len(result["right_unmatched"]) == 1  # id 4


def test_merge_left_join(two_dfs):
    left, right = two_dfs
    result = exe(
        "merge_join",
        {
            "how": "left",
            "key_pairs": [{"left_key": "id", "right_key": "id"}],
        },
        {"left": left, "right": right},
    )
    assert len(result["joined"]) == 3  # all left rows preserved


# ---------------------------------------------------------------------------
# RecordID
# ---------------------------------------------------------------------------


def test_record_id_default(simple_df):
    result = exe("record_id", {"field_name": "row_id", "start": 1}, {"data": simple_df})
    assert "row_id" in result["data"].columns
    assert list(result["data"]["row_id"]) == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Code generation smoke tests
# ---------------------------------------------------------------------------


def test_filter_codegen_no_conditions():
    lines = code("filter_rows", {}, ["df_in"], connected_outs=["true", "false"])
    assert any("pd.Series(True" in line for line in lines)
    full = "\n".join(lines)
    assert "df_in.index" in full  # the bug fix: {iv} must be interpolated


def test_export_codegen_import_csv():
    lines = code("import_csv", {"file_path": "/tmp/x.csv", "delimiter": "comma"}, [], "df_out")
    assert len(lines) == 1
    assert "pd.read_csv" in lines[0]
    assert "/tmp/x.csv" in lines[0]


def test_sort_codegen():
    lines = code("sort", {"rules": [{"column": "age", "order": "descending"}]}, ["df_in"], "df_out")
    assert "sort_values" in lines[0]
    assert "False" in lines[0]  # ascending=False
