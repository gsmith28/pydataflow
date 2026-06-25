"""Transform / Summarize tool nodes: Summarize, GroupBy, Pivot, Unpivot."""

from __future__ import annotations

from tkinter import ttk

import pandas as pd

from nodes.base import BaseTool


class Summarize(BaseTool):
    node_type = "summarize"
    display_name = "Summarize"
    color = "#a06020"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_combobox(
            parent, "Scope", "scope", ["all", "numeric", "specific"], params, on_change, 0
        )
        self.add_column_multiselect(
            parent, "Specific cols", "columns", params, on_change, 1, columns or []
        )
        self.add_checkbox(parent, "Include percentiles", "percentiles", params, on_change, 2)
        self.add_checkbox(parent, "Transpose result", "transpose", params, on_change, 3)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        scope = params.get("scope", "all")
        pcts = [0.25, 0.5, 0.75] if params.get("percentiles") else None
        if scope == "numeric":
            result = df.describe(include="number", percentiles=pcts)
        elif scope == "specific":
            cols = params.get("columns", [])
            if isinstance(cols, str):
                cols = [c.strip() for c in cols.split(",") if c.strip()]
            result = df[cols].describe(percentiles=pcts) if cols else df.describe(percentiles=pcts)
        else:
            result = df.describe(include="all", percentiles=pcts)
        if params.get("transpose"):
            result = result.T
        result = result.reset_index()
        log(f"Summarize: {len(result)} stats rows")
        return {"data": result}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        scope = params.get("scope", "all")
        t = ".T" if params.get("transpose") else ""
        if scope == "numeric":
            return [f"{output_var} = {iv}.describe(include='number'){t}.reset_index()"]
        elif scope == "specific":
            cols = params.get("columns", [])
            return [f"{output_var} = {iv}[{cols!r}].describe(){t}.reset_index()"]
        return [f"{output_var} = {iv}.describe(include='all'){t}.reset_index()"]

    def subtitle(self, params):
        return params.get("scope", "all")


class GroupBy(BaseTool):
    node_type = "group_by"
    display_name = "Group By"
    color = "#a06020"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_column_multiselect(
            parent, "Group columns", "group_cols", params, on_change, 0, columns or []
        )
        agg_fields = [
            {"key": "column", "type": "combobox", "values": columns or [], "width": 12},
            {
                "key": "func",
                "type": "combobox",
                "values": ["sum", "mean", "count", "min", "max", "std", "median", "first", "last"],
                "width": 8,
            },
            {"key": "alias", "type": "entry", "width": 10},
        ]
        ttk.Label(parent, text="Aggregations (col / func / alias):").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0)
        )
        self.add_dynamic_rows(
            parent,
            "aggs",
            params,
            on_change,
            agg_fields,
            default_row={"column": "", "func": "sum", "alias": ""},
        )

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        group_cols = params.get("group_cols", [])
        if isinstance(group_cols, str):
            group_cols = [c.strip() for c in group_cols.split(",") if c.strip()]
        if not group_cols:
            raise ValueError("No group columns specified")
        aggs = params.get("aggs", [])
        if not aggs:
            result = df.groupby(group_cols).size().reset_index(name="count")
        else:
            agg_dict: dict = {}
            aliases: dict = {}
            for a in aggs:
                col = a.get("column")
                func = a.get("func", "sum")
                alias = a.get("alias") or f"{col}_{func}"
                if col and col in df.columns:
                    agg_dict.setdefault(col, [])
                    agg_dict[col].append(func)
                    aliases[(col, func)] = alias
            if not agg_dict:
                result = df.groupby(group_cols).size().reset_index(name="count")
            else:
                result = df.groupby(group_cols).agg(agg_dict).reset_index()
                result.columns = [
                    "_".join(c).rstrip("_") if isinstance(c, tuple) else c for c in result.columns
                ]
        log(f"Group By: {len(result)} groups")
        return {"data": result}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        group_cols = params.get("group_cols", [])
        if isinstance(group_cols, str):
            group_cols = [c.strip() for c in group_cols.split(",") if c.strip()]
        aggs = params.get("aggs", [])
        if not aggs:
            return [f"{output_var} = {iv}.groupby({group_cols!r}).size().reset_index(name='count')"]
        agg_dict: dict = {}
        for a in aggs:
            col = a.get("column")
            func = a.get("func", "sum")
            if col:
                agg_dict.setdefault(col, [])
                agg_dict[col].append(func)
        lines = [
            f"{output_var} = {iv}.groupby({group_cols!r}).agg({agg_dict!r}).reset_index()",
            f"{output_var}.columns = ['_'.join(c).rstrip('_') if isinstance(c, tuple) else c for c in {output_var}.columns]",
        ]
        return lines

    def subtitle(self, params):
        group_cols = params.get("group_cols", [])
        if isinstance(group_cols, list) and group_cols:
            return ", ".join(group_cols[:2])
        return "not configured"


