from __future__ import annotations
from collections import defaultdict, deque
from typing import Optional
from models.workflow import Workflow, WorkflowNode, WorkflowEdge


class GraphValidationError(Exception):
    pass


def build_adjacency(workflow: Workflow) -> tuple[dict, dict]:
    """Returns (successors, predecessors) maps: node_id -> list of (node_id, port info)."""
    successors: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    predecessors: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    for edge in workflow.edges:
        successors[edge.source_node_id].append(
            (edge.target_node_id, edge.source_port, edge.target_port, edge.edge_id)
        )
        predecessors[edge.target_node_id].append(
            (edge.source_node_id, edge.source_port, edge.target_port, edge.edge_id)
        )
    return dict(successors), dict(predecessors)


def topological_sort(workflow: Workflow) -> list[WorkflowNode]:
    """Kahn's algorithm. Raises GraphValidationError if a cycle is detected."""
    node_map = {n.node_id: n for n in workflow.nodes}
    in_degree: dict[str, int] = {n.node_id: 0 for n in workflow.nodes}
    successors: dict[str, list[str]] = defaultdict(list)

    for edge in workflow.edges:
        if edge.source_node_id not in node_map:
            raise GraphValidationError(
                f"Edge references unknown source node: {edge.source_node_id}"
            )
        if edge.target_node_id not in node_map:
            raise GraphValidationError(
                f"Edge references unknown target node: {edge.target_node_id}"
            )
        in_degree[edge.target_node_id] += 1
        successors[edge.source_node_id].append(edge.target_node_id)

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    result: list[WorkflowNode] = []

    while queue:
        nid = queue.popleft()
        result.append(node_map[nid])
        for succ in successors[nid]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    if len(result) != len(workflow.nodes):
        raise GraphValidationError(
            "Workflow contains a cycle — cycles are not permitted."
        )

    return result


def get_upstream_nodes(workflow: Workflow, node_id: str) -> list[WorkflowNode]:
    """Return all nodes that must execute before node_id, in topological order."""
    node_map = {n.node_id: n for n in workflow.nodes}
    predecessors: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        predecessors[edge.target_node_id].append(edge.source_node_id)

    visited: set[str] = set()
    stack = [node_id]
    while stack:
        nid = stack.pop()
        if nid in visited:
            continue
        visited.add(nid)
        for pred in predecessors.get(nid, []):
            stack.append(pred)

    sub_nodes = [n for n in workflow.nodes if n.node_id in visited]
    sub_edges = [
        e for e in workflow.edges
        if e.source_node_id in visited and e.target_node_id in visited
    ]

    from models.workflow import Workflow as WF
    sub_workflow = WF(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        nodes=sub_nodes,
        edges=sub_edges,
    )
    return topological_sort(sub_workflow)


def validate_workflow_structure(workflow: Workflow) -> list[str]:
    """Return a list of validation messages (non-fatal warnings)."""
    messages: list[str] = []
    node_ids = {n.node_id for n in workflow.nodes}

    for edge in workflow.edges:
        if edge.source_node_id not in node_ids:
            messages.append(f"Edge {edge.edge_id} references missing node {edge.source_node_id}")
        if edge.target_node_id not in node_ids:
            messages.append(f"Edge {edge.edge_id} references missing node {edge.target_node_id}")

    try:
        topological_sort(workflow)
    except GraphValidationError as e:
        messages.append(str(e))

    return messages
