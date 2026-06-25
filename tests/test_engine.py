"""Tests for engine.py — topological sort and execute_flow."""

import pytest

from engine import Edge, Node, execute_flow, topological_sort

# ---------------------------------------------------------------------------
# topological_sort
# ---------------------------------------------------------------------------


def test_sort_single_node():
    n = Node("comment", 0, 0)
    assert topological_sort([n], []) == [n]


def test_sort_linear_chain():
    a = Node("import_csv", 0, 0)
    b = Node("filter_rows", 200, 0)
    c = Node("sort", 400, 0)
    edges = [Edge(a.id, "data", b.id, "data"), Edge(b.id, "true", c.id, "data")]
    order = topological_sort([a, b, c], edges)
    assert order.index(a) < order.index(b) < order.index(c)


def test_sort_diamond():
    """Two branches that both feed into a union."""
    src = Node("import_csv", 0, 0)
    left = Node("filter_rows", 200, 0)
    rgt = Node("sort", 200, 150)
    dst = Node("union", 400, 75)
    edges = [
        Edge(src.id, "data", left.id, "data"),
        Edge(src.id, "data", rgt.id, "data"),
        Edge(left.id, "true", dst.id, "top"),
        Edge(rgt.id, "data", dst.id, "bottom"),
    ]
    order = topological_sort([src, left, rgt, dst], edges)
    assert order.index(src) < order.index(left)
    assert order.index(src) < order.index(rgt)
    assert order.index(left) < order.index(dst)
    assert order.index(rgt) < order.index(dst)


def test_sort_raises_on_cycle():
    a = Node("filter_rows", 0, 0)
    b = Node("sort", 200, 0)
    edges = [Edge(a.id, "data", b.id, "data"), Edge(b.id, "data", a.id, "data")]
    with pytest.raises(ValueError, match="Cycle"):
        topological_sort([a, b], edges)


def test_sort_ignores_dangling_edges():
    """Edges referencing unknown node IDs should not crash the sort."""
    a = Node("import_csv", 0, 0)
    dangling = Edge("nonexistent", "data", a.id, "data")
    order = topological_sort([a], [dangling])
    assert order == [a]


def test_sort_empty_graph():
    assert topological_sort([], []) == []


# ---------------------------------------------------------------------------
# execute_flow — helpers
# ---------------------------------------------------------------------------


def _csv_node(path: str) -> Node:
    n = Node("import_csv", 0, 0)
    n.params["file_path"] = path
    n.params["delimiter"] = "comma"
    return n


# ---------------------------------------------------------------------------
# execute_flow
# ---------------------------------------------------------------------------


def test_execute_single_import(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n3,4\n")
    n = _csv_node(str(csv))
    execute_flow([n], [])
    assert n.result is not None
    df = n.result["data"]
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_execute_filter_keeps_correct_rows(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("name,score\nAlice,90\nBob,40\nCarol,75\n")
    n1 = _csv_node(str(csv))
    n2 = Node("filter_rows", 200, 0)
    n2.params["conditions"] = [{"column": "score", "operator": "greater_than", "value": "50"}]
    n2.params["logic"] = "AND"
    execute_flow([n1, n2], [Edge(n1.id, "data", n2.id, "data")])
    assert len(n2.result["true"]) == 2  # Alice, Carol
    assert len(n2.result["false"]) == 1  # Bob


def test_execute_skips_disabled_node(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x\n1\n2\n")
    n1 = _csv_node(str(csv))
    n2 = Node("sort", 200, 0)
    n2.disabled = True
    n2.params["rules"] = [{"column": "x", "order": "descending"}]
    execute_flow([n1, n2], [Edge(n1.id, "data", n2.id, "data")])
    assert n2.result is None  # disabled, never ran


def test_execute_logs_errors_on_bad_tool():
    n = Node("__nonexistent_tool__", 0, 0)
    log_msgs = []
    execute_flow([n], [], log=lambda m, level="info": log_msgs.append((level, m)))
    assert any(level == "error" for level, _ in log_msgs)


def test_execute_returns_result_dict(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("v\n10\n20\n")
    n = _csv_node(str(csv))
    results = execute_flow([n], [])
    assert n.id in results
    assert "data" in results[n.id]


def test_execute_sort_order(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("n\n3\n1\n2\n")
    n1 = _csv_node(str(csv))
    n2 = Node("sort", 200, 0)
    n2.params["rules"] = [{"column": "n", "order": "ascending"}]
    execute_flow([n1, n2], [Edge(n1.id, "data", n2.id, "data")])
    assert list(n2.result["data"]["n"]) == [1, 2, 3]
