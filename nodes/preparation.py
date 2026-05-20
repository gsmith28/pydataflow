from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import pandas as pd
from nodes.base import BaseTool


class SelectColumns(BaseTool):
    node_type = "select_columns"
    display_name = "Select Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_column_multiselect(parent, "Columns", "columns", params, on_change, 0, columns or [])

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
        ttk.Label(parent, text="Filter expression\n(pandas query syntax)").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        self.add_textarea(parent, "", "expr", params, on_change, 1, height=3)
        self.add_combobox(parent, "Logic", "logic", ["AND", "OR"], params, on_change, 2)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        expr = params.get("expr", "").strip()
        if not expr:
            return {"true": df, "false": df.iloc[0:0]}
        try:
            mask = df.eval(expr)
        except Exception as e:
            raise ValueError(f"Filter expression error: {e}")
        true_df = df[mask].reset_index(drop=True)
        false_df = df[~mask].reset_index(drop=True)
        log(f"Filter: {len(true_df)} matched, {len(false_df)} excluded")
        return {"true": true_df, "false": false_df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        expr = params.get("expr", "").strip()
        outs = connected_outs or ["true", "false"]
        lines = [f"_mask = {iv}.eval({expr!r})"]
        if "true" in outs:
            lines.append(f"{output_var}_true = {iv}[_mask].reset_index(drop=True)")
        if "false" in outs:
            lines.append(f"{output_var}_false = {iv}[~_mask].reset_index(drop=True)")
        return lines

    def subtitle(self, params):
        expr = params.get("expr", "")
        return expr[:25] + "…" if len(expr) > 25 else expr


class Sort(BaseTool):
    node_type = "sort"
    display_name = "Sort"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        fields = [
            {"key": "column", "label": "Column", "type": "combobox",
             "values": columns or [], "width": 14},
            {"key": "order", "label": "Order", "type": "combobox",
             "values": ["ascending", "descending"], "width": 10},
        ]
        ttk.Label(parent, text="Sort rules:").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 0))
        self.add_dynamic_rows(parent, "rules", params, on_change, fields,
                              default_row={"column": "", "order": "ascending"})

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        rules = params.get("rules", [])
        if not rules:
            return {"data": df}
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
        return [f"{output_var} = {iv}.sort_values(by={by!r}, ascending={asc!r}).reset_index(drop=True)"]

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


class RenameColumns(BaseTool):
    node_type = "rename_columns"
    display_name = "Rename Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        ttk.Label(parent, text="old_name = new_name  (one per line)").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        self.add_textarea(parent, "", "mappings", params, on_change, 1, height=5)

    def _parse_mappings(self, params):
        text = params.get("mappings", "")
        result = {}
        for line in text.strip().splitlines():
            if "=" in line:
                left, _, right = line.partition("=")
                result[left.strip()] = right.strip()
        return result

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        mapping = self._parse_mappings(params)
        if not mapping:
            return {"data": df}
        return {"data": df.rename(columns=mapping)}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        mapping = self._parse_mappings(params)
        return [f"{output_var} = {iv}.rename(columns={mapping!r})"]

    def subtitle(self, params):
        m = self._parse_mappings(params)
        return f"{len(m)} renames" if m else "not configured"


class EditColumns(BaseTool):
    node_type = "edit_columns"
    display_name = "Edit Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        dtypes = ["str", "int", "float", "bool", "datetime", "category"]
        fields = [
            {"key": "column", "type": "combobox", "values": columns or [], "width": 14},
            {"key": "dtype", "type": "combobox", "values": dtypes, "width": 9},
        ]
        ttk.Label(parent, text="Type conversions:").grid(row=0, column=0, sticky="w", padx=4, pady=(4, 0))
        self.add_dynamic_rows(parent, "conversions", params, on_change, fields,
                              default_row={"column": "", "dtype": "str"})

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        df = df.copy()
        for conv in params.get("conversions", []):
            col = conv.get("column")
            dtype = conv.get("dtype", "str")
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
            except Exception as e:
                log(f"Could not convert {col} to {dtype}: {e}", "warning")
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        lines = [f"{output_var} = {iv}.copy()"]
        for conv in params.get("conversions", []):
            col = conv.get("column")
            dtype = conv.get("dtype", "str")
            if not col:
                continue
            if dtype == "datetime":
                lines.append(f'{output_var}["{col}"] = pd.to_datetime({output_var}["{col}"], errors="coerce")')
            elif dtype in ("int", "float"):
                lines.append(f'{output_var}["{col}"] = pd.to_numeric({output_var}["{col}"], errors="coerce")')
            else:
                lines.append(f'{output_var}["{col}"] = {output_var}["{col}"].astype("{dtype}")')
        return lines

    def subtitle(self, params):
        c = params.get("conversions", [])
        return f"{len(c)} conversions" if c else "not configured"


