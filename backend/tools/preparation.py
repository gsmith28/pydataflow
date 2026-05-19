from __future__ import annotations
from typing import Any
import pandas as pd
import numpy as np
from tools.base import BaseTool, ExecutionContext, ToolError


def _evaluate_condition(df: pd.DataFrame, cond: dict[str, Any]) -> pd.Series:
    ctype = cond.get("type", "comparison")
    if ctype == "comparison":
        field = cond["field"]
        op = cond["op"]
        value = cond.get("value")
        col = df[field]
        if op == "==":
            return col == value
        elif op == "!=":
            return col != value
        elif op == ">":
            return col > value
        elif op == ">=":
            return col >= value
        elif op == "<":
            return col < value
        elif op == "<=":
            return col <= value
        elif op == "contains":
            return col.astype(str).str.contains(str(value), na=False)
        elif op == "starts_with":
            return col.astype(str).str.startswith(str(value), na=False)
        elif op == "ends_with":
            return col.astype(str).str.endswith(str(value), na=False)
        elif op == "is_null":
            return col.isna()
        elif op == "is_not_null":
            return col.notna()
        elif op == "in":
            vals = value if isinstance(value, list) else [value]
            return col.isin(vals)
        elif op == "not_in":
            vals = value if isinstance(value, list) else [value]
            return ~col.isin(vals)
        elif op == "between":
            lo, hi = value[0], value[1]
            return (col >= lo) & (col <= hi)
        else:
            raise ToolError(f"Unknown operator: {op}")
    elif ctype == "binary_op":
        left = _evaluate_condition(df, cond["left"])
        right = _evaluate_condition(df, cond["right"])
        if cond["op"] == "and":
            return left & right
        elif cond["op"] == "or":
            return left | right
        else:
            raise ToolError(f"Unknown binary op: {cond['op']}")
    else:
        raise ToolError(f"Unknown condition type: {ctype}")


def _condition_to_python(cond: dict[str, Any], df_var: str) -> str:
    ctype = cond.get("type", "comparison")
    if ctype == "comparison":
        field = cond["field"]
        op = cond["op"]
        value = cond.get("value")
        col = f'{df_var}["{field}"]'
        if op == "==":
            return f'({col} == {repr(value)})'
        elif op == "!=":
            return f'({col} != {repr(value)})'
        elif op == ">":
            return f'({col} > {repr(value)})'
        elif op == ">=":
            return f'({col} >= {repr(value)})'
        elif op == "<":
            return f'({col} < {repr(value)})'
        elif op == "<=":
            return f'({col} <= {repr(value)})'
        elif op == "contains":
            return f'({col}.astype(str).str.contains({repr(value)}, na=False))'
        elif op == "starts_with":
            return f'({col}.astype(str).str.startswith({repr(value)}, na=False))'
        elif op == "ends_with":
            return f'({col}.astype(str).str.endswith({repr(value)}, na=False))'
        elif op == "is_null":
            return f'({col}.isna())'
        elif op == "is_not_null":
            return f'({col}.notna())'
        elif op == "in":
            return f'({col}.isin({repr(value)}))'
        elif op == "not_in":
            return f'(~{col}.isin({repr(value)}))'
        elif op == "between":
            return f'(({col} >= {repr(value[0])}) & ({col} <= {repr(value[1])}))'
        else:
            return f'(pd.Series([True] * len({df_var})))'
    elif ctype == "binary_op":
        left = _condition_to_python(cond["left"], df_var)
        right = _condition_to_python(cond["right"], df_var)
        op = "&" if cond["op"] == "and" else "|"
        return f'({left} {op} {right})'
    return f'(pd.Series([True] * len({df_var})))'


