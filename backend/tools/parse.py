from __future__ import annotations
from typing import Any
import pandas as pd
import re as _re
from tools.base import BaseTool, ExecutionContext, ToolError


class DateTimeParsetool(BaseTool):
    tool_type = "datetime_parse"
    display_name = "DateTime Parse / Format"
    category = "Parse / Standardize"
    description = "Convert strings to dates or dates to strings."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "source_field": {"type": "field_selector", "label": "Source field"},
        "target_field": {"type": "text", "label": "Target field (blank = overwrite source)"},
        "mode": {"type": "select", "label": "Mode", "options": ["string_to_datetime", "datetime_to_string"], "default": "string_to_datetime"},
        "input_format": {"type": "text", "label": "Input format (e.g. %Y-%m-%d)", "default": ""},
        "output_format": {"type": "text", "label": "Output format", "default": "%Y-%m-%d"},
        "error_handling": {"type": "select", "label": "On error", "options": ["coerce", "raise", "keep"], "default": "coerce"},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        src = config.get("source_field")
        tgt = config.get("target_field") or src
        mode = config.get("mode", "string_to_datetime")
        fmt_in = config.get("input_format") or None
        fmt_out = config.get("output_format", "%Y-%m-%d")
        on_err = config.get("error_handling", "coerce")

        if not src or src not in df.columns:
            return {"out": df}

        errors = "coerce" if on_err == "coerce" else "raise"

        if mode == "string_to_datetime":
            df[tgt] = pd.to_datetime(df[src], format=fmt_in, errors=errors)
        else:
            dt_series = pd.to_datetime(df[src], errors=errors)
            df[tgt] = dt_series.dt.strftime(fmt_out)

        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_parsed")
        src = config.get("source_field", "date_field")
        tgt = config.get("target_field") or src
        fmt = config.get("input_format", "")
        fmt_repr = f'"{fmt}"' if fmt else "None"
        return (
            f'{out_var} = {in_var}.copy()\n'
            f'{out_var}["{tgt}"] = pd.to_datetime({out_var}["{src}"], format={fmt_repr}, errors="coerce")'
        )


class TextToColumnsTool(BaseTool):
    tool_type = "text_to_columns"
    display_name = "Text to Columns"
    category = "Parse / Standardize"
    description = "Split a string field into multiple columns or rows."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "source_field": {"type": "field_selector", "label": "Source field"},
        "delimiter": {"type": "text", "label": "Delimiter", "default": ","},
        "mode": {"type": "select", "label": "Mode", "options": ["split_to_columns", "split_to_rows"], "default": "split_to_columns"},
        "max_splits": {"type": "number", "label": "Max output columns (0 = unlimited)", "default": 0},
        "output_prefix": {"type": "text", "label": "Output column prefix", "default": "part_"},
        "keep_original": {"type": "checkbox", "label": "Keep original field", "default": False},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        src = config.get("source_field")
        delim = config.get("delimiter", ",")
        mode = config.get("mode", "split_to_columns")
        max_splits = int(config.get("max_splits", 0))
        prefix = config.get("output_prefix", "part_")
        keep = config.get("keep_original", False)

        if not src or src not in df.columns:
            return {"out": df}

        n = max_splits if max_splits > 0 else -1

        if mode == "split_to_columns":
            split = df[src].astype(str).str.split(delim, n=n if n > 0 else 0, expand=True)
            split.columns = [f"{prefix}{i+1}" for i in range(len(split.columns))]
            df = pd.concat([df, split], axis=1)
            if not keep:
                df = df.drop(columns=[src])
        else:
            df = df.assign(**{src: df[src].astype(str).str.split(delim)}).explode(src).reset_index(drop=True)

        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_split")
        src = config.get("source_field", "field")
        delim = config.get("delimiter", ",")
        prefix = config.get("output_prefix", "part_")
        return (
            f"_split = {in_var}[\"{src}\"].astype(str).str.split(\"{delim}\", expand=True)\n"
            f"_split.columns = [\"{prefix}\" + str(i+1) for i in range(len(_split.columns))]\n"
            f"{out_var} = pd.concat([{in_var}, _split], axis=1)"
        )


class RegexTool(BaseTool):
    tool_type = "regex"
    display_name = "Regex"
    category = "Parse / Standardize"
    description = "Extract, match, replace, or tokenize text using regular expressions."
    input_ports = ["in"]
    output_ports = ["out"]
    config_schema = {
        "source_field": {"type": "field_selector", "label": "Source field"},
        "regex": {"type": "text", "label": "Regular expression"},
        "mode": {"type": "select", "label": "Mode", "options": ["extract", "match", "replace", "tokenize"], "default": "extract"},
        "output_fields": {"type": "text", "label": "Output field name(s) (comma-separated)", "default": "match_1"},
        "replacement": {"type": "text", "label": "Replacement text (for replace mode)", "default": ""},
        "case_insensitive": {"type": "checkbox", "label": "Case insensitive", "default": False},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        df = inputs.get("in", pd.DataFrame()).copy()
        src = config.get("source_field")
        pattern = config.get("regex", "")
        mode = config.get("mode", "extract")
        output_fields = [f.strip() for f in config.get("output_fields", "match_1").split(",")]
        replacement = config.get("replacement", "")
        flags = _re.IGNORECASE if config.get("case_insensitive") else 0

        if not src or not pattern or src not in df.columns:
            return {"out": df}

        series = df[src].astype(str)

        if mode == "extract":
            extracted = series.str.extract(pattern, flags=flags)
            extracted.columns = output_fields[:len(extracted.columns)]
            df = pd.concat([df, extracted], axis=1)
        elif mode == "match":
            df[output_fields[0]] = series.str.match(pattern, flags=flags)
        elif mode == "replace":
            df[output_fields[0] if output_fields else src] = series.str.replace(pattern, replacement, regex=True, flags=flags)
        elif mode == "tokenize":
            tokens = series.str.findall(pattern)
            df[output_fields[0]] = tokens

        return {"out": df}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        in_var = input_vars.get("in", "df")
        out_var = output_vars.get("out", "df_regex")
        src = config.get("source_field", "field")
        pattern = config.get("regex", "")
        mode = config.get("mode", "extract")
        out_fields = config.get("output_fields", "match_1")
        if mode == "extract":
            return (
                f"_extracted = {in_var}[\"{src}\"].astype(str).str.extract(r\"{pattern}\")\n"
                f"_extracted.columns = {repr([f.strip() for f in out_fields.split(',')])}\n"
                f"{out_var} = pd.concat([{in_var}, _extracted], axis=1)"
            )
        return f'{out_var} = {in_var}.copy()'
