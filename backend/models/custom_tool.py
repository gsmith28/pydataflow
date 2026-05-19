from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class CustomToolPort(BaseModel):
    name: str
    label: str = ""
    type: str = "dataframe"


class CustomToolTest(BaseModel):
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    expected_output_row_count: Optional[int] = None


class CustomTool(BaseModel):
    tool_id: str = Field(default_factory=lambda: f"custom.{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    category: str = "Custom Tools"
    icon: str = "puzzle"
    color: str = "#6366f1"
    version: str = "1.0.0"
    author: str = ""
    trusted: bool = True
    input_ports: list[CustomToolPort] = Field(default_factory=lambda: [CustomToolPort(name="in")])
    output_ports: list[CustomToolPort] = Field(default_factory=lambda: [CustomToolPort(name="out")])
    config_schema: dict[str, Any] = Field(default_factory=dict)
    python_code: str = ""
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    tests: list[CustomToolTest] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    change_notes: str = ""
    code_hash: str = ""


class CustomToolCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "Custom Tools"
    input_ports: list[CustomToolPort] = Field(default_factory=lambda: [CustomToolPort(name="in")])
    output_ports: list[CustomToolPort] = Field(default_factory=lambda: [CustomToolPort(name="out")])
    config_schema: dict[str, Any] = Field(default_factory=dict)
    python_code: str = ""
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    tests: list[CustomToolTest] = Field(default_factory=list)
    trusted: bool = True


class CustomToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    input_ports: Optional[list[CustomToolPort]] = None
    output_ports: Optional[list[CustomToolPort]] = None
    config_schema: Optional[dict[str, Any]] = None
    python_code: Optional[str] = None
    dependencies: Optional[dict[str, list[str]]] = None
    tests: Optional[list[CustomToolTest]] = None
    trusted: Optional[bool] = None
    version: Optional[str] = None
    change_notes: Optional[str] = None


class CustomToolTestRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    input_data: Optional[dict[str, list[dict[str, Any]]]] = None
