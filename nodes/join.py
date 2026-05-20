from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import pandas as pd
from nodes.base import BaseTool


class MergeJoin(BaseTool):
    node_type = "merge_join"
    display_name = "Merge / Join"
    color = "#a03070"
    ins = ["left", "right"]
    outs = ["joined", "left_unmatched", "right_unmatched"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_combobox(parent, "Join type", "how",
                          ["inner", "left", "right", "outer"],
                          params, on_change, 0)
        ttk.Separator(parent, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Label(parent, text="Key pairs  (left_col = right_col):").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=4)
        self.add_textarea(parent, "", "key_pairs", params, on_change, 3, height=4)

    def _parse_keys(self, params):
        text = params.get("key_pairs", "")
        left_keys, right_keys = [], []
        for line in text.strip().splitlines():
            if "=" in line:
                lk, _, rk = line.partition("=")
                left_keys.append(lk.strip())
                right_keys.append(rk.strip())
        return left_keys, right_keys

    def execute(self, params, inputs, log):
        left = inputs.get("left")
        right = inputs.get("right")
        if left is None or right is None:
            raise ValueError("Need both left and right inputs")
        how = params.get("how", "inner")
        lk, rk = self._parse_keys(params)
        if not lk:
            raise ValueError("No join keys specified")
        merged = pd.merge(left, right, left_on=lk, right_on=rk, how="outer", indicator=True)
        joined = merged[merged["_merge"] != "right_only"].drop(columns=["_merge"])
        if how == "inner":
            joined = merged[merged["_merge"] == "both"].drop(columns=["_merge"])
        elif how == "left":
            joined = merged[merged["_merge"].isin(["both", "left_only"])].drop(columns=["_merge"])
        elif how == "right":
            joined = merged[merged["_merge"].isin(["both", "right_only"])].drop(columns=["_merge"])
        else:
            joined = merged.drop(columns=["_merge"])
        left_only = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
        right_only = merged[merged["_merge"] == "right_only"].drop(columns=["_merge"])
        log(f"Join: {len(joined)} joined, {len(left_only)} left-only, {len(right_only)} right-only")
        return {
            "joined": joined.reset_index(drop=True),
            "left_unmatched": left_only.reset_index(drop=True),
            "right_unmatched": right_only.reset_index(drop=True),
        }

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        lv = input_vars[0] if len(input_vars) > 0 else "df_left"
        rv = input_vars[1] if len(input_vars) > 1 else "df_right"
        how = params.get("how", "inner")
        lk, rk = self._parse_keys(params)
        outs = connected_outs or ["joined"]
        lines = []
        if len({"left_unmatched", "right_unmatched"} & set(outs)) > 0:
            lines.append(f"_m = pd.merge({lv}, {rv}, left_on={lk!r}, right_on={rk!r}, how='outer', indicator=True)")
            if "joined" in outs:
                flag = {"inner": "both", "left": "both|left_only", "right": "both|right_only"}.get(how, "both")
                if "|" in flag:
                    flags = flag.split("|")
                    lines.append(f"{output_var}_joined = _m[_m['_merge'].isin({flags!r})].drop(columns=['_merge']).reset_index(drop=True)")
                else:
                    lines.append(f"{output_var}_joined = _m[_m['_merge'] == '{flag}'].drop(columns=['_merge']).reset_index(drop=True)")
            if "left_unmatched" in outs:
                lines.append(f"{output_var}_left_unmatched = _m[_m['_merge'] == 'left_only'].drop(columns=['_merge']).reset_index(drop=True)")
            if "right_unmatched" in outs:
                lines.append(f"{output_var}_right_unmatched = _m[_m['_merge'] == 'right_only'].drop(columns=['_merge']).reset_index(drop=True)")
        else:
            lines.append(f"{output_var}_joined = pd.merge({lv}, {rv}, left_on={lk!r}, right_on={rk!r}, how='{how}').reset_index(drop=True)")
        return lines

    def subtitle(self, params):
        return params.get("how", "inner") + " join"


class Union(BaseTool):
    node_type = "union"
    display_name = "Union"
    color = "#a03070"
    ins = ["top", "bottom"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_combobox(parent, "Match by", "match_by",
                          ["name", "position"],
                          params, on_change, 0)
        self.add_checkbox(parent, "Add _source column", "add_source", params, on_change, 1)

    def execute(self, params, inputs, log):
        top = inputs.get("top")
        bot = inputs.get("bottom")
        frames = [f for f in [top, bot] if f is not None]
        if not frames:
            raise ValueError("No input data")
        if params.get("match_by", "name") == "position" and len(frames) == 2:
            bot_renamed = bot.copy()
            bot_renamed.columns = top.columns[:len(bot.columns)]
            frames = [top, bot_renamed]
        if params.get("add_source"):
            if top is not None:
                top = top.copy(); top["_source"] = "top"
            if bot is not None:
                bot = bot.copy(); bot["_source"] = "bottom"
            frames = [f for f in [top, bot] if f is not None]
        result = pd.concat(frames, ignore_index=True)
        log(f"Union: {len(result)} rows total")
        return {"data": result}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        tv = input_vars[0] if len(input_vars) > 0 else "df_top"
        bv = input_vars[1] if len(input_vars) > 1 else "df_bottom"
        src = params.get("add_source", False)
        lines = []
        if src:
            lines.append(f'_top = {tv}.copy(); _top["_source"] = "top"')
            lines.append(f'_bot = {bv}.copy(); _bot["_source"] = "bottom"')
            lines.append(f"{output_var} = pd.concat([_top, _bot], ignore_index=True)")
        else:
            lines.append(f"{output_var} = pd.concat([{tv}, {bv}], ignore_index=True)")
        return lines

    def subtitle(self, params):
        return f"by {params.get('match_by','name')}"


class UniqueDuplicate(BaseTool):
    node_type = "unique_duplicate"
    display_name = "Unique / Duplicate"
    color = "#a03070"
    ins = ["data"]
    outs = ["unique", "duplicate"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_column_multiselect(parent, "Key columns", "key_columns", params, on_change, 0, columns or [])
        self.add_combobox(parent, "Keep", "keep", ["first", "last", "none"], params, on_change, 1)
        self.add_checkbox(parent, "Add dup-group ID", "add_group_id", params, on_change, 2)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        keys = params.get("key_columns", [])
        if isinstance(keys, str):
            keys = [c.strip() for c in keys.split(",") if c.strip()]
        subset = keys if keys else None
        keep = params.get("keep", "first")
        keep_val = keep if keep in ("first", "last") else False
        dup_mask = df.duplicated(subset=subset, keep=keep_val)
        unique_df = df[~dup_mask].reset_index(drop=True)
        dup_df = df[dup_mask].reset_index(drop=True)
        if params.get("add_group_id") and subset and len(dup_df):
            dup_df = dup_df.copy()
            dup_df["_dup_group"] = dup_df.groupby(subset).ngroup()
        log(f"Unique: {len(unique_df)}, Duplicate: {len(dup_df)}")
        return {"unique": unique_df, "duplicate": dup_df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        keys = params.get("key_columns", [])
        keep = params.get("keep", "first")
        subset_arg = f"subset={keys!r}" if keys else ""
        keep_arg = f"keep='{keep}'" if keep in ("first", "last") else "keep=False"
        args = ", ".join(filter(None, [subset_arg, keep_arg]))
        outs = connected_outs or ["unique", "duplicate"]
        lines = [f"_dup_mask = {iv}.duplicated({args})"]
        if "unique" in outs:
            lines.append(f"{output_var}_unique = {iv}[~_dup_mask].reset_index(drop=True)")
        if "duplicate" in outs:
            lines.append(f"{output_var}_duplicate = {iv}[_dup_mask].reset_index(drop=True)")
        return lines

    def subtitle(self, params):
        keys = params.get("key_columns", [])
        if isinstance(keys, list) and keys:
            return f"{len(keys)} key(s)"
        return "all cols"
