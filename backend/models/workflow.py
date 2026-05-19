from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class Port(BaseModel):
    name: str
    label: str = ""
    type: str = "dataframe"


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class WorkflowNode(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_type: str
    display_name: str = ""
    position: Position = Field(default_factory=Position)
    config: dict[str, Any] = Field(default_factory=dict)
    input_ports: list[str] = Field(default_factory=list)
    output_ports: list[str] = Field(default_factory=list)
    annotation: str = ""
    disabled: bool = False
    cache_enabled: bool = True
    created_from_custom_tool_id: Optional[str] = None
    created_from_custom_tool_version: Optional[str] = None
    created_from_custom_tool_hash: Optional[str] = None


class WorkflowEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str
    source_port: str = "out"
    target_node_id: str
    target_port: str = "in"


class WorkflowMetadata(BaseModel):
    author: str = ""
    purpose: str = ""
    reviewer: str = ""
    review_date: Optional[str] = None
    change_notes: str = ""


class Workflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Workflow"
    description: str = ""
    version: str = "1.0.0"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: WorkflowMetadata = Field(default_factory=WorkflowMetadata)


class SchemaField(BaseModel):
    name: str
    type: str
    nullable: bool = True
    description: str = ""
    source_node_id: Optional[str] = None


class DataSchema(BaseModel):
    fields: list[SchemaField] = Field(default_factory=list)
    record_count: Optional[int] = None
    profile_available: bool = False


class NodeResult(BaseModel):
    node_id: str
    port: str
    record_count: Optional[int] = None
    column_count: Optional[int] = None
    execution_time_ms: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    schema: Optional[DataSchema] = None
    preview_rows: Optional[list[dict[str, Any]]] = None
    preview_columns: Optional[list[str]] = None


class WorkflowRunResult(BaseModel):
    run_id: str
    workflow_id: str
    status: str  # success | failed | partial
    started_at: str
    finished_at: str
    node_results: dict[str, list[NodeResult]] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    preview_limit: int = 100
    parameters: dict[str, Any] = Field(default_factory=dict)
    stop_on_error: bool = True


class NodeRunRequest(RunRequest):
    node_id: str
