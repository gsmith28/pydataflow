"""Tests for export_script.py — Python code generation."""

from engine import Edge, Node
from export_script import generate_python


def _csv_node(path: str) -> Node:
    n = Node("import_csv", 0, 0)
    n.params["file_path"] = path
    n.params["delimiter"] = "comma"
    return n


def test_generate_imports_header():
    code = generate_python([], [])
    assert "import pandas as pd" in code
    assert "PyDataFlow" in code


def test_generate_single_import(tmp_path):
    csv = tmp_path / "x.csv"
    csv.write_text("a,b\n1,2\n")
    n = _csv_node(str(csv))
    code = generate_python([n], [])
    assert "pd.read_csv" in code
    assert str(csv) in code


def test_generate_disabled_node_is_commented(tmp_path):
    csv = tmp_path / "x.csv"
    csv.write_text("a\n1\n")
    n = _csv_node(str(csv))
    n.disabled = True
    code = generate_python([n], [])
    assert "skipped (disabled)" in code
    assert "pd.read_csv" not in code


def test_generate_chain_produces_correct_var_references(tmp_path):
    csv = tmp_path / "x.csv"
    csv.write_text("score\n10\n20\n30\n")
    n1 = _csv_node(str(csv))
    n2 = Node("sort", 200, 0)
    n2.params["rules"] = [{"column": "score", "order": "descending"}]
    code = generate_python([n1, n2], [Edge(n1.id, "data", n2.id, "data")])
    # n2's generated line should reference n1's variable
    lines = [line for line in code.splitlines() if "sort_values" in line]
    assert lines, "Expected a sort_values line in exported code"
    assert f"df_import_csv_{n1.id}" in lines[0]


def test_generate_cycle_returns_error_comment():
    a = Node("filter_rows", 0, 0)
    b = Node("sort", 200, 0)
    code = generate_python(
        [a, b],
        [
            Edge(a.id, "data", b.id, "data"),
            Edge(b.id, "data", a.id, "data"),
        ],
    )
    assert "Export failed" in code


def test_generated_code_is_executable(tmp_path):
    """Round-trip: generate code, exec it, compare the resulting DataFrame."""
    csv = tmp_path / "data.csv"
    csv.write_text("name,score\nAlice,90\nBob,40\nCarol,75\n")

    n1 = _csv_node(str(csv))
    n2 = Node("filter_rows", 200, 0)
    n2.params["conditions"] = [{"column": "score", "operator": "greater_than", "value": "50"}]
    n2.params["logic"] = "AND"

    code = generate_python([n1, n2], [Edge(n1.id, "data", n2.id, "data")])

    ns: dict = {}
    exec(compile(code, "<generated>", "exec"), ns)  # noqa: S102

    true_var = f"df_filter_rows_{n2.id}_true"
    assert true_var in ns, f"Expected {true_var!r} in exported namespace; got {list(ns)}"
    result_df = ns[true_var]
    assert len(result_df) == 2
    assert set(result_df["name"]) == {"Alice", "Carol"}


def test_generated_group_by_honors_alias(tmp_path):
    """Exported GroupBy code must name columns with the alias, matching execute()."""
    csv = tmp_path / "data.csv"
    csv.write_text("dept,salary\nEng,90\nEng,95\nHR,55\n")

    n1 = _csv_node(str(csv))
    n2 = Node("group_by", 200, 0)
    n2.params["group_cols"] = ["dept"]
    n2.params["aggs"] = [{"column": "salary", "func": "sum", "alias": "total_salary"}]

    code = generate_python([n1, n2], [Edge(n1.id, "data", n2.id, "data")])

    ns: dict = {}
    exec(compile(code, "<generated>", "exec"), ns)  # noqa: S102

    out_var = f"df_group_by_{n2.id}"
    assert out_var in ns, f"Expected {out_var!r} in exported namespace; got {list(ns)}"
    result_df = ns[out_var].set_index("dept")
    assert "total_salary" in result_df.columns
    assert result_df.loc["Eng", "total_salary"] == 185
