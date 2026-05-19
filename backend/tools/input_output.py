from __future__ import annotations
from typing import Any
import pandas as pd
from pathlib import Path
from tools.base import BaseTool, ExecutionContext, ToolError


class InputDataTool(BaseTool):
    tool_type = "input_data"
    display_name = "Input Data"
    category = "Input / Output"
    description = "Load data from CSV, Excel, or text files by local path."
    input_ports = []
    output_ports = ["out"]
    config_schema = {
        "source_type": {"type": "select", "label": "Source type", "options": ["csv", "excel", "text"], "default": "csv"},
        "path": {"type": "filepath", "label": "File path"},
        "path_mode": {"type": "select", "label": "Path mode", "options": ["absolute", "project_relative"], "default": "absolute"},
        "sheet_name": {"type": "text", "label": "Sheet name (Excel)", "default": ""},
        "delimiter": {"type": "text", "label": "Delimiter (CSV/text)", "default": ","},
        "encoding": {"type": "text", "label": "Encoding", "default": "utf-8"},
        "skip_rows": {"type": "number", "label": "Rows to skip", "default": 0},
        "preview_limit": {"type": "number", "label": "Preview row limit", "default": 1000},
    }

    def validate_config(self, config: dict[str, Any], input_schemas: dict) -> list[str]:
        errors = []
        if not config.get("path"):
            errors.append("File path is required.")
        return errors

    def _resolve_path(self, config: dict[str, Any], context: ExecutionContext) -> Path:
        path_str = config.get("path", "")
        if config.get("path_mode") == "project_relative":
            return context.project_dir / path_str
        return Path(path_str)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: ExecutionContext) -> dict[str, pd.DataFrame]:
        path = self._resolve_path(config, context)
        if not path.exists():
            raise ToolError(f"File not found: {path}")

        source_type = config.get("source_type", "csv")
        skip = int(config.get("skip_rows", 0))
        encoding = config.get("encoding", "utf-8")

        if source_type == "csv":
            delimiter = config.get("delimiter", ",")
            df = pd.read_csv(path, delimiter=delimiter, encoding=encoding, skiprows=skip)
        elif source_type == "excel":
            sheet = config.get("sheet_name") or 0
            df = pd.read_excel(path, sheet_name=sheet, skiprows=skip)
        elif source_type == "text":
            delimiter = config.get("delimiter", "\t")
            df = pd.read_csv(path, delimiter=delimiter, encoding=encoding, skiprows=skip)
        else:
            raise ToolError(f"Unknown source type: {source_type}")

        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        out = output_vars.get("out", "df")
        path = config.get("path", "")
        source_type = config.get("source_type", "csv")
        skip = config.get("skip_rows", 0)
        encoding = config.get("encoding", "utf-8")

        if source_type == "csv":
            delim = config.get("delimiter", ",")
            return f'{out} = pd.read_csv(r"{path}", delimiter="{delim}", encoding="{encoding}", skiprows={skip})'
        elif source_type == "excel":
            sheet = config.get("sheet_name") or 0
            sheet_repr = f'"{sheet}"' if isinstance(sheet, str) and sheet else sheet
            return f'{out} = pd.read_excel(r"{path}", sheet_name={sheet_repr}, skiprows={skip})'
        else:
            delim = config.get("delimiter", "\t")
            return f'{out} = pd.read_csv(r"{path}", delimiter="{delim}", encoding="{encoding}", skiprows={skip})'


class BrowsePreviewTool(BaseTool):
    tool_type = "browse_preview"
    display_name = "Browse / Preview"
    category = "Input / Output"
    description = "Inspect data without modifying it."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "preview_rows": {"type": "number", "label": "Preview rows", "default": 50},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        return {"out": df.copy()}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df")
        rows = config.get("preview_rows", 50)
        return f"# Browse/Preview: {rows} rows\n{out_var} = {in_var}.copy()\nprint({out_var}.head({rows}))"


class OutputDataTool(BaseTool):
    tool_type = "output_data"
    display_name = "Output Data"
    category = "Input / Output"
    description = "Write results to a local CSV, Excel, or Parquet file."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "destination_type": {"type": "select", "label": "Format", "options": ["csv", "excel", "parquet", "json"], "default": "csv"},
        "path": {"type": "filepath", "label": "Output file path"},
        "sheet_name": {"type": "text", "label": "Sheet name (Excel)", "default": "Sheet1"},
        "overwrite": {"type": "checkbox", "label": "Overwrite if exists", "default": True},
        "include_index": {"type": "checkbox", "label": "Include index", "default": False},
    }

    def validate_config(self, config: dict, input_schemas: dict) -> list[str]:
        if not config.get("path"):
            return ["Output file path is required."]
        return []

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        path = Path(config.get("path", "output.csv"))
        path.parent.mkdir(parents=True, exist_ok=True)
        dest = config.get("destination_type", "csv")
        index = config.get("include_index", False)

        if not config.get("overwrite", True) and path.exists():
            raise ToolError(f"Output file already exists and overwrite is disabled: {path}")

        if dest == "csv":
            df.to_csv(path, index=index)
        elif dest == "excel":
            df.to_excel(path, sheet_name=config.get("sheet_name", "Sheet1"), index=index)
        elif dest == "parquet":
            df.to_parquet(path, index=index)
        elif dest == "json":
            df.to_json(path, orient="records", indent=2)

        context.logger(f"Output written to {path} ({len(df)} rows)")
        return {"out": df.copy()}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        path = config.get("path", "output.csv")
        dest = config.get("destination_type", "csv")
        index = config.get("include_index", False)
        sheet = config.get("sheet_name", "Sheet1")
        if dest == "csv":
            return f'{in_var}.to_csv(r"{path}", index={index})'
        elif dest == "excel":
            return f'{in_var}.to_excel(r"{path}", sheet_name="{sheet}", index={index})'
        elif dest == "parquet":
            return f'{in_var}.to_parquet(r"{path}", index={index})'
        else:
            return f'{in_var}.to_json(r"{path}", orient="records", indent=2)'


class CountRecordsTool(BaseTool):
    tool_type = "count_records"
    display_name = "Count Records"
    category = "Input / Output"
    description = "Output a one-row DataFrame containing the record count."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "output_field": {"type": "text", "label": "Output field name", "default": "record_count"},
        "label": {"type": "text", "label": "Label field value", "default": ""},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        field = config.get("output_field", "record_count")
        label = config.get("label", "")
        row: dict = {field: len(df)}
        if label:
            row["label"] = label
        return {"out": pd.DataFrame([row])}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "count_df")
        field = config.get("output_field", "record_count")
        return f'{out_var} = pd.DataFrame({{"{field}": [len({in_var})]}})'
