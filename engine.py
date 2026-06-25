"""
Execution engine for PyDataFlow.

Provides two public functions:
  - topological_sort(nodes, edges) → ordered list of nodes (raises on cycles)
  - execute_flow(nodes, edges, log) → runs all non-disabled nodes in dependency order

Each node's output is stored on node.result as dict[port_name, DataFrame].
"""
from __future__ import annotations
import time
import uuid
from collections import defaultdict, deque
from typing import Callable
import pandas as pd

from nodes import get_tool


class Node:
    __slots__ = ("id", "kind", "x", "y", "params", "result", "disabled", "annotation")

    def __init__(self, kind: str, x: float = 100, y: float = 100,
                 node_id: str | None = None, params: dict | None = None,
                 disabled: bool = False, annotation: str = "") -> None:
        self.id = node_id or uuid.uuid4().hex[:8]
        self.kind = kind
        self.x = x
        self.y = y
        self.params: dict = params or {}
        self.result: dict | None = None
        self.disabled = disabled
        self.annotation = annotation


class Edge:
    __slots__ = ("id", "src_node", "src_port", "dst_node", "dst_port")

    def __init__(self, src_node: str, src_port: str,
                 dst_node: str, dst_port: str,
                 edge_id: str | None = None) -> None:
        self.id = edge_id or uuid.uuid4().hex[:8]
        self.src_node = src_node
        self.src_port = src_port
        self.dst_node = dst_node
        self.dst_port = dst_port


def topological_sort(nodes: list[Node], edges: list[Edge]) -> list[Node]:
    """Return nodes in execution order using Kahn's algorithm.

    Edges that reference node IDs not in `nodes` are silently ignored (dangling
    references from a partially-deleted graph).

    Raises ValueError if a cycle is detected.
    """
    all_ids = {n.id for n in nodes}
    in_deg: dict[str, int] = {n.id: 0 for n in nodes}
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.src_node in all_ids and e.dst_node in all_ids:
            adj[e.src_node].append(e.dst_node)
            in_deg[e.dst_node] += 1

    by_id = {n.id: n for n in nodes}
    queue: deque[Node] = deque(n for n in nodes if in_deg[n.id] == 0)
    result: list[Node] = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for dst_id in adj[node.id]:
            in_deg[dst_id] -= 1
            if in_deg[dst_id] == 0:
                queue.append(by_id[dst_id])

    if len(result) != len(nodes):
        raise ValueError("Cycle detected in workflow graph")
    return result


def execute_flow(nodes: list[Node], edges: list[Edge],
                 log: Callable[[str, str], None] | None = None) -> dict:
    """Run all non-disabled nodes in topological order.

    Each node's result dict is stored on node.result after execution.
    On tool error the node is skipped and the error is logged; downstream
    nodes receive no input from that port and will likely also fail.

    Returns a dict mapping node_id → output dict (same as node.result).
    Raises ValueError if the graph contains a cycle.
    Returns dict of node_id -> result_dict.
    Raises ValueError on cycle.
    """
    def _log(msg: str, level: str = "info") -> None:
        if log:
            log(msg, level)

    results: dict[str, dict] = {}

    try:
        ordered = topological_sort(nodes, edges)
    except ValueError as e:
        _log(str(e), "error")
        raise

    by_id = {n.id: n for n in nodes}

    # Build edge map: dst_node -> list[(src_node, src_port, dst_port)]
    edge_map: dict[str, list[tuple]] = defaultdict(list)
    for e in edges:
        edge_map[e.dst_node].append((e.src_node, e.src_port, e.dst_port))

    run_id = uuid.uuid4().hex[:8]
    history: list[dict] = []

    for node in ordered:
        if node.disabled:
            _log(f"[{node.kind}] skipped (disabled)")
            node.result = None
            continue

        tool = get_tool(node.kind)
        if tool is None:
            _log(f"Unknown tool type: {node.kind}", "error")
            continue

        # Gather inputs
        inputs: dict[str, pd.DataFrame] = {}
        for src_id, src_port, dst_port in edge_map.get(node.id, []):
            src_result = results.get(src_id, {})
            df = src_result.get(src_port)
            if df is not None:
                inputs[dst_port] = df

        t0 = time.monotonic()
        try:
            out = tool.execute(node.params, inputs, _log)
        except Exception as e:
            msg = f"[{node.kind}] Error: {e}"
            _log(msg, "error")
            node.result = None
            history.append({"node": node.id, "kind": node.kind, "status": "error",
                            "error": str(e), "elapsed_ms": 0})
            continue

        elapsed = (time.monotonic() - t0) * 1000

        # Normalise output
        if isinstance(out, pd.DataFrame):
            out = {tool.outs[0]: out} if tool.outs else {}
        node.result = out
        results[node.id] = out

        # Log counts
        for port, df in out.items():
            if isinstance(df, pd.DataFrame):
                _log(f"[{node.kind}] {port}: {len(df)} rows × {len(df.columns)} cols")

        history.append({"node": node.id, "kind": node.kind, "status": "ok",
                        "elapsed_ms": round(elapsed, 1)})

    return results
