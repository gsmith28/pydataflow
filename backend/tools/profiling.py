from __future__ import annotations
from typing import Any
import pandas as pd
import numpy as np
from tools.base import BaseTool, ExecutionContext


class FieldSummaryTool(BaseTool):
    tool_type = "field_summary"
    display_name = "Field Summary"
    category = "Data Quality / Profiling"
    description = "Produce field-level statistics and data quality indicators."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "fields": {"type": "multi_field_selector", "label": "Fields to profile (empty = all)"},
        "include_numeric_profile": {"type": "checkbox", "label": "Include numeric stats", "default": True},
        "include_string_profile": {"type": "checkbox", "label": "Include string stats", "default": True},
        "include_distinct_count": {"type": "checkbox", "label": "Include distinct count", "default": True},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        target_fields = config.get("fields") or list(df.columns)
        rows = []

        for i, col in enumerate(target_fields):
            if col not in df.columns:
                continue
            series = df[col]
            row: dict[str, Any] = {
                "field_name": col,
                "dtype": str(series.dtype),
                "position": i,
                "record_count": len(series),
                "null_count": int(series.isna().sum()),
                "null_pct": round(series.isna().mean() * 100, 2),
            }

            if config.get("include_distinct_count", True):
                row["distinct_count"] = int(series.nunique())

            if pd.api.types.is_numeric_dtype(series) and config.get("include_numeric_profile", True):
                non_null = series.dropna()
                row["min"] = float(non_null.min()) if len(non_null) else None
                row["max"] = float(non_null.max()) if len(non_null) else None
                row["mean"] = round(float(non_null.mean()), 4) if len(non_null) else None
                row["median"] = float(non_null.median()) if len(non_null) else None
                row["std"] = round(float(non_null.std()), 4) if len(non_null) else None

            if series.dtype == object and config.get("include_string_profile", True):
                lengths = series.dropna().astype(str).str.len()
                row["min_length"] = int(lengths.min()) if len(lengths) else None
                row["max_length"] = int(lengths.max()) if len(lengths) else None

            rows.append(row)

        return {"out": pd.DataFrame(rows)}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "field_summary")
        return (
            f"_profile_rows = []\n"
            f"for _col in {in_var}.columns:\n"
            f"    _s = {in_var}[_col]\n"
            f"    _profile_rows.append({{\n"
            f"        'field_name': _col, 'dtype': str(_s.dtype),\n"
            f"        'record_count': len(_s), 'null_count': int(_s.isna().sum()),\n"
            f"        'null_pct': round(_s.isna().mean() * 100, 2),\n"
            f"        'distinct_count': int(_s.nunique()),\n"
            f"    }})\n"
            f"{out_var} = pd.DataFrame(_profile_rows)"
        )


class FrequencyTableTool(BaseTool):
    tool_type = "frequency_table"
    display_name = "Frequency Table"
    category = "Data Quality / Profiling"
    description = "Count frequency of values in selected fields."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "field": {"type": "field_selector", "label": "Field to analyze"},
        "include_nulls": {"type": "checkbox", "label": "Include nulls", "default": True},
        "top_n": {"type": "number", "label": "Top N (0 = all)", "default": 0},
        "include_pct": {"type": "checkbox", "label": "Include percentage", "default": True},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        field = config.get("field")
        if not field or field not in df.columns:
            return {"out": pd.DataFrame()}

        dropna = not config.get("include_nulls", True)
        freq = df[field].value_counts(dropna=dropna).reset_index()
        freq.columns = [field, "count"]

        if config.get("include_pct", True):
            total = len(df) if not dropna else df[field].notna().sum()
            freq["pct"] = (freq["count"] / total * 100).round(2)

        top_n = int(config.get("top_n", 0))
        if top_n > 0:
            freq = freq.head(top_n)

        return {"out": freq}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "freq_table")
        field = config.get("field", "field")
        dropna = not config.get("include_nulls", True)
        top_n = config.get("top_n", 0)
        lines = [
            f'{out_var} = {in_var}["{field}"].value_counts(dropna={dropna}).reset_index()',
            f'{out_var}.columns = ["{field}", "count"]',
        ]
        if config.get("include_pct", True):
            lines.append(f'{out_var}["pct"] = ({out_var}["count"] / len({in_var}) * 100).round(2)')
        if top_n > 0:
            lines.append(f'{out_var} = {out_var}.head({top_n})')
        return "\n".join(lines)
