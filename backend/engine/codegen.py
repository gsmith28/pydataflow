from __future__ import annotations
import re
from datetime import datetime
from models.workflow import Workflow
from tools.registry import get_tool


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    reserved = {"and", "or", "not", "if", "else", "for", "while", "in", "is", "import", "from", "return", "class", "def", "lambda", "pass", "break", "continue", "with", "as", "try", "except", "finally", "raise", "del", "global", "nonlocal", "yield", "assert"}
    if slug in reserved or (slug and slug[0].isdigit()):
        slug = f"df_{slug}"
    return slug or "df"


def _unique_varname(base: str, used: set[str]) -> str:
    name = base
    counter = 2
    while name in used:
        name = f"{base}_{counter}"
        counter += 1
    used.add(name)
    return name


def generate_python(workflow: Workflow, project_dir: str = ".") -> str:
    from engine.graph import topological_sort
    try:
        ordered_nodes = topological_sort(workflow)
    except Exception as e:
        return f"# ERROR: Cannot generate code — {e}"

    edge_map: dict[str, list[tuple[str, str, str, str]]] = {}
    for edge in workflow.edges:
        if edge.source_node_id not in edge_map:
            edge_map[edge.source_node_id] = []
        edge_map[edge.source_node_id].append(
            (edge.source_port, edge.target_node_id, edge.target_port, edge.edge_id)
        )

    inbound: dict[str, list[tuple[str, str, str]]] = {}
    for edge in workflow.edges:
        if edge.target_node_id not in inbound:
            inbound[edge.target_node_id] = []
        inbound[edge.target_node_id].append(
            (edge.source_node_id, edge.source_port, edge.target_port)
        )

    used_vars: set[str] = set()
    node_output_vars: dict[str, dict[str, str]] = {}

    path_vars: list[str] = []
    node_sections: list[str] = []
    imports: set[str] = {"import pandas as pd", "import os"}

    for node in ordered_nodes:
        if node.disabled:
            continue

        tool = get_tool(node.tool_type)
        label = node.display_name or node.tool_type
        slug = _slugify(label)

        tool_input_ports = tool.input_ports if tool else ["in"]
        tool_output_ports = tool.output_ports if tool else ["out"]

        input_vars: dict[str, str] = {}
        for src_node_id, src_port, tgt_port in inbound.get(node.node_id, []):
            if src_node_id in node_output_vars and src_port in node_output_vars[src_node_id]:
                input_vars[tgt_port] = node_output_vars[src_node_id][src_port]

        output_vars: dict[str, str] = {}
        for port in tool_output_ports:
            if len(tool_output_ports) == 1:
                base = slug
            else:
                base = f"{slug}_{port}"
            output_vars[port] = _unique_varname(base, used_vars)
        node_output_vars[node.node_id] = output_vars

        if tool:
            code = tool.generate_python(input_vars, output_vars, node.config)
        else:
            code = f"# Unknown tool: {node.tool_type}"

        section_lines = [
            f"# {'=' * 60}",
            f"# Node: {label}",
        ]
        if node.annotation:
            section_lines.append(f"# {node.annotation}")
        section_lines.append(f"# {'=' * 60}")
        section_lines.append(code)

        node_sections.append("\n".join(section_lines))

        if node.tool_type == "input_data":
            cfg = node.config
            path = cfg.get("path", "")
            if path:
                var_name = _unique_varname(f"{slug.upper()}_PATH", set())
                path_vars.append(f'{var_name} = r"{path}"')

    header = f'''"""
Workflow: {workflow.name}
{f"Description: {workflow.description}" if workflow.description else ""}
Purpose: {workflow.metadata.purpose or "Audit analytics workflow"}
Author: {workflow.metadata.author or ""}
Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
"""'''

    sections = [header, ""]
    sections.append("\n".join(sorted(imports)))
    sections.append("")

    if path_vars:
        sections.append("# " + "-" * 40)
        sections.append("# File paths")
        sections.append("# " + "-" * 40)
        sections.extend(path_vars)
        sections.append("")

    sections.extend(node_sections)
    return "\n\n".join(sections)
