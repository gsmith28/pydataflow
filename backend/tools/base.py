from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import pandas as pd


@dataclass
class ExecutionContext:
    run_id: str
    project_dir: Path
    temp_dir: Path
    logger: Any
    preview_limit: int = 100
    parameters: dict[str, Any] = field(default_factory=dict)


class ToolError(Exception):
    pass


class BaseTool(ABC):
    tool_type: str = ""
    display_name: str = ""
    category: str = ""
    description: str = ""
    input_ports: list[str] = []
    output_ports: list[str] = ["out"]
    config_schema: dict[str, Any] = {}

    def validate_config(self, config: dict[str, Any], input_schemas: dict[str, Any]) -> list[str]:
        """Return list of validation error messages."""
        return []

    @abstractmethod
    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, pd.DataFrame]:
        ...

    def infer_output_schema(
        self, input_schemas: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        return {}

    @abstractmethod
    def generate_python(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        ...

    def tool_info(self) -> dict[str, Any]:
        return {
            "tool_type": self.tool_type,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "input_ports": self.input_ports,
            "output_ports": self.output_ports,
            "config_schema": self.config_schema,
        }
