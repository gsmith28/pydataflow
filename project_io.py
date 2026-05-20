from __future__ import annotations
import json
from pathlib import Path
from engine import Node, Edge

FORMAT_VERSION = 3


def save_project(path: str, nodes: list[Node], edges: list[Edge]) -> None:
    data = {
        "version": FORMAT_VERSION,
        "nodes": [
            {
                "id": n.id,
                "kind": n.kind,
                "x": n.x,
                "y": n.y,
                "params": n.params,
                "disabled": n.disabled,
                "annotation": n.annotation,
            }
            for n in nodes
        ],
        "edges": [
            {
                "id": e.id,
                "src_node": e.src_node,
                "src_port": e.src_port,
                "dst_node": e.dst_node,
                "dst_port": e.dst_port,
            }
            for e in edges
        ],
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_project(path: str) -> tuple[list[Node], list[Edge]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    nodes = [
        Node(
            kind=n["kind"],
            x=float(n.get("x", 100)),
            y=float(n.get("y", 100)),
            node_id=n["id"],
            params=n.get("params", {}),
            disabled=bool(n.get("disabled", False)),
            annotation=str(n.get("annotation", "")),
        )
        for n in raw.get("nodes", [])
    ]
    edges = [
        Edge(
            src_node=e["src_node"],
            src_port=e["src_port"],
            dst_node=e["dst_node"],
            dst_port=e["dst_port"],
            edge_id=e.get("id"),
        )
        for e in raw.get("edges", [])
    ]
    return nodes, edges
