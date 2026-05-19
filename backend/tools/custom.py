from __future__ import annotations
import hashlib
import textwrap
import traceback
from typing import Any
import pandas as pd
from tools.base import BaseTool, ExecutionContext, ToolError


def _compute_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:16]


def run_custom_tool_code(
    python_code: str,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: ExecutionContext,
) -> dict[str, pd.DataFrame]:
    namespace: dict[str, Any] = {"pd": pd, "__builtins__": __builtins__}
    try:
        exec(textwrap.dedent(python_code), namespace)  # noqa: S102
    except SyntaxError as e:
        raise ToolError(f"Custom tool syntax error: {e}")

    execute_fn = namespace.get("execute")
    if not callable(execute_fn):
        raise ToolError("Custom tool code must define an 'execute(inputs, config, context)' function.")

    try:
        result = execute_fn(inputs, config, context)
    except Exception as e:
        raise ToolError(f"Custom tool runtime error: {e}\n{traceback.format_exc()}")

    if not isinstance(result, dict):
        raise ToolError("Custom tool 'execute' must return a dict mapping port names to DataFrames.")

    return result


class CustomToolRunner(BaseTool):
    """Dynamically represents a user-defined custom tool at runtime."""

    def __init__(self, tool_def: dict[str, Any]) -> None:
        self.tool_type = tool_def["tool_id"]
        self.display_name = tool_def.get("name", "Custom Tool")
        self.category = tool_def.get("category", "Custom Tools")
        self.description = tool_def.get("description", "")
        self.input_ports = [p["name"] for p in tool_def.get("input_ports", [{"name": "in"}])]
        self.output_ports = [p["name"] for p in tool_def.get("output_ports", [{"name": "out"}])]
        self.config_schema = tool_def.get("config_schema", {})
        self._python_code = tool_def.get("python_code", "")
        self._tool_def = tool_def

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        if not self._python_code.strip():
            raise ToolError(f"Custom tool '{self.display_name}' has no Python code.")
        return run_custom_tool_code(self._python_code, inputs, config, context)

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        tool_id = self._tool_def.get("tool_id", "custom_tool")
        version = self._tool_def.get("version", "1.0.0")
        code_hash = _compute_hash(self._python_code)
        in_repr = repr(input_vars)
        out_repr = repr(output_vars)
        config_repr = repr(config)
        fn_name = tool_id.replace(".", "_").replace("-", "_")

        code_block = textwrap.indent(textwrap.dedent(self._python_code), "    ")
        return (
            f"# Custom tool: {self.display_name}\n"
            f"# Tool ID: {tool_id}  Version: {version}  Hash: {code_hash}\n"
            f"def {fn_name}(inputs, config, context=None):\n"
            f"{code_block}\n\n"
            f"_custom_result = {fn_name}({in_repr}, {config_repr})\n"
            + "\n".join(f'{v} = _custom_result["{k}"]' for k, v in out_repr.items() if isinstance(out_repr, dict))
        )