class SelectFieldsTool(BaseTool):
    tool_type = "select_fields"
    display_name = "Select Fields"
    category = "Preparation"
    description = "Include, exclude, rename, and reorder fields."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "fields": {
            "type": "field_list",
            "label": "Field configuration",
            "description": "List of {name, include, rename_to, output_type} objects",
        },
        "unknown_fields": {
            "type": "select",
            "label": "Unknown fields",
            "options": ["allow", "drop", "warn", "error"],
            "default": "allow",
        },
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        fields = config.get("fields", [])

        if not fields:
            return {"out": df}

        selected = [f["name"] for f in fields if f.get("include", True) and f["name"] in df.columns]
        unknown = [f["name"] for f in fields if f["name"] not in df.columns]
        unknown_handling = config.get("unknown_fields", "allow")

        if unknown and unknown_handling == "error":
            raise ToolError(f"Unknown fields: {unknown}")
        if unknown and unknown_handling == "warn":
            for u in unknown:
                context.logger(f"Warning: field '{u}' not found in input.")

        out = df[selected].copy()

        rename_map = {f["name"]: f["rename_to"] for f in fields if f.get("rename_to") and f["name"] in selected}
        if rename_map:
            out = out.rename(columns=rename_map)

        for f in fields:
            target_name = f.get("rename_to") or f["name"]
            if target_name in out.columns and f.get("output_type"):
                try:
                    if f["output_type"] == "string":
                        out[target_name] = out[target_name].astype(str)
                    elif f["output_type"] == "integer":
                        out[target_name] = pd.to_numeric(out[target_name], errors="coerce").astype("Int64")
                    elif f["output_type"] == "float":
                        out[target_name] = pd.to_numeric(out[target_name], errors="coerce")
                    elif f["output_type"] == "datetime":
                        out[target_name] = pd.to_datetime(out[target_name], errors="coerce")
                    elif f["output_type"] == "boolean":
                        out[target_name] = out[target_name].astype(bool)
                except Exception:
                    pass

        return {"out": out}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_selected")
        fields = config.get("fields", [])
        selected = [f["name"] for f in fields if f.get("include", True)]
        rename_map = {f["name"]: f["rename_to"] for f in fields if f.get("rename_to")}
        lines = [f'{out_var} = {in_var}[{selected}].copy()']
        if rename_map:
            lines.append(f'{out_var} = {out_var}.rename(columns={repr(rename_map)})')
        return "\n".join(lines)


class FilterTool(BaseTool):
    tool_type = "filter"
    display_name = "Filter"
    category = "Preparation"
    description = "Split data into matching (true) and non-matching (false) streams."
    input_ports = ["in"]
    output_ports = ["true", "false"]
    config_schema = {
        "condition": {
            "type": "condition_builder",
            "label": "Filter condition",
            "description": "Structured condition expression",
        },
    }

    def validate_config(self, config: dict, input_schemas: dict) -> list[str]:
        if not config.get("condition"):
            return ["A filter condition is required."]
        return []

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        cond = config.get("condition")
        if not cond:
            return {"true": df.copy(), "false": pd.DataFrame(columns=df.columns)}

        mask = _evaluate_condition(df, cond)
        return {"true": df[mask].copy(), "false": df[~mask].copy()}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        true_var = output_vars.get("true", "df_true")
        false_var = output_vars.get("false", "df_false")
        cond = config.get("condition", {})
        mask_expr = _condition_to_python(cond, in_var)
        return (
            f"_mask = {mask_expr}\n"
            f"{true_var} = {in_var}[_mask].copy()\n"
            f"{false_var} = {in_var}[~_mask].copy()"
        )


class FormulaTool(BaseTool):
    tool_type = "formula"
    display_name = "Formula"
    category = "Preparation"
    description = "Create or update fields using expressions."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "formulas": {
            "type": "formula_list",
            "label": "Formulas",
            "description": "List of {target_field, expression, output_type} objects",
        },
    }

    def _eval_expr(self, df: pd.DataFrame, expression: str) -> pd.Series:
        local_ns = {
            "df": df,
            "pd": pd,
            "np": np,
            **{col: df[col] for col in df.columns},
        }
        try:
            result = eval(expression, {"__builtins__": {}}, local_ns)  # noqa: S307
            if isinstance(result, pd.Series):
                return result
            return pd.Series([result] * len(df))
        except Exception as e:
            raise ToolError(f"Formula evaluation error: {e}")

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        for formula in config.get("formulas", []):
            target = formula.get("target_field")
            expr = formula.get("expression", "")
            if target and expr:
                df[target] = self._eval_expr(df, expr)
        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_formula")
        lines = [f"{out_var} = {in_var}.copy()"]
        for f in config.get("formulas", []):
            target = f.get("target_field", "new_field")
            expr = f.get("expression", "None")
            lines.append(f'{out_var}["{target}"] = {expr}')
        return "\n".join(lines)


