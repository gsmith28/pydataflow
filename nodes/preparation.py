"""
Preparation tool nodes (9 tools).

SelectColumns, FilterRows, Sort, HeadTail, RenameColumns,
EditColumns, AddColumns, Cleansing, RecordID.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import pandas as pd
from nodes.base import BaseTool

# ── Filter operator table ────────────────────────────────────────────────────
_FILTER_OPS = [
    ("equals",       "= equals"),
    ("not_equals",   "≠ not equals"),
    ("greater_than", "> greater than"),
    ("greater_eq",   "≥ greater or equal"),
    ("less_than",    "< less than"),
    ("less_eq",      "≤ less or equal"),
    ("contains",     "contains"),
    ("starts_with",  "starts with"),
    ("ends_with",    "ends with"),
    ("is_null",      "is null"),
    ("not_null",     "is not null"),
    ("in_list",      "in list  (a,b,c)"),
    ("between",      "between  lo,hi"),
]
_OP_DISP = [d for _, d in _FILTER_OPS]
_OP_KEY  = [k for k, _ in _FILTER_OPS]
_D2K     = {d: k for k, d in _FILTER_OPS}
_K2D     = {k: d for k, d in _FILTER_OPS}

_ADD_COL_HELP = (
    "Formula examples (reference columns by name):\n"
    "  Numeric : price * qty   |  amount.round(2)  |  (a + b) / 2\n"
    "  Text    : name.str.upper()  |  name.str[:5]  |  name.str.len()\n"
    "            name.str.replace('old','new')  |  name.str.strip()\n"
    "  Date    : pd.to_datetime(date_col).dt.year\n"
    "            pd.to_datetime(date_col).dt.month\n"
    "            pd.to_datetime(date_col).dt.dayofweek\n"
    "  Cond.   : np.where(price > 100, 'high', 'low')\n"
    "            col.where(col > 0, 0)\n"
    "  Cast    : col.astype(str)  |  pd.to_numeric(col, errors='coerce')"
)


class SelectColumns(BaseTool):
    node_type = "select_columns"
    display_name = "Select Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        cols = columns if isinstance(columns, list) else []
        self.add_column_multiselect(parent, "Columns", "columns",
                                    params, on_change, 0, cols)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        cols = params.get("columns", [])
        if isinstance(cols, str):
            cols = [c.strip() for c in cols.split(",") if c.strip()]
        if not cols:
            return {"data": df}
        missing = [c for c in cols if c not in df.columns]
        if missing:
            log(f"Warning: columns not found: {missing}", "warning")
        valid = [c for c in cols if c in df.columns]
        return {"data": df[valid]}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        cols = params.get("columns", [])
        if isinstance(cols, str):
            cols = [c.strip() for c in cols.split(",") if c.strip()]
        return [f"{output_var} = {iv}[{cols!r}]"]

    def subtitle(self, params):
        cols = params.get("columns", [])
        if isinstance(cols, list):
            return f"{len(cols)} cols" if cols else "all cols"
        return str(cols)[:20]


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
        self.add_combobox(parent, "Logic", "logic", ["AND", "OR"],
                          params, on_change, 0)

        # ── Conditions ───────────────────────────────────────────────────
        ttk.Label(parent, text="Conditions:").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(6, 2))

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
                    c["column"] = v.get(); on_change()
                col_var.trace_add("write", _col_cb)
                ttk.Combobox(rf, textvariable=col_var, values=cols,
                             width=13).pack(side="left", padx=(0, 2))

                # Operator dropdown (display → key mapping)
                cur_op  = cond.get("operator", "equals")
                op_var  = tk.StringVar(value=_K2D.get(cur_op, _OP_DISP[0]))
                def _op_cb(*_, c=cond, v=op_var):
                    c["operator"] = _D2K.get(v.get(), "equals"); on_change()
                op_var.trace_add("write", _op_cb)
                ttk.Combobox(rf, textvariable=op_var, values=_OP_DISP,
                             state="readonly", width=16).pack(side="left", padx=(0, 2))

                # Value entry (hidden for null checks)
                val_var = tk.StringVar(value=cond.get("value", ""))
                def _val_cb(*_, c=cond, v=val_var):
                    c["value"] = v.get(); on_change()
                val_var.trace_add("write", _val_cb)
                ttk.Entry(rf, textvariable=val_var, width=12).pack(side="left", padx=(0, 2))

                # Remove button
                def _remove(idx=i):
                    conditions.pop(idx); rebuild(); on_change()
                ttk.Button(rf, text="×", width=2, command=_remove).pack(side="left")

            # Add button
            def _add():
                conditions.append({"column": "", "operator": "equals", "value": ""})
                rebuild(); on_change()
            ttk.Button(container, text="+ Add condition", command=_add).pack(anchor="w", pady=(4, 0))

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
                return pd.to_numeric(s, errors="coerce").between(
                    float(parts[0]), float(parts[1]))
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
            op  = cond.get("operator", "equals")
            val = cond.get("value", "")
            if not col or col not in df.columns:
                continue
            masks.append(self._apply_op(df[col], op, val))
        if not masks:
            return {"true": df, "false": df.iloc[0:0]}
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m if logic == "AND" else combined | m
        true_df  = df[combined].reset_index(drop=True)
        false_df = df[~combined].reset_index(drop=True)
        log(f"Filter: {len(true_df)} matched, {len(false_df)} excluded")
        return {"true": true_df, "false": false_df}

    def _cond_to_expr(self, iv: str, cond: dict) -> str:
        col = cond.get("column", "")
        op  = cond.get("operator", "equals")
        val = cond.get("value", "")
        c = f'{iv}["{col}"]'
        if op == "equals":        return f'({c} == {val!r})'
        if op == "not_equals":    return f'({c} != {val!r})'
        if op == "greater_than":  return f'(pd.to_numeric({c}, errors="coerce") > {val})'
        if op == "greater_eq":    return f'(pd.to_numeric({c}, errors="coerce") >= {val})'
        if op == "less_than":     return f'(pd.to_numeric({c}, errors="coerce") < {val})'
        if op == "less_eq":       return f'(pd.to_numeric({c}, errors="coerce") <= {val})'
        if op == "contains":      return f'({c}.astype(str).str.contains({val!r}, case=False, na=False))'
        if op == "starts_with":   return f'({c}.astype(str).str.startswith({val!r}))'
        if op == "ends_with":     return f'({c}.astype(str).str.endswith({val!r}))'
        if op == "is_null":       return f'({c}.isna())'
        if op == "not_null":      return f'({c}.notna())'
        if op == "in_list":
            items = [v.strip() for v in val.split(",")]
            return f'({c}.astype(str).isin({items!r}))'
        if op == "between":
            parts = [v.strip() for v in val.split(",")]
            return f'(pd.to_numeric({c}, errors="coerce").between({parts[0]}, {parts[1]}))'
        return "True"

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        conditions = [c for c in params.get("conditions", []) if c.get("column")]
        logic = params.get("logic", "AND")
        outs  = connected_outs or ["true", "false"]
        join  = " & " if logic == "AND" else " | "
        if conditions:
            exprs   = [self._cond_to_expr(iv, c) for c in conditions]
            mask_expr = join.join(exprs)
        else:
            mask_expr = f"pd.Series(True, index={iv}.index)"
        lines = [f"_mask = {mask_expr}"]
        if "true"  in outs: lines.append(f"{output_var}_true  = {iv}[_mask].reset_index(drop=True)")
        if "false" in outs: lines.append(f"{output_var}_false = {iv}[~_mask].reset_index(drop=True)")
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
            {"key": "order",  "type": "combobox",
             "values": ["ascending", "descending"], "width": 11},
        ]
        ttk.Label(parent, text="Sort rules:").grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 0))
        self.add_dynamic_rows(parent, "rules", params, on_change, fields,
                              default_row={"column": "", "order": "ascending"},
                              add_label="+ Add sort rule")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        rules = params.get("rules", [])
        by  = [r["column"] for r in rules if r.get("column")]
        asc = [r.get("order", "ascending") == "ascending" for r in rules if r.get("column")]
        if not by:
            return {"data": df}
        return {"data": df.sort_values(by=by, ascending=asc).reset_index(drop=True)}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        rules = params.get("rules", [])
        by  = [r["column"] for r in rules if r.get("column")]
        asc = [r.get("order", "ascending") == "ascending" for r in rules if r.get("column")]
        if not by:
            return [f"{output_var} = {iv}.copy()"]
        return [f"{output_var} = {iv}.sort_values(by={by!r}, ascending={asc!r}).reset_index(drop=True)"]

    def subtitle(self, params):
        rules = params.get("rules", [])
        cols  = [r.get("column", "") for r in rules if r.get("column")]
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


class RenameColumns(BaseTool):
    node_type = "rename_columns"
    display_name = "Rename Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        cols = columns if isinstance(columns, list) else []
        params.setdefault("renames", [])

        ttk.Label(parent, text="Rename rules  (old column → new name):").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 2))

        container = ttk.Frame(parent)
        container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4)
        parent.columnconfigure(1, weight=1)

        renames: list[dict] = params["renames"]

        def rebuild() -> None:
            for w in container.winfo_children():
                w.destroy()

            for i, rule in enumerate(renames):
                rf = ttk.Frame(container)
                rf.pack(fill="x", pady=1)

                # Old column dropdown
                from_var = tk.StringVar(value=rule.get("from", ""))
                def _from_cb(*_, r=rule, v=from_var):
                    r["from"] = v.get(); on_change()
                from_var.trace_add("write", _from_cb)
                ttk.Combobox(rf, textvariable=from_var, values=cols,
                             width=14).pack(side="left", padx=(0, 2))

                tk.Label(rf, text="→", bg="#252535", fg="#7878a0",
                         font=("Segoe UI", 9)).pack(side="left", padx=2)

                # New name entry
                to_var = tk.StringVar(value=rule.get("to", ""))
                def _to_cb(*_, r=rule, v=to_var):
                    r["to"] = v.get(); on_change()
                to_var.trace_add("write", _to_cb)
                ttk.Entry(rf, textvariable=to_var, width=14).pack(side="left", padx=(0, 2))

                def _remove(idx=i):
                    renames.pop(idx); rebuild(); on_change()
                ttk.Button(rf, text="×", width=2, command=_remove).pack(side="left")

            def _add():
                renames.append({"from": "", "to": ""})
                rebuild(); on_change()
            ttk.Button(container, text="+ Add rename", command=_add).pack(anchor="w", pady=(4, 0))

        rebuild()

    def _get_mapping(self, params) -> dict:
        return {
            r["from"]: r["to"]
            for r in params.get("renames", [])
            if r.get("from") and r.get("to")
        }

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        mapping = self._get_mapping(params)
        return {"data": df.rename(columns=mapping) if mapping else df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        mapping = self._get_mapping(params)
        return [f"{output_var} = {iv}.rename(columns={mapping!r})"]

    def subtitle(self, params):
        n = len(self._get_mapping(params))
        return f"{n} rename(s)" if n else "not configured"


class EditColumns(BaseTool):
    """Change data types of columns (string ↔ numeric ↔ datetime ↔ category)."""
    node_type = "edit_columns"
    display_name = "Edit Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    _DTYPES = ["str", "int (Int64)", "float", "bool", "datetime", "category"]
    _DTYPE_MAP = {
        "str": "str", "int (Int64)": "int", "float": "float",
        "bool": "bool", "datetime": "datetime", "category": "category",
    }

    def build_config(self, parent, params, on_change, columns=None):
        cols = columns if isinstance(columns, list) else []
        ttk.Label(parent, text="Convert column data types:").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 2))
        ttk.Label(parent,
                  text="int/float → numeric  |  str → text  |  datetime → date parsing",
                  foreground="#7878a0", font=("Segoe UI", 7)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))

        fields = [
            {"key": "column", "type": "combobox", "values": cols,  "width": 14},
            {"key": "dtype",  "type": "combobox", "values": self._DTYPES, "width": 11},
        ]
        self.add_dynamic_rows(parent, "conversions", params, on_change, fields,
                              default_row={"column": "", "dtype": "str"},
                              add_label="+ Add conversion")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        df = df.copy()
        for conv in params.get("conversions", []):
            col   = conv.get("column")
            dtype = self._DTYPE_MAP.get(conv.get("dtype", "str"), "str")
            if not col or col not in df.columns:
                continue
            try:
                if dtype == "datetime":
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                elif dtype == "int":
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif dtype == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
                elif dtype == "bool":
                    df[col] = df[col].astype(bool)
                elif dtype == "category":
                    df[col] = df[col].astype("category")
                else:
                    df[col] = df[col].astype(str)
                log(f"Converted {col} → {dtype}")
            except Exception as e:
                log(f"Could not convert {col} to {dtype}: {e}", "warning")
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        lines = [f"{output_var} = {iv}.copy()"]
        for conv in params.get("conversions", []):
            col   = conv.get("column")
            dtype = self._DTYPE_MAP.get(conv.get("dtype", "str"), "str")
            if not col:
                continue
            if dtype == "datetime":
                lines.append(f'{output_var}["{col}"] = pd.to_datetime({output_var}["{col}"], errors="coerce")')
            elif dtype in ("int", "float"):
                suffix = '.astype("Int64")' if dtype == "int" else ".astype(float)"
                lines.append(f'{output_var}["{col}"] = pd.to_numeric({output_var}["{col}"], errors="coerce"){suffix}')
            else:
                lines.append(f'{output_var}["{col}"] = {output_var}["{col}"].astype("{dtype}")')
        return lines

    def subtitle(self, params):
        c = [x for x in params.get("conversions", []) if x.get("column")]
        return f"{len(c)} conversion(s)" if c else "not configured"


class AddColumns(BaseTool):
    node_type = "add_columns"
    display_name = "Add Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        params.setdefault("new_cols", [])

        ttk.Label(parent, text="New columns  (name + formula):").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 2))

        container = ttk.Frame(parent)
        container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4)
        parent.columnconfigure(1, weight=1)

        new_cols: list[dict] = params["new_cols"]

        def rebuild() -> None:
            for w in container.winfo_children():
                w.destroy()
            for i, col in enumerate(new_cols):
                rf = ttk.Frame(container)
                rf.pack(fill="x", pady=2)
                rf.columnconfigure(1, weight=1)

                # Name entry
                nm_var = tk.StringVar(value=col.get("name", ""))
                def _nm(*_, c=col, v=nm_var): c["name"] = v.get(); on_change()
                nm_var.trace_add("write", _nm)
                ttk.Label(rf, text="Name").grid(row=0, column=0, sticky="w", padx=(0,2))
                ttk.Entry(rf, textvariable=nm_var, width=12).grid(row=0, column=1, sticky="ew", padx=(0,2))

                def _rm(idx=i): new_cols.pop(idx); rebuild(); on_change()
                ttk.Button(rf, text="×", width=2, command=_rm).grid(row=0, column=2)

                # Formula entry
                fm_var = tk.StringVar(value=col.get("formula", ""))
                def _fm(*_, c=col, v=fm_var): c["formula"] = v.get(); on_change()
                fm_var.trace_add("write", _fm)
                ttk.Label(rf, text="Formula").grid(row=1, column=0, sticky="w", padx=(0,2))
                ttk.Entry(rf, textvariable=fm_var, width=24).grid(row=1, column=1, columnspan=2, sticky="ew")

            def _add(): new_cols.append({"name": "", "formula": ""}); rebuild(); on_change()
            ttk.Button(container, text="+ Add column", command=_add).pack(anchor="w", pady=(4, 0))

        rebuild()

        # Formula guide
        sep_row = parent.grid_size()[1]
        ttk.Separator(parent, orient="horizontal").grid(
            row=sep_row, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        guide = tk.Text(parent, height=10, bg="#0d0d1a", fg="#888888",
                        font=("Courier New", 7), state="normal", relief="flat",
                        wrap="word")
        guide.insert("1.0", _ADD_COL_HELP)
        guide.configure(state="disabled")
        guide.grid(row=sep_row + 1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        df = df.copy()
        import numpy as np
        ctx = {"df": df, "pd": pd, "np": np, **{c: df[c] for c in df.columns}}
        for col_def in params.get("new_cols", []):
            name    = (col_def.get("name") or "").strip()
            formula = (col_def.get("formula") or "").strip()
            if not name or not formula:
                continue
            try:
                df[name] = df.eval(formula)
            except Exception:
                try:
                    df[name] = eval(formula, ctx)  # noqa: S307
                except Exception as e:
                    log(f"Could not compute '{name}': {e}", "warning")
                    df[name] = None
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        lines = [f"{output_var} = {iv}.copy()"]
        for col_def in params.get("new_cols", []):
            name    = (col_def.get("name") or "").strip()
            formula = (col_def.get("formula") or "").strip()
            if name and formula:
                lines.append(f'{output_var}["{name}"] = {output_var}.eval({formula!r})')
        return lines

    def subtitle(self, params):
        n = len([c for c in params.get("new_cols", []) if c.get("name")])
        return f"{n} new column(s)" if n else "not configured"


class Cleansing(BaseTool):
    node_type = "cleansing"
    display_name = "Cleansing"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        cols = columns if isinstance(columns, list) else []
        self.add_column_multiselect(parent, "Columns", "columns",
                                    params, on_change, 0, cols)
        self.add_checkbox(parent, "Trim whitespace",       "trim",          params, on_change, 1)
        self.add_checkbox(parent, "Collapse spaces",       "collapse",      params, on_change, 2)
        self.add_checkbox(parent, "Remove tabs/newlines",  "rm_ctrl",       params, on_change, 3)
        self.add_combobox(parent, "Case", "case",
                          ["none", "upper", "lower", "title"],
                          params, on_change, 4)
        self.add_checkbox(parent, "Null → blank string",  "null_to_blank",  params, on_change, 5)
        self.add_checkbox(parent, "Drop all-null rows",   "drop_null_rows", params, on_change, 6)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        df = df.copy()
        cols = params.get("columns", [])
        if isinstance(cols, str):
            cols = [c.strip() for c in cols.split(",") if c.strip()]
        if not cols:
            cols = list(df.select_dtypes(include="object").columns)
        for col in cols:
            if col not in df.columns:
                continue
            s = df[col].astype(str)
            if params.get("trim"):
                s = s.str.strip()
            if params.get("collapse"):
                s = s.str.replace(r"\s+", " ", regex=True)
            if params.get("rm_ctrl"):
                s = s.str.replace(r"[\t\n\r]", " ", regex=True)
            case = params.get("case", "none")
            if case == "upper":   s = s.str.upper()
            elif case == "lower": s = s.str.lower()
            elif case == "title": s = s.str.title()
            if params.get("null_to_blank"):
                df[col] = df[col].fillna("").astype(str)
            else:
                df[col] = s
        if params.get("drop_null_rows"):
            df = df.dropna(how="all").reset_index(drop=True)
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        return [f"{output_var} = {iv}.copy()  # cleansing — see node config"]

    def subtitle(self, params):
        ops = []
        if params.get("trim"):    ops.append("trim")
        if params.get("case", "none") != "none": ops.append(params["case"])
        return ", ".join(ops) if ops else "not configured"


class RecordID(BaseTool):
    node_type = "record_id"
    display_name = "Record ID"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_entry(parent,   "Field name",  "field_name", params, on_change, 0)
        self.add_entry(parent,   "Start value", "start",      params, on_change, 1, width=8)
        self.add_combobox(parent, "Position", "position",
                          ["first", "last"], params, on_change, 2)
        params.setdefault("field_name", "id")
        params.setdefault("start",      "1")
        params.setdefault("position",   "first")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        df    = df.copy()
        name  = params.get("field_name") or "id"
        start = int(params.get("start") or 1)
        pos   = params.get("position", "first")
        ids   = range(start, start + len(df))
        if pos == "first":
            df.insert(0, name, ids)
        else:
            df[name] = ids
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv    = input_vars[0] if input_vars else "df"
        name  = params.get("field_name") or "id"
        start = int(params.get("start") or 1)
        pos   = params.get("position", "first")
        lines = [f"{output_var} = {iv}.copy()"]
        if pos == "first":
            lines.append(f'{output_var}.insert(0, "{name}", range({start}, {start} + len({output_var})))')
        else:
            lines.append(f'{output_var}["{name}"] = range({start}, {start} + len({output_var}))')
        return lines

    def subtitle(self, params):
        return f"{params.get('field_name','id')} from {params.get('start',1)}"
