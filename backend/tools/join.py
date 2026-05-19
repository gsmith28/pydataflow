from __future__ import annotations
from typing import Any
import pandas as pd
from tools.base import BaseTool, ExecutionContext, ToolError


class JoinTool(BaseTool):
    tool_type = "join"
    display_name = "Join"
    category = "Join / Reconcile"
    description = "Join two data streams, producing matched and unmatched outputs."
    input_ports = ["left", "right"]
    output_ports = ["joined", "left_unmatched", "right_unmatched"]
    config_schema = {
        "left_keys": {"type": "multi_field_selector", "label": "Left join keys"},
        "right_keys": {"type": "multi_field_selector", "label": "Right join keys"},
        "join_type": {"type": "select", "label": "Join type", "options": ["inner", "left", "right", "outer"], "default": "inner"},
        "case_insensitive": {"type": "checkbox", "label": "Case-insensitive join", "default": False},
        "trim_keys": {"type": "checkbox", "label": "Trim key whitespace", "default": True},
        "left_suffix": {"type": "text", "label": "Left suffix for duplicates", "default": "_left"},
        "right_suffix": {"type": "text", "label": "Right suffix for duplicates", "default": "_right"},
    }

    def validate_config(self, config: dict, input_schemas: dict) -> list[str]:
        errors = []
        if not config.get("left_keys"):
            errors.append("Left join keys are required.")
        if not config.get("right_keys"):
            errors.append("Right join keys are required.")
        if len(config.get("left_keys", [])) != len(config.get("right_keys", [])):
            errors.append("Left and right key lists must have the same length.")
        return errors

    def _normalize_keys(self, df: pd.DataFrame, keys: list[str], case_insensitive: bool, trim: bool) -> pd.DataFrame:
        work = df.copy()
        for k in keys:
            if k in work.columns and work[k].dtype == object:
                if trim:
                    work[k] = work[k].str.strip()
                if case_insensitive:
                    work[k] = work[k].str.upper()
        return work

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        left = inputs.get("left", pd.DataFrame())
        right = inputs.get("right", pd.DataFrame())
        left_keys = config.get("left_keys", [])
        right_keys = config.get("right_keys", [])
        join_type = config.get("join_type", "inner")
        case_ins = config.get("case_insensitive", False)
        trim = config.get("trim_keys", True)
        left_suf = config.get("left_suffix", "_left")
        right_suf = config.get("right_suffix", "_right")

        lwork = self._normalize_keys(left, left_keys, case_ins, trim)
        rwork = self._normalize_keys(right, right_keys, case_ins, trim)

        left_idx = lwork.index
        right_idx = rwork.index

        merged_full = lwork.merge(
            rwork,
            left_on=left_keys,
            right_on=right_keys,
            how="outer",
            suffixes=(left_suf, right_suf),
            indicator=True,
        )

        both_mask = merged_full["_merge"] == "both"
        left_only_mask = merged_full["_merge"] == "left_only"
        right_only_mask = merged_full["_merge"] == "right_only"

        joined_full = merged_full[both_mask].drop(columns=["_merge"])
        left_unmatched_raw = merged_full[left_only_mask].drop(columns=["_merge"])
        right_unmatched_raw = merged_full[right_only_mask].drop(columns=["_merge"])

        if join_type == "inner":
            result = joined_full
        elif join_type == "left":
            result = merged_full[both_mask | left_only_mask].drop(columns=["_merge"])
        elif join_type == "right":
            result = merged_full[both_mask | right_only_mask].drop(columns=["_merge"])
        else:
            result = merged_full.drop(columns=["_merge"])

        left_unmatched_cols = [c for c in left_unmatched_raw.columns if c in left.columns or c.endswith(left_suf)]
        right_unmatched_cols = [c for c in right_unmatched_raw.columns if c in right.columns or c.endswith(right_suf)]

        return {
            "joined": result.reset_index(drop=True),
            "left_unmatched": left[~left.index.isin(
                lwork.merge(rwork, left_on=left_keys, right_on=right_keys, how="inner").index
            )].copy() if len(left) else pd.DataFrame(columns=left.columns),
            "right_unmatched": right[~right.index.isin(
                rwork.merge(lwork, left_on=right_keys, right_on=left_keys, how="inner").index
            )].copy() if len(right) else pd.DataFrame(columns=right.columns),
        }

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        left_var = input_vars.get("left", "left_df")
        right_var = input_vars.get("right", "right_df")
        joined_var = output_vars.get("joined", "joined")
        left_unm = output_vars.get("left_unmatched", "left_unmatched")
        right_unm = output_vars.get("right_unmatched", "right_unmatched")
        lk = config.get("left_keys", [])
        rk = config.get("right_keys", [])
        jtype = config.get("join_type", "inner")
        ls = config.get("left_suffix", "_left")
        rs = config.get("right_suffix", "_right")
        return (
            f"_merged = {left_var}.merge({right_var}, left_on={lk}, right_on={rk}, "
            f"how=\"outer\", suffixes=(\"{ls}\", \"{rs}\"), indicator=True)\n"
            f"{joined_var} = _merged[_merged['_merge'] == 'both'].drop(columns=['_merge']).reset_index(drop=True)\n"
            f"{left_unm} = _merged[_merged['_merge'] == 'left_only'].drop(columns=['_merge']).reset_index(drop=True)\n"
            f"{right_unm} = _merged[_merged['_merge'] == 'right_only'].drop(columns=['_merge']).reset_index(drop=True)"
        )


