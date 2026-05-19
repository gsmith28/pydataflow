from __future__ import annotations
from typing import Any
import pandas as pd
from tools.base import BaseTool, ExecutionContext, ToolError


class SummarizeTool(BaseTool):
    tool_type = "summarize"
    display_name = "Summarize"
    category = "Transform / Summarize"
    description = "Group and aggregate records."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "group_fields": {"type": "multi_field_selector", "label": "Group by fields"},
        "aggregations": {
            "type": "aggregation_list",
            "label": "Aggregations",
            "description": "List of {field, function, output_field} objects",
        },
    }

    _AGG_MAP = {
        "count": "count",
        "count_distinct": pd.Series.nunique,
        "sum": "sum",
        "min": "min",
        "max": "max",
        "mean": "mean",
        "average": "mean",
        "median": "median",
        "std": "std",
        "first": "first",
        "last": "last",
        "concat": lambda s: ", ".join(s.dropna().astype(str)),
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        group_fields = [f for f in config.get("group_fields", []) if f in df.columns]
        aggregations = config.get("aggregations", [])

        if not aggregations:
            if group_fields:
                return {"out": df.groupby(group_fields, dropna=False).size().reset_index(name="count")}
            return {"out": df.copy()}

        agg_dict: dict[str, list] = {}
        rename_map: dict[tuple, str] = {}

        for agg in aggregations:
            src_field = agg.get("field")
            func_name = agg.get("function", "count")
            out_field = agg.get("output_field") or f"{src_field}_{func_name}"
            if src_field not in df.columns:
                continue
            func = self._AGG_MAP.get(func_name, "count")
            if src_field not in agg_dict:
                agg_dict[src_field] = []
            agg_dict[src_field].append(func)
            rename_map[(src_field, func if isinstance(func, str) else func.__name__)] = out_field

        if group_fields:
            grouped = df.groupby(group_fields, dropna=False).agg(agg_dict).reset_index()
        else:
            grouped = df.agg(agg_dict).to_frame().T

        grouped.columns = [
            "_".join(str(c) for c in col) if isinstance(col, tuple) else str(col)
            for col in grouped.columns
        ]
        return {"out": grouped}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_summary")
        groups = config.get("group_fields", [])
        aggs = config.get("aggregations", [])
        agg_repr = {a.get("field"): a.get("function", "count") for a in aggs}
        if groups:
            return (
                f"{out_var} = {in_var}.groupby({groups}, dropna=False)"
                f".agg({repr(agg_repr)}).reset_index()"
            )
        return f"{out_var} = {in_var}.agg({repr(agg_repr)}).to_frame().T"


class CrossTabPivotTool(BaseTool):
    tool_type = "crosstab_pivot"
    display_name = "Cross Tab / Pivot"
    category = "Transform / Summarize"
    description = "Pivot data from long format into a summary table."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "index_fields": {"type": "multi_field_selector", "label": "Row / group fields"},
        "column_field": {"type": "field_selector", "label": "Column header field"},
        "value_field": {"type": "field_selector", "label": "Values field"},
        "aggfunc": {"type": "select", "label": "Aggregation", "options": ["sum", "count", "mean", "min", "max"], "default": "sum"},
        "fill_value": {"type": "text", "label": "Fill value (empty = NaN)", "default": ""},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        index_fields = config.get("index_fields", [])
        col_field = config.get("column_field")
        val_field = config.get("value_field")
        aggfunc = config.get("aggfunc", "sum")
        fill = config.get("fill_value", "")
        fill_val = None if fill == "" else fill

        if not col_field or not val_field:
            return {"out": df.copy()}

        out = pd.pivot_table(
            df,
            index=index_fields or None,
            columns=col_field,
            values=val_field,
            aggfunc=aggfunc,
            fill_value=fill_val,
        ).reset_index()
        out.columns = [str(c) for c in out.columns]
        return {"out": out}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_pivot")
        idx = config.get("index_fields", [])
        col = config.get("column_field", "column")
        val = config.get("value_field", "value")
        agg = config.get("aggfunc", "sum")
        return (
            f"{out_var} = pd.pivot_table({in_var}, index={idx}, columns=\"{col}\", "
            f"values=\"{val}\", aggfunc=\"{agg}\").reset_index()\n"
            f"{out_var}.columns = [str(c) for c in {out_var}.columns]"
        )


class TransposeUnpivotTool(BaseTool):
    tool_type = "transpose_unpivot"
    display_name = "Transpose / Unpivot"
    category = "Transform / Summarize"
    description = "Convert wide data into long format."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "id_columns": {"type": "multi_field_selector", "label": "ID / key columns (keep fixed)"},
        "value_columns": {"type": "multi_field_selector", "label": "Value columns to unpivot (empty = all non-ID)"},
        "name_field": {"type": "text", "label": "Variable name field", "default": "variable"},
        "value_field": {"type": "text", "label": "Value field", "default": "value"},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        id_cols = config.get("id_columns", [])
        val_cols = config.get("value_columns") or [c for c in df.columns if c not in id_cols]
        name_field = config.get("name_field", "variable")
        value_field = config.get("value_field", "value")
        out = pd.melt(df, id_vars=id_cols, value_vars=val_cols, var_name=name_field, value_name=value_field)
        return {"out": out}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_long")
        id_cols = config.get("id_columns", [])
        val_cols = config.get("value_columns", [])
        name_f = config.get("name_field", "variable")
        val_f = config.get("value_field", "value")
        return (
            f"{out_var} = pd.melt({in_var}, id_vars={id_cols}, value_vars={val_cols}, "
            f"var_name=\"{name_f}\", value_name=\"{val_f}\")"
        )
