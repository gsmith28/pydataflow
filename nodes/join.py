"""Join / Reconcile tool nodes: MergeJoin, Union, UniqueDuplicate."""
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
        # columns may be a dict {"left": [...], "right": [...]} or a list
        if isinstance(columns, dict):
            left_cols  = columns.get("left",  [])
            right_cols = columns.get("right", [])
        else:
            left_cols = right_cols = (columns or [])

        params.setdefault("how", "inner")
        params.setdefault("key_pairs", [])

        self.add_combobox(parent, "Join type", "how",
                          ["inner", "left", "right", "outer"],
                          params, on_change, 0)

        # Join type help text
        help_text = {
            "inner": "inner — only matched rows",
            "left":  "left  — all left rows + matches",
            "right": "right — all right rows + matches",
            "outer": "outer — all rows from both sides",
        }
        help_lbl = ttk.Label(parent, text=help_text.get(params.get("how", "inner"), ""),
                             foreground="#7878a0", font=("Segoe UI", 7))
        help_lbl.grid(row=1, column=0, columnspan=2, sticky="w", padx=4)

        ttk.Separator(parent, orient="horizontal").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Label(parent, text="Join keys:").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 2))

        container = ttk.Frame(parent)
        container.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4)
        parent.columnconfigure(1, weight=1)

        key_pairs: list[dict] = params["key_pairs"]

        def rebuild() -> None:
            for w in container.winfo_children():
                w.destroy()
            n = len(key_pairs)

            for i, pair in enumerate(key_pairs):
                # When multiple pairs, show ordinal number
                num_suffix = f" ({i+1})" if n > 1 else ""
                rf = ttk.Frame(container)
                rf.pack(fill="x", pady=1)

                ttk.Label(rf, text=f"Left key{num_suffix}", width=11).pack(side="left")
                lk_var = tk.StringVar(value=pair.get("left_key", ""))
                def _lk(*_, p=pair, v=lk_var): p["left_key"] = v.get(); on_change()
                lk_var.trace_add("write", _lk)
                ttk.Combobox(rf, textvariable=lk_var, values=left_cols,
                             width=13).pack(side="left", padx=(0, 4))

                ttk.Label(rf, text=f"Right{num_suffix}", width=6).pack(side="left")
                rk_var = tk.StringVar(value=pair.get("right_key", ""))
                def _rk(*_, p=pair, v=rk_var): p["right_key"] = v.get(); on_change()
                rk_var.trace_add("write", _rk)
                ttk.Combobox(rf, textvariable=rk_var, values=right_cols,
                             width=13).pack(side="left", padx=(0, 2))

                def _rm(idx=i): key_pairs.pop(idx); rebuild(); on_change()
                ttk.Button(rf, text="×", width=2, command=_rm).pack(side="left")

            def _add():
                key_pairs.append({"left_key": "", "right_key": ""})
                rebuild(); on_change()
            ttk.Button(container, text="+ Add key pair", command=_add).pack(anchor="w", pady=(4, 0))

        rebuild()

    def _get_keys(self, params):
        pairs = params.get("key_pairs", [])
        lk = [p["left_key"]  for p in pairs if p.get("left_key")]
        rk = [p["right_key"] for p in pairs if p.get("right_key")]
        return lk, rk

    def execute(self, params, inputs, log):
        left  = inputs.get("left")
        right = inputs.get("right")
        if left is None or right is None:
            raise ValueError("Need both left and right inputs connected")
        how = params.get("how", "inner")
        lk, rk = self._get_keys(params)
        if not lk:
            raise ValueError("No join keys specified")
        merged = pd.merge(left, right, left_on=lk, right_on=rk,
                          how="outer", indicator=True)
        if how == "inner":
            joined = merged[merged["_merge"] == "both"]
        elif how == "left":
            joined = merged[merged["_merge"].isin(["both", "left_only"])]
        elif how == "right":
            joined = merged[merged["_merge"].isin(["both", "right_only"])]
        else:
            joined = merged
        joined     = joined.drop(columns=["_merge"]).reset_index(drop=True)
        left_only  = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"]).reset_index(drop=True)
        right_only = merged[merged["_merge"] == "right_only"].drop(columns=["_merge"]).reset_index(drop=True)
        log(f"Join: {len(joined)} joined, {len(left_only)} left-only, {len(right_only)} right-only")
        return {"joined": joined, "left_unmatched": left_only, "right_unmatched": right_only}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        lv  = input_vars[0] if len(input_vars) > 0 else "df_left"
        rv  = input_vars[1] if len(input_vars) > 1 else "df_right"
        how = params.get("how", "inner")
        lk, rk = self._get_keys(params)
        outs = connected_outs or ["joined"]
        lines = []
        if {"left_unmatched", "right_unmatched"} & set(outs):
            lines.append(f"_m = pd.merge({lv}, {rv}, left_on={lk!r}, right_on={rk!r}, how='outer', indicator=True)")
            if "joined" in outs:
                incl = {"inner": ["both"], "left": ["both","left_only"],
                        "right": ["both","right_only"]}.get(how, None)
                if incl is None:
                    lines.append(f"{output_var}_joined = _m.drop(columns=['_merge']).reset_index(drop=True)")
                else:
                    lines.append(f"{output_var}_joined = _m[_m['_merge'].isin({incl!r})].drop(columns=['_merge']).reset_index(drop=True)")
            if "left_unmatched" in outs:
                lines.append(f"{output_var}_left_unmatched = _m[_m['_merge']=='left_only'].drop(columns=['_merge']).reset_index(drop=True)")
            if "right_unmatched" in outs:
                lines.append(f"{output_var}_right_unmatched = _m[_m['_merge']=='right_only'].drop(columns=['_merge']).reset_index(drop=True)")
        else:
            lines.append(f"{output_var}_joined = pd.merge({lv}, {rv}, left_on={lk!r}, right_on={rk!r}, how='{how}').reset_index(drop=True)")
        return lines

    def subtitle(self, params):
        lk, _ = self._get_keys(params)
        how = params.get("how", "inner")
        return f"{how}  {len(lk)} key(s)" if lk else f"{how} join"