class UnionTool(BaseTool):
    tool_type = "union"
    display_name = "Union"
    category = "Join / Reconcile"
    description = "Combine multiple data streams vertically."
    input_ports = ["in_1", "in_2", "in_3"]
    output_ports = ["out"]
    config_schema = {
        "match_by": {"type": "select", "label": "Match columns by", "options": ["name", "position"], "default": "name"},
        "add_source_field": {"type": "checkbox", "label": "Add source input field", "default": False},
        "source_field_name": {"type": "text", "label": "Source field name", "default": "_source"},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        frames = []
        add_source = config.get("add_source_field", False)
        source_field = config.get("source_field_name", "_source")

        for port_name in sorted(inputs.keys()):
            df = inputs[port_name].copy()
            if add_source:
                df[source_field] = port_name
            frames.append(df)

        if not frames:
            return {"out": pd.DataFrame()}

        match_by = config.get("match_by", "name")
        if match_by == "name":
            out = pd.concat(frames, ignore_index=True)
        else:
            out = pd.concat([f.reset_index(drop=True) for f in frames], ignore_index=True)

        return {"out": out}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        out_var = output_vars.get("out", "df_union")
        frame_list = list(input_vars.values())
        return f"{out_var} = pd.concat([{', '.join(frame_list)}], ignore_index=True)"


class FindReplaceLookupTool(BaseTool):
    tool_type = "find_replace_lookup"
    display_name = "Find / Replace / Lookup"
    category = "Join / Reconcile"
    description = "Match values from a lookup table and append or replace fields."
    input_ports = ["data", "lookup"]
    output_ports = ["out", "unmatched"]
    config_schema = {
        "data_field": {"type": "field_selector", "label": "Data field to match"},
        "lookup_key_field": {"type": "field_selector", "label": "Lookup key field"},
        "lookup_value_fields": {"type": "multi_field_selector", "label": "Fields to append from lookup"},
        "match_mode": {"type": "select", "label": "Match mode", "options": ["exact", "contains", "starts_with", "ends_with"], "default": "exact"},
        "case_sensitive": {"type": "checkbox", "label": "Case sensitive", "default": True},
    }

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict, context: ExecutionContext) -> dict[str, pd.DataFrame]:
        data = inputs.get("data", pd.DataFrame()).copy()
        lookup = inputs.get("lookup", pd.DataFrame())
        data_field = config.get("data_field")
        lookup_key = config.get("lookup_key_field")
        value_fields = config.get("lookup_value_fields", [])

        if not data_field or not lookup_key:
            return {"out": data, "unmatched": pd.DataFrame(columns=data.columns)}

        if config.get("match_mode", "exact") == "exact":
            cols_to_use = [lookup_key] + [f for f in value_fields if f in lookup.columns]
            merged = data.merge(
                lookup[cols_to_use],
                left_on=data_field,
                right_on=lookup_key,
                how="left",
                indicator=True,
            )
            matched = merged[merged["_merge"] == "both"].drop(columns=["_merge"])
            unmatched = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
            if lookup_key != data_field and lookup_key in matched.columns:
                matched = matched.drop(columns=[lookup_key])
                unmatched = unmatched.drop(columns=[lookup_key])
            return {"out": matched.reset_index(drop=True), "unmatched": unmatched.reset_index(drop=True)}

        return {"out": data, "unmatched": pd.DataFrame(columns=data.columns)}

    def generate_python(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        data_var = input_vars.get("data", "data_df")
        lookup_var = input_vars.get("lookup", "lookup_df")
        out_var = output_vars.get("out", "df_looked_up")
        df = config.get("data_field", "field")
        lk = config.get("lookup_key_field", "key")
        return (
            f"{out_var} = {data_var}.merge({lookup_var}, left_on=\"{df}\", right_on=\"{lk}\", how=\"left\")"
        )
