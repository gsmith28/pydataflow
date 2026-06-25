"""
Row-oriented preparation tools: filter, sort, head/tail.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pandas as pd

from nodes.base import BaseTool

# ── Filter operator table ────────────────────────────────────────────────────
_FILTER_OPS = [
    ("equals", "= equals"),
    ("not_equals", "≠ not equals"),
    ("greater_than", "> greater than"),
    ("greater_eq", "≥ greater or equal"),
    ("less_than", "< less than"),
    ("less_eq", "≤ less or equal"),
    ("contains", "contains"),
    ("starts_with", "starts with"),
    ("ends_with", "ends with"),
    ("is_null", "is null"),
    ("not_null", "is not null"),
    ("in_list", "in list  (a,b,c)"),
    ("between", "between  lo,hi"),
]
_OP_DISP = [d for _, d in _FILTER_OPS]
_D2K = {d: k for k, d in _FILTER_OPS}
_K2D = {k: d for k, d in _FILTER_OPS}


class FilterRows(BaseTool):
    node_type = "filter_rows"
    display_name = "Filter Rows"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["true", "false"]

    def build_config(self, parent, params, on_change, columns=None):
        cols = columns if isinstance(columns, list) else []
        params.setdefault("conditions", [])
        params.setdefault("logic", "AND")

        # ── Logic row ────────────────────────────────────────────────────
        self.add_combobox(parent, "Logic", "logic", ["AND", "OR"], params, on_change, 0)

        # ── Conditions ───────────────────────────────────────────────────
        ttk.Label(parent, text="Conditions:").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(6, 2)
        )

        container = ttk.Frame(parent)
        container.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4)
        parent.columnconfigure(1, weight=1)

        conditions: list[dict] = params["conditions"]

        def rebuild() -> None:
            for w in container.winfo_children():
                w.destroy()

            for i, cond in enumerate(conditions):
                rf = ttk.Frame(container)
                rf.pack(fill="x", pady=1)

                # Column dropdown
                col_var = tk.StringVar(value=cond.get("column", ""))

                def _col_cb(*_, c=cond, v=col_var):
                    c["column"] = v.get()
                    on_change()

                col_var.trace_add("write", _col_cb)
                ttk.Combobox(rf, textvariable=col_var, values=cols, width=13).pack(
                    side="left", padx=(0, 2)
                )

                # Operator dropdown (display → key mapping)
                cur_op = cond.get("operator", "equals")
                op_var = tk.StringVar(value=_K2D.get(cur_op, _OP_DISP[0]))

                def _op_cb(*_, c=cond, v=op_var):
                    c["operator"] = _D2K.get(v.get(), "equals")
                    on_change()

                op_var.trace_add("write", _op_cb)
                ttk.Combobox(
                    rf, textvariable=op_var, values=_OP_DISP, state="readonly", width=16
                ).pack(side="left", padx=(0, 2))

                # Value entry (hidden for null checks)
                val_var = tk.StringVar(value=cond.get("value", ""))

                def _val_cb(*_, c=cond, v=val_var):
                    c["value"] = v.get()
                    on_change()

                val_var.trace_add("write", _val_cb)
                ttk.Entry(rf, textvariable=val_var, width=12).pack(side="left", padx=(0, 2))

                # Remove button
                def _remove(idx=i):
                    conditions.pop(idx)
                    rebuild()
                    on_change()

                ttk.Button(rf, text="×", width=2, command=_remove).pack(side="left")

            # Add button
            def _add():
                conditions.append({"column": "", "operator": "equals", "value": ""})
                rebuild()
                on_change()

            ttk.Button(container, text="+ Add condition", command=_add).pack(
                anchor="w", pady=(4, 0)
            )

        rebuild()

    def _apply_op(self, s: pd.Series, op: str, val: str) -> pd.Series:
        if op in ("is_null",):
            return s.isna()
        if op in ("not_null",):
            return s.notna()
        if op == "equals":
            try:
                return pd.to_numeric(s, errors="coerce") == float(val)
            except (ValueError, TypeError):
                return s.astype(str) == str(val)
        if op == "not_equals":
            try:
                return pd.to_numeric(s, errors="coerce") != float(val)
            except (ValueError, TypeError):
                return s.astype(str) != str(val)
        if op == "greater_than":
            return pd.to_numeric(s, errors="coerce") > float(val)
        if op == "greater_eq":
            return pd.to_numeric(s, errors="coerce") >= float(val)
        if op == "less_than":
            return pd.to_numeric(s, errors="coerce") < float(val)
        if op == "less_eq":
            return pd.to_numeric(s, errors="coerce") <= float(val)
        if op == "contains":
            return s.astype(str).str.contains(val, case=False, na=False)
        if op == "starts_with":
            return s.astype(str).str.startswith(val)
        if op == "ends_with":
            return s.astype(str).str.endswith(val)
        if op == "in_list":
            items = [v.strip() for v in val.split(",")]
            return s.astype(str).isin(items)
        if op == "between":
            parts = [v.strip() for v in val.split(",")]
            if len(parts) == 2:
                return pd.to_numeric(s, errors="coerce").between(float(parts[0]), float(parts[1]))
        return pd.Series(True, index=s.index)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        conditions = params.get("conditions", [])
        logic = params.get("logic", "AND")
        if not conditions:
            return {"true": df, "false": df.iloc[0:0]}
        masks = []
        for cond in conditions:
            col = cond.get("column", "")
            op = cond.get("operator", "equals")
            val = cond.get("value", "")
            if not col or col not in df.columns:
                continue
            masks.append(self._apply_op(df[col], op, val))
        if not masks:
            return {"true": df, "false": df.iloc[0:0]}
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m if logic == "AND" else combined | m
        true_df = df[combined].reset_index(drop=True)
        false_df = df[~combined].reset_index(drop=True)
        log(f"Filter: {len(true_df)} matched, {len(false_df)} excluded")
        return {"true": true_df, "false": false_df}

    def _cond_to_expr(self, iv: str, cond: dict) -> str:
        col = cond.get("column", "")
        op = cond.get("operator", "equals")
        val = cond.get("value", "")
        c = f'{iv}["{col}"]'
        if op == "equals":
            return f"({c} == {val!r})"
        if op == "not_equals":
            return f"({c} != {val!r})"
        if op == "greater_than":
            return f'(pd.to_numeric({c}, errors="coerce") > {val})'
        if op == "greater_eq":
            return f'(pd.to_numeric({c}, errors="coerce") >= {val})'
        if op == "less_than":
            return f'(pd.to_numeric({c}, errors="coerce") < {val})'
        if op == "less_eq":
            return f'(pd.to_numeric({c}, errors="coerce") <= {val})'
        if op == "contains":
            return f"({c}.astype(str).str.contains({val!r}, case=False, na=False))"
        if op == "starts_with":
            return f"({c}.astype(str).str.startswith({val!r}))"
        if op == "ends_with":
            return f"({c}.astype(str).str.endswith({val!r}))"
        if op == "is_null":
            return f"({c}.isna())"
        if op == "not_null":
            return f"({c}.notna())"
        if op == "in_list":
            items = [v.strip() for v in val.split(",")]
            return f"({c}.astype(str).isin({items!r}))"
        if op == "between":
            parts = [v.strip() for v in val.split(",")]
            return f'(pd.to_numeric({c}, errors="coerce").between({parts[0]}, {parts[1]}))'
        return "True"

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        conditions = [c for c in params.get("conditions", []) if c.get("column")]
        logic = params.get("logic", "AND")
        outs = connected_outs or ["true", "false"]
        join = " & " if logic == "AND" else " | "
        if conditions:
            exprs = [self._cond_to_expr(iv, c) for c in conditions]
            mask_expr = join.join(exprs)
        else:
            mask_expr = f"pd.Series(True, index={iv}.index)"
        lines = [f"_mask = {mask_expr}"]
        if "true" in outs:
            lines.append(f"{output_var}_true = {iv}[_mask].reset_index(drop=True)")
        if "false" in outs:
            lines.append(f"{output_var}_false = {iv}[~_mask].reset_index(drop=True)")
        return lines

    def subtitle(self, params):
        n = len([c for c in params.get("conditions", []) if c.get("column")])
        logic = params.get("logic", "AND")
        return f"{n} condition(s) [{logic}]" if n else "no conditions"


class Sort(BaseTool):
    node_type = "sort"
    display_name = "Sort"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        cols = columns if isinstance(columns, list) else []
        fields = [
            {"key": "column", "type": "combobox", "values": cols, "width": 14},
            {
                "key": "order",
                "type": "combobox",
                "values": ["ascending", "descending"],
                "width": 11,
            },
        ]
        ttk.Label(parent, text="Sort rules:").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 0))
        self.add_dynamic_rows(
            parent,
            "rules",
            params,
            on_change,
            fields,
            default_row={"column": "", "order": "ascending"},
            add_label="+ Add sort rule",
        )

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        rules = params.get("rules", [])
        by = [r["column"] for r in rules if r.get("column")]
        asc = [r.get("order", "ascending") == "ascending" for r in rules if r.get("column")]
        if not by:
            return {"data": df}
        return {"data": df.sort_values(by=by, ascending=asc).reset_index(drop=True)}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        rules = params.get("rules", [])
        by = [r["column"] for r in rules if r.get("column")]
        asc = [r.get("order", "ascending") == "ascending" for r in rules if r.get("column")]
        if not by:
            return [f"{output_var} = {iv}.copy()"]
        return [
            f"{output_var} = {iv}.sort_values(by={by!r}, ascending={asc!r}).reset_index(drop=True)"
        ]

    def subtitle(self, params):
        rules = params.get("rules", [])
        cols = [r.get("column", "") for r in rules if r.get("column")]
        return ", ".join(cols[:3]) or "not configured"


class HeadTail(BaseTool):
    node_type = "head_tail"
    display_name = "Head / Tail"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_combobox(parent, "Mode", "mode", ["head", "tail"], params, on_change, 0)
        self.add_entry(parent, "Rows", "n", params, on_change, 1, width=8)
        params.setdefault("n", "10")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        n = int(params.get("n") or 10)
        mode = params.get("mode", "head")
        result = df.head(n) if mode == "head" else df.tail(n)
        log(f"{mode}({n}): {len(result)} rows")
        return {"data": result.reset_index(drop=True)}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        n = int(params.get("n") or 10)
        mode = params.get("mode", "head")
        return [f"{output_var} = {iv}.{mode}({n}).reset_index(drop=True)"]

    def subtitle(self, params):
        return f"{params.get('mode', 'head')}({params.get('n', 10)})"