class Union(BaseTool):
    node_type = "union"
    display_name = "Union"
    color = "#a03070"
    ins = ["top", "bottom"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_combobox(parent, "Match by", "match_by",
                          ["name", "position"], params, on_change, 0)
        self.add_checkbox(parent, "Add _source column", "add_source", params, on_change, 1)
        # Show column preview from each side if available
        if isinstance(columns, dict):
            top_cols  = columns.get("top", [])
            bot_cols  = columns.get("bottom", [])
            if top_cols or bot_cols:
                ttk.Separator(parent, orient="horizontal").grid(
                    row=2, column=0, columnspan=2, sticky="ew", pady=4)
                ttk.Label(parent,
                          text=f"Top columns ({len(top_cols)}): {', '.join(top_cols[:5])}{'…' if len(top_cols)>5 else ''}",
                          foreground="#7878a0", font=("Segoe UI", 7), wraplength=240).grid(
                    row=3, column=0, columnspan=2, sticky="w", padx=4)
                ttk.Label(parent,
                          text=f"Bot columns ({len(bot_cols)}): {', '.join(bot_cols[:5])}{'…' if len(bot_cols)>5 else ''}",
                          foreground="#7878a0", font=("Segoe UI", 7), wraplength=240).grid(
                    row=4, column=0, columnspan=2, sticky="w", padx=4)

    def execute(self, params, inputs, log):
        top = inputs.get("top")
        bot = inputs.get("bottom")
        frames = [f for f in [top, bot] if f is not None]
        if not frames:
            raise ValueError("No input data")
        if params.get("match_by", "name") == "position" and len(frames) == 2:
            bot2 = bot.copy()
            bot2.columns = list(top.columns[:len(bot.columns)])
            frames = [top, bot2]
        if params.get("add_source"):
            if top is not None:
                t = top.copy(); t["_source"] = "top"
            else:
                t = None
            if bot is not None:
                b = bot.copy(); b["_source"] = "bottom"
            else:
                b = None
            frames = [f for f in [t, b] if f is not None]
        result = pd.concat(frames, ignore_index=True)
        log(f"Union: {len(result)} rows total")
        return {"data": result}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        tv = input_vars[0] if len(input_vars) > 0 else "df_top"
        bv = input_vars[1] if len(input_vars) > 1 else "df_bottom"
        src = params.get("add_source", False)
        if src:
            return [
                f'_top = {tv}.copy(); _top["_source"] = "top"',
                f'_bot = {bv}.copy(); _bot["_source"] = "bottom"',
                f"{output_var} = pd.concat([_top, _bot], ignore_index=True)",
            ]
        return [f"{output_var} = pd.concat([{tv}, {bv}], ignore_index=True)"]

    def subtitle(self, params):
        return f"by {params.get('match_by','name')}"


class UniqueDuplicate(BaseTool):
    node_type = "unique_duplicate"
    display_name = "Unique / Duplicate"
    color = "#a03070"
    ins = ["data"]
    outs = ["unique", "duplicate"]

    def build_config(self, parent, params, on_change, columns=None):
        cols = columns if isinstance(columns, list) else []
        self.add_column_multiselect(parent, "Key columns", "key_columns",
                                    params, on_change, 0, cols)
        self.add_combobox(parent, "Keep", "keep",
                          ["first", "last", "none"], params, on_change, 1)
        self.add_checkbox(parent, "Add dup-group ID", "add_group_id", params, on_change, 2)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        keys = params.get("key_columns", [])
        if isinstance(keys, str):
            keys = [c.strip() for c in keys.split(",") if c.strip()]
        subset   = keys if keys else None
        keep     = params.get("keep", "first")
        keep_val = keep if keep in ("first", "last") else False
        dup_mask = df.duplicated(subset=subset, keep=keep_val)
        unique_df = df[~dup_mask].reset_index(drop=True)
        dup_df    = df[dup_mask].reset_index(drop=True)
        if params.get("add_group_id") and subset and len(dup_df):
            dup_df = dup_df.copy()
            dup_df["_dup_group"] = dup_df.groupby(subset).ngroup()
        log(f"Unique: {len(unique_df)}, Duplicate: {len(dup_df)}")
        return {"unique": unique_df, "duplicate": dup_df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv   = input_vars[0] if input_vars else "df"
        keys = params.get("key_columns", [])
        keep = params.get("keep", "first")
        subset_arg = f"subset={keys!r}" if keys else ""
        keep_arg   = f"keep='{keep}'" if keep in ("first","last") else "keep=False"
        args  = ", ".join(filter(None, [subset_arg, keep_arg]))
        outs  = connected_outs or ["unique", "duplicate"]
        lines = [f"_dup_mask = {iv}.duplicated({args})"]
        if "unique"    in outs: lines.append(f"{output_var}_unique    = {iv}[~_dup_mask].reset_index(drop=True)")
        if "duplicate" in outs: lines.append(f"{output_var}_duplicate = {iv}[_dup_mask].reset_index(drop=True)")
        return lines

    def subtitle(self, params):
        keys = params.get("key_columns", [])
        return f"{len(keys)} key(s)" if isinstance(keys, list) and keys else "all cols"
