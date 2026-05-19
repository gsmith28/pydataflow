from __future__ import annotations
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
import pandas as pd

from engine.graph import topological_sort, get_upstream_nodes, GraphValidationError
from models.workflow import Workflow, WorkflowRunResult, NodeResult, DataSchema, SchemaField
from tools.registry import get_tool_or_raise
from tools.base import ExecutionContext, ToolError


@dataclass
class RunLog:
    messages: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, msg: str, level: str = "info", node_id: str = "") -> None:
        self.messages.append({"level": level, "message": msg, "node_id": node_id})


def _infer_schema(df: pd.DataFrame, source_node_id: str = "") -> DataSchema:
    fields = []
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            field_type = "integer"
        elif pd.api.types.is_float_dtype(dtype):
            field_type = "float"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            field_type = "datetime"
        elif pd.api.types.is_bool_dtype(dtype):
            field_type = "boolean"
        else:
            field_type = "string"

        fields.append(SchemaField(
            name=col,
            type=field_type,
            nullable=bool(df[col].isna().any()),
            source_node_id=source_node_id,
        ))
    return DataSchema(fields=fields, record_count=len(df), profile_available=True)


def _df_to_preview(df: pd.DataFrame, limit: int = 50) -> tuple[list[str], list[dict]]:
    preview = df.head(limit).copy()
    for col in preview.select_dtypes(include=["datetime64"]).columns:
        preview[col] = preview[col].astype(str)
    cols = list(preview.columns)
    rows = preview.fillna("").to_dict(orient="records")
    return cols, rows


def execute_workflow(
    workflow: Workflow,
    project_dir: Path,
    temp_dir: Path,
    preview_limit: int = 50,
    parameters: dict[str, Any] | None = None,
    node_id_filter: Optional[str] = None,
    on_node_done: Optional[Callable[[str, dict], None]] = None,
) -> WorkflowRunResult:
    run_id = str(uuid.uuid4())
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log = RunLog()
    errors: list[str] = []
    warnings: list[str] = []
    output_files: list[str] = []
    node_results: dict[str, list[NodeResult]] = {}

    try:
        if node_id_filter:
            ordered_nodes = get_upstream_nodes(workflow, node_id_filter)
        else:
            ordered_nodes = topological_sort(workflow)
    except GraphValidationError as e:
        return WorkflowRunResult(
            run_id=run_id, workflow_id=workflow.workflow_id,
            status="failed", started_at=started_at,
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            errors=[str(e)],
        )

    edge_map: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for edge in workflow.edges:
        edge_map[edge.source_node_id].append(
            (edge.source_port, edge.target_node_id, edge.target_port)
        )

    node_outputs: dict[str, dict[str, pd.DataFrame]] = {}

    ctx = ExecutionContext(
        run_id=run_id,
        project_dir=project_dir,
        temp_dir=temp_dir,
        logger=log,
        preview_limit=preview_limit,
        parameters=parameters or {},
    )

    active_nodes = {n.node_id for n in ordered_nodes}

    for node in ordered_nodes:
        if node.disabled:
            log(f"Skipping disabled node: {node.display_name}", node_id=node.node_id)
            continue

        try:
            tool = get_tool_or_raise(node.tool_type)
        except KeyError as e:
            errors.append(str(e))
            continue

        inputs: dict[str, pd.DataFrame] = {}
        for edge in workflow.edges:
            if edge.target_node_id == node.node_id and edge.source_node_id in node_outputs:
                src_outputs = node_outputs[edge.source_node_id]
                if edge.source_port in src_outputs:
                    inputs[edge.target_port] = src_outputs[edge.source_port]

        validation_errors = tool.validate_config(node.config, {})
        if validation_errors:
            errors.extend([f"[{node.display_name}] {e}" for e in validation_errors])
            node_results[node.node_id] = [
                NodeResult(node_id=node.node_id, port="error", errors=validation_errors)
            ]
            continue

        t_start = time.monotonic()
        try:
            def node_logger(msg: str, level: str = "info") -> None:
                log(msg, level=level, node_id=node.node_id)

            ctx.logger = node_logger
            outputs = tool.execute(inputs, node.config, ctx)
        except ToolError as e:
            err_msg = f"[{node.display_name}] {e}"
            errors.append(err_msg)
            log(err_msg, level="error", node_id=node.node_id)
            node_results[node.node_id] = [
                NodeResult(node_id=node.node_id, port="error", errors=[str(e)])
            ]
            continue
        except Exception as e:
            err_msg = f"[{node.display_name}] Unexpected error: {e}"
            errors.append(err_msg)
            log(err_msg, level="error", node_id=node.node_id)
            node_results[node.node_id] = [
                NodeResult(node_id=node.node_id, port="error", errors=[err_msg])
            ]
            continue

        elapsed_ms = (time.monotonic() - t_start) * 1000
        node_outputs[node.node_id] = outputs

        port_results: list[NodeResult] = []
        for port, df in outputs.items():
            cols, rows = _df_to_preview(df, limit=preview_limit)
            nr = NodeResult(
                node_id=node.node_id,
                port=port,
                record_count=len(df),
                column_count=len(df.columns),
                execution_time_ms=round(elapsed_ms, 1),
                output_schema=_infer_schema(df, node.node_id),
                preview_columns=cols,
                preview_rows=rows,
            )
            port_results.append(nr)

        node_results[node.node_id] = port_results

        if on_node_done:
            on_node_done(node.node_id, {
                "port_results": [r.model_dump() for r in port_results],
            })

        ctx.logger = log

    status = "success" if not errors else "partial" if node_results else "failed"
    return WorkflowRunResult(
        run_id=run_id,
        workflow_id=workflow.workflow_id,
        status=status,
        started_at=started_at,
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        node_results=node_results,
        errors=errors,
        warnings=[m["message"] for m in log.messages if m["level"] == "warning"],
        output_files=output_files,
    )