class AddColumns(BaseTool):
    node_type = "add_columns"
    display_name = "Add Columns"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        ttk.Label(parent, text="name = expression  (one per line)").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        self.add_textarea(parent, "", "formulas", params, on_change, 1, height=5)

    def _parse_formulas(self, params):
        text = params.get("formulas", "")
        result = []
        for line in text.strip().splitlines():
            if "=" in line:
                left, _, right = line.partition("=")
                result.append((left.strip(), right.strip()))
        return result

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        df = df.copy()
        for name, expr in self._parse_formulas(params):
            if not name:
                continue
            try:
                df[name] = df.eval(expr)
            except Exception:
                try:
                    df[name] = eval(expr, {"df": df, "pd": pd})  # noqa: S307
                except Exception as e:
                    log(f"Could not compute {name}: {e}", "warning")
                    df[name] = None
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        lines = [f"{output_var} = {iv}.copy()"]
        for name, expr in self._parse_formulas(params):
            if name:
                lines.append(f'{output_var}["{name}"] = {output_var}.eval({expr!r})')
        return lines

    def subtitle(self, params):
        f = self._parse_formulas(params)
        return f"{len(f)} formula(s)" if f else "not configured"


class Cleansing(BaseTool):
    node_type = "cleansing"
    display_name = "Cleansing"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_column_multiselect(parent, "Columns", "columns", params, on_change, 0, columns or [])
        self.add_checkbox(parent, "Trim whitespace", "trim", params, on_change, 1)
        self.add_checkbox(parent, "Collapse spaces", "collapse", params, on_change, 2)
        self.add_checkbox(parent, "Remove tabs/newlines", "rm_ctrl", params, on_change, 3)
        self.add_combobox(parent, "Case", "case", ["none", "upper", "lower", "title"],
                          params, on_change, 4)
        self.add_checkbox(parent, "Null → blank string", "null_to_blank", params, on_change, 5)
        self.add_checkbox(parent, "Drop all-null rows", "drop_null_rows", params, on_change, 6)

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
            if case == "upper":
                s = s.str.upper()
            elif case == "lower":
                s = s.str.lower()
            elif case == "title":
                s = s.str.title()
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
        if params.get("trim"):
            ops.append("trim")
        if params.get("case", "none") != "none":
            ops.append(params["case"])
        return ", ".join(ops) if ops else "not configured"


class RecordID(BaseTool):
    node_type = "record_id"
    display_name = "Record ID"
    color = "#2a85c4"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_entry(parent, "Field name", "field_name", params, on_change, 0)
        self.add_entry(parent, "Start value", "start", params, on_change, 1, width=8)
        self.add_combobox(parent, "Position", "position", ["first", "last"], params, on_change, 2)
        params.setdefault("field_name", "id")
        params.setdefault("start", "1")
        params.setdefault("position", "first")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        df = df.copy()
        name = params.get("field_name") or "id"
        start = int(params.get("start") or 1)
        pos = params.get("position", "first")
        ids = range(start, start + len(df))
        if pos == "first":
            df.insert(0, name, ids)
        else:
            df[name] = ids
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        name = params.get("field_name") or "id"
        start = int(params.get("start") or 1)
        pos = params.get("position", "first")
        lines = [f"{output_var} = {iv}.copy()"]
        if pos == "first":
            lines.append(f'{output_var}.insert(0, "{name}", range({start}, {start} + len({output_var})))')
        else:
            lines.append(f'{output_var}["{name}"] = range({start}, {start} + len({output_var}))')
        return lines

    def subtitle(self, params):
        name = params.get("field_name") or "id"
        start = params.get("start", 1)
        return f"{name} from {start}"