class SortTool(BaseTool):
    tool_type = "sort"
    display_name = "Sort"
    category = "Preparation"
    description = "Sort data by one or more fields."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "sort_fields": {
            "type": "sort_list",
            "label": "Sort fields",
            "description": "List of {field, ascending} objects",
        },
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        sort_fields = config.get("sort_fields", [])
        if not sort_fields:
            return {"out": df}
        cols = [s["field"] for s in sort_fields if s["field"] in df.columns]
        asc = [s.get("ascending", True) for s in sort_fields if s["field"] in df.columns]
        if cols:
            df = df.sort_values(by=cols, ascending=asc, kind="mergesort")
        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_sorted")
        sf = config.get("sort_fields", [])
        cols = [s["field"] for s in sf]
        asc = [s.get("ascending", True) for s in sf]
        return f'{out_var} = {in_var}.sort_values(by={cols}, ascending={asc}, kind="mergesort")'


class UniqueDuplicateTool(BaseTool):
    tool_type = "unique_duplicate"
    display_name = "Unique / Duplicate"
    category = "Preparation"
    description = "Separate unique and duplicate records based on key fields."
    input_ports = ["in"]
    output_ports = ["unique", "duplicate"]
    config_schema = {
        "key_fields": {"type": "multi_field_selector", "label": "Key fields"},
        "keep": {"type": "select", "label": "Keep occurrence", "options": ["first", "last"], "default": "first"},
        "case_insensitive": {"type": "checkbox", "label": "Case-insensitive matching", "default": False},
        "add_group_id": {"type": "checkbox", "label": "Add duplicate group ID", "default": False},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        key_fields = [f for f in config.get("key_fields", []) if f in df.columns]
        if not key_fields:
            return {"unique": df, "duplicate": pd.DataFrame(columns=df.columns)}

        keep = config.get("keep", "first")
        work = df.copy()

        if config.get("case_insensitive"):
            for f in key_fields:
                if work[f].dtype == object:
                    work[f"_norm_{f}"] = work[f].astype(str).str.strip().str.upper()
            norm_keys = [f"_norm_{f}" if work[df[f].name if hasattr(df[f], 'name') else f].dtype == object else f for f in key_fields]
        else:
            norm_keys = key_fields

        dup_mask = work.duplicated(subset=norm_keys, keep=keep)

        if config.get("add_group_id"):
            group_id = work.groupby(norm_keys, sort=False).ngroup()
            df["_duplicate_group_id"] = group_id

        return {"unique": df[~dup_mask].copy(), "duplicate": df[dup_mask].copy()}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        uniq_var = output_vars.get("unique", "df_unique")
        dup_var = output_vars.get("duplicate", "df_duplicate")
        keys = config.get("key_fields", [])
        keep = config.get("keep", "first")
        return (
            f"_dup_mask = {in_var}.duplicated(subset={keys}, keep=\"{keep}\")\n"
            f"{uniq_var} = {in_var}[~_dup_mask].copy()\n"
            f"{dup_var} = {in_var}[_dup_mask].copy()"
        )


class RecordIDTool(BaseTool):
    tool_type = "record_id"
    display_name = "Record ID"
    category = "Preparation"
    description = "Add a sequential record identifier field."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "field_name": {"type": "text", "label": "Field name", "default": "record_id"},
        "start": {"type": "number", "label": "Start value", "default": 1},
        "increment": {"type": "number", "label": "Increment", "default": 1},
        "position": {"type": "select", "label": "Position", "options": ["first", "last"], "default": "first"},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        field = config.get("field_name", "record_id")
        start = int(config.get("start", 1))
        increment = int(config.get("increment", 1))
        ids = pd.RangeIndex(len(df)) * increment + start
        if config.get("position", "first") == "first":
            df.insert(0, field, ids)
        else:
            df[field] = ids
        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_with_id")
        field = config.get("field_name", "record_id")
        start = config.get("start", 1)
        inc = config.get("increment", 1)
        return (
            f"{out_var} = {in_var}.copy()\n"
            f"{out_var}.insert(0, \"{field}\", range({start}, {start} + len({out_var}) * {inc}, {inc}))"
        )


class DataCleansingTool(BaseTool):
    tool_type = "data_cleansing"
    display_name = "Data Cleansing"
    category = "Preparation"
    description = "Apply common cleaning operations to selected fields."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "fields": {"type": "multi_field_selector", "label": "Fields to cleanse (empty = all string fields)"},
        "trim_whitespace": {"type": "checkbox", "label": "Trim whitespace", "default": True},
        "collapse_whitespace": {"type": "checkbox", "label": "Collapse repeated whitespace", "default": False},
        "to_case": {"type": "select", "label": "Convert case", "options": ["none", "upper", "lower", "title"], "default": "none"},
        "fill_null_strings": {"type": "text", "label": "Replace null strings with", "default": ""},
        "remove_null_rows": {"type": "checkbox", "label": "Remove fully null rows", "default": False},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        target_fields = config.get("fields") or [c for c in df.columns if df[c].dtype == object]

        for col in target_fields:
            if col not in df.columns:
                continue
            if df[col].dtype == object:
                if config.get("trim_whitespace", True):
                    df[col] = df[col].str.strip()
                if config.get("collapse_whitespace"):
                    df[col] = df[col].str.replace(r"\s+", " ", regex=True)
                case = config.get("to_case", "none")
                if case == "upper":
                    df[col] = df[col].str.upper()
                elif case == "lower":
                    df[col] = df[col].str.lower()
                elif case == "title":
                    df[col] = df[col].str.title()
                fill = config.get("fill_null_strings", "")
                if fill is not None:
                    df[col] = df[col].fillna(fill)

        if config.get("remove_null_rows"):
            df = df.dropna(how="all")

        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_clean")
        lines = [f"{out_var} = {in_var}.copy()"]
        fields = config.get("fields") or []
        field_expr = repr(fields) if fields else f"[c for c in {out_var}.columns if {out_var}[c].dtype == object]"
        lines.append(f"for _col in {field_expr}:")
        if config.get("trim_whitespace", True):
            lines.append(f'    {out_var}[_col] = {out_var}[_col].str.strip()')
        case = config.get("to_case", "none")
        if case != "none":
            lines.append(f'    {out_var}[_col] = {out_var}[_col].str.{case}()')
        return "\n".join(lines)


class SampleTool(BaseTool):
    tool_type = "sample"
    display_name = "Sample"
    category = "Preparation"
    description = "Select a reproducible subset of records."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "mode": {"type": "select", "label": "Mode", "options": ["first_n", "last_n", "random_n", "random_pct", "every_nth"], "default": "first_n"},
        "n": {"type": "number", "label": "N / percentage", "default": 100},
        "random_seed": {"type": "number", "label": "Random seed", "default": 42},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame())
        mode = config.get("mode", "first_n")
        n = int(config.get("n", 100))
        seed = int(config.get("random_seed", 42))

        if mode == "first_n":
            out = df.head(n)
        elif mode == "last_n":
            out = df.tail(n)
        elif mode == "random_n":
            out = df.sample(min(n, len(df)), random_state=seed)
        elif mode == "random_pct":
            out = df.sample(frac=min(n, 100) / 100, random_state=seed)
        elif mode == "every_nth":
            out = df.iloc[::n]
        else:
            out = df
        return {"out": out.copy()}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_sample")
        mode = config.get("mode", "first_n")
        n = config.get("n", 100)
        seed = config.get("random_seed", 42)
        if mode == "first_n":
            return f"{out_var} = {in_var}.head({n}).copy()"
        elif mode == "random_n":
            return f"{out_var} = {in_var}.sample({n}, random_state={seed}).copy()"
        elif mode == "random_pct":
            return f"{out_var} = {in_var}.sample(frac={n/100}, random_state={seed}).copy()"
        else:
            return f"{out_var} = {in_var}.head({n}).copy()"