class Pivot(BaseTool):
    node_type = "pivot"
    display_name = "Pivot"
    color = "#a06020"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_column_dropdown(
            parent, "Index field", "index_col", params, on_change, 0, columns or []
        )
        self.add_column_dropdown(
            parent, "Columns field", "columns_col", params, on_change, 1, columns or []
        )
        self.add_column_dropdown(
            parent, "Values field", "values_col", params, on_change, 2, columns or []
        )
        self.add_combobox(
            parent,
            "Aggregation",
            "aggfunc",
            ["mean", "sum", "count", "min", "max", "first"],
            params,
            on_change,
            3,
        )

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        idx = params.get("index_col")
        cols = params.get("columns_col")
        vals = params.get("values_col")
        aggfunc = params.get("aggfunc", "mean")
        if not all([idx, cols, vals]):
            raise ValueError("Index, columns, and values fields are required")
        result = pd.pivot_table(
            df, index=idx, columns=cols, values=vals, aggfunc=aggfunc
        ).reset_index()
        result.columns = [str(c) for c in result.columns]
        log(f"Pivot: {len(result)} rows × {len(result.columns)} cols")
        return {"data": result}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        idx = params.get("index_col", "")
        cols = params.get("columns_col", "")
        vals = params.get("values_col", "")
        aggfunc = params.get("aggfunc", "mean")
        lines = [
            f'{output_var} = pd.pivot_table({iv}, index="{idx}", columns="{cols}", values="{vals}", aggfunc="{aggfunc}").reset_index()',
            f"{output_var}.columns = [str(c) for c in {output_var}.columns]",
        ]
        return lines

    def subtitle(self, params):
        idx = params.get("index_col", "")
        return f"by {idx}" if idx else "not configured"


class Unpivot(BaseTool):
    node_type = "unpivot"
    display_name = "Unpivot"
    color = "#a06020"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_column_multiselect(
            parent, "ID columns", "id_cols", params, on_change, 0, columns or []
        )
        self.add_column_multiselect(
            parent, "Value columns", "value_cols", params, on_change, 1, columns or []
        )
        self.add_entry(parent, "Variable col name", "var_name", params, on_change, 2)
        self.add_entry(parent, "Value col name", "value_name", params, on_change, 3)
        params.setdefault("var_name", "variable")
        params.setdefault("value_name", "value")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        id_cols = params.get("id_cols", [])
        if isinstance(id_cols, str):
            id_cols = [c.strip() for c in id_cols.split(",") if c.strip()]
        val_cols = params.get("value_cols", [])
        if isinstance(val_cols, str):
            val_cols = [c.strip() for c in val_cols.split(",") if c.strip()]
        var_name = params.get("var_name") or "variable"
        value_name = params.get("value_name") or "value"
        result = pd.melt(
            df,
            id_vars=id_cols or None,
            value_vars=val_cols or None,
            var_name=var_name,
            value_name=value_name,
        )
        log(f"Unpivot: {len(result)} rows")
        return {"data": result}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        id_cols = params.get("id_cols", [])
        val_cols = params.get("value_cols", [])
        var_name = params.get("var_name") or "variable"
        value_name = params.get("value_name") or "value"
        return [
            f"{output_var} = pd.melt({iv}, id_vars={id_cols!r}, value_vars={val_cols!r}, "
            f'var_name="{var_name}", value_name="{value_name}")'
        ]

    def subtitle(self, params):
        var_name = params.get("var_name") or "variable"
        return f"→ {var_name}"
