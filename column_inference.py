from __future__ import annotations
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Node, Edge


def infer_columns(target_node_id: str, target_port: str,
                  nodes: list, edges: list,
                  port: str = "data") -> list[str]:
    """
    Trace upstream from (target_node_id, target_port) and return
    the column names available at that input.
    """
    nodes_by_id = {n.id: n for n in nodes}
    # Find which source is wired to this input port
    for edge in edges:
        if edge.dst_node == target_node_id and edge.dst_port == target_port:
            src_node = nodes_by_id.get(edge.src_node)
            if src_node:
                return _cols_from_node(src_node, edge.src_port, nodes, edges)
    return []


def _cols_from_node(node, port: str, nodes: list, edges: list) -> list[str]:
    from nodes import get_tool

    # 1. Live result
    if node.result and isinstance(node.result, dict):
        df = node.result.get(port)
        if df is not None and hasattr(df, "columns"):
            return list(df.columns)

    tool = get_tool(node.kind)
    if tool is None:
        return []

    # 2. Import CSV — read file headers
    if node.kind == "import_csv":
        path = node.params.get("file_path", "")
        if path and os.path.exists(path):
            try:
                import pandas as pd
                from constants import TOOL_COLORS  # noqa: just a guard
                dm = node.params.get("delimiter", "comma")
                sep_map = {"comma": ",", "tab": "\t", "pipe": "|", "semicolon": ";"}
                sep = sep_map.get(dm, node.params.get("custom_delim", ",") or ",")
                df = pd.read_csv(path, sep=sep, nrows=0)
                return list(df.columns)
            except Exception:
                pass

    # 3. Import Excel — read sheet headers
    if node.kind == "import_excel":
        path = node.params.get("file_path", "")
        if path and os.path.exists(path):
            try:
                import pandas as pd
                sheet = node.params.get("sheet_name") or 0
                df = pd.read_excel(path, sheet_name=sheet, nrows=0, engine="openpyxl")
                return list(df.columns)
            except Exception:
                pass

    # 4. SelectColumns — forward the selected list
    if node.kind == "select_columns":
        cols = node.params.get("columns", [])
        if isinstance(cols, list) and cols:
            return cols
        if isinstance(cols, str):
            parsed = [c.strip() for c in cols.split(",") if c.strip()]
            if parsed:
                return parsed
        # Fall through to its own upstream
        return _trace_upstream(node, "data", nodes, edges)

    # 5. For any other pass-through tool, trace upstream recursively
    if "data" in (tool.ins or []) and port == (tool.outs[0] if tool.outs else ""):
        return _trace_upstream(node, "data", nodes, edges)

    return []


def _trace_upstream(node, in_port: str, nodes: list, edges: list) -> list[str]:
    nodes_by_id = {n.id: n for n in nodes}
    for edge in edges:
        if edge.dst_node == node.id and edge.dst_port == in_port:
            src = nodes_by_id.get(edge.src_node)
            if src:
                return _cols_from_node(src, edge.src_port, nodes, edges)
    return []
