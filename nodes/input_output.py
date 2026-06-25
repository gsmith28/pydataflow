"""Input / Output tool nodes: Import CSV, Import Excel, Show Table, Export CSV, Export Excel."""
from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from nodes.base import BaseTool
from constants import DELIM_MAP


class ImportCSV(BaseTool):
    node_type = "import_csv"
    display_name = "Import CSV"
    color = "#2d9e5a"
    ins = []
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_file_picker(parent, "File", "file_path", params, on_change, 0,
                             filetypes=[("CSV / Text", "*.csv *.txt *.tsv"), ("All", "*.*")])
        self.add_combobox(parent, "Delimiter", "delimiter", ["comma", "tab", "pipe", "semicolon", "custom"],
                          params, on_change, 1)
        self.add_entry(parent, "Custom delim", "custom_delim", params, on_change, 2, width=4)
        self.add_checkbox(parent, "Skip blank lines", "skip_blank", params, on_change, 3)

    def execute(self, params, inputs, log):
        path = params.get("file_path", "")
        if not path or not os.path.exists(path):
            raise ValueError(f"File not found: {path}")
        dm = params.get("delimiter", "comma")
        sep = DELIM_MAP.get(dm, params.get("custom_delim", ",") or ",")
        df = pd.read_csv(path, sep=sep, skip_blank_lines=bool(params.get("skip_blank", True)))
        log(f"Loaded {len(df)} rows × {len(df.columns)} cols from {os.path.basename(path)}")
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        path = params.get("file_path", "")
        # to_code emits a literal string, so \t must be escaped for the output script
        code_delim_map = {**DELIM_MAP, "tab": "\\t"}
        dm = params.get("delimiter", "comma")
        sep = code_delim_map.get(dm, params.get("custom_delim", ",") or ",")
        skip = "True" if params.get("skip_blank", True) else "False"
        return [f'{output_var} = pd.read_csv(r"{path}", sep="{sep}", skip_blank_lines={skip})']

    def subtitle(self, params):
        p = params.get("file_path", "")
        return os.path.basename(p) if p else "no file"


class ImportExcel(BaseTool):
    node_type = "import_excel"
    display_name = "Import Excel"
    color = "#2d9e5a"
    ins = []
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        self.add_file_picker(parent, "File", "file_path", params, on_change, 0,
                             filetypes=[("Excel", "*.xlsx *.xls *.xlsm"), ("All", "*.*")])
        self.add_entry(parent, "Sheet", "sheet_name", params, on_change, 1)

    def execute(self, params, inputs, log):
        path = params.get("file_path", "")
        if not path or not os.path.exists(path):
            raise ValueError(f"File not found: {path}")
        sheet = params.get("sheet_name") or 0
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
        log(f"Loaded {len(df)} rows × {len(df.columns)} cols")
        return {"data": df}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        path = params.get("file_path", "")
        sheet = params.get("sheet_name") or 0
        sheet_arg = f'"{sheet}"' if isinstance(sheet, str) and sheet else str(sheet)
        return [f'{output_var} = pd.read_excel(r"{path}", sheet_name={sheet_arg}, engine="openpyxl")']

    def subtitle(self, params):
        p = params.get("file_path", "")
        return os.path.basename(p) if p else "no file"


class ShowTable(BaseTool):
    node_type = "show_table"
    display_name = "Show Table"
    color = "#2d9e5a"
    ins = ["data"]
    outs = ["data"]

    def build_config(self, parent, params, on_change, columns=None):
        ttk.Label(parent, text="Opens a pop-out data viewer\nwhen the flow is run.").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        self.add_entry(parent, "Max rows", "max_rows", params, on_change, 1, width=8)
        params.setdefault("max_rows", "500")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None or not isinstance(df, pd.DataFrame):
            raise ValueError("No input data")
        limit = int(params.get("max_rows") or 500)
        log(f"Show Table: {len(df)} rows × {len(df.columns)} cols")
        # Pop-out viewer is triggered by app.py after execution
        return {"data": df, "_show_viewer": df.head(limit)}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        return [f"print({iv})", f"{output_var} = {iv}"]

    def subtitle(self, params):
        return f"max {params.get('max_rows', 500)} rows"


class ExportCSV(BaseTool):
    node_type = "export_csv"
    display_name = "Export CSV"
    color = "#2d9e5a"
    ins = ["data"]
    outs = []

    def build_config(self, parent, params, on_change, columns=None):
        self.add_file_picker(parent, "Output file", "file_path", params, on_change, 0,
                             filetypes=[("CSV", "*.csv"), ("All", "*.*")],
                             save=True, default_ext=".csv")
        self.add_checkbox(parent, "Include index", "include_index", params, on_change, 1)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input data")
        path = params.get("file_path", "")
        if not path:
            raise ValueError("No output file specified")
        idx = bool(params.get("include_index", False))
        df.to_csv(path, index=idx)
        log(f"Exported {len(df)} rows to {os.path.basename(path)}")
        return {}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        path = params.get("file_path", "output.csv")
        idx = str(bool(params.get("include_index", False)))
        return [f'{iv}.to_csv(r"{path}", index={idx})']

    def subtitle(self, params):
        p = params.get("file_path", "")
        return os.path.basename(p) if p else "no file"


class ExportExcel(BaseTool):
    node_type = "export_excel"
    display_name = "Export Excel"
    color = "#2d9e5a"
    ins = ["data"]
    outs = []

    def build_config(self, parent, params, on_change, columns=None):
        self.add_file_picker(parent, "Output file", "file_path", params, on_change, 0,
                             filetypes=[("Excel", "*.xlsx"), ("All", "*.*")],
                             save=True, default_ext=".xlsx")
        self.add_entry(parent, "Sheet name", "sheet_name", params, on_change, 1)
        params.setdefault("sheet_name", "Sheet1")

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input data")
        path = params.get("file_path", "")
        if not path:
            raise ValueError("No output file specified")
        sheet = params.get("sheet_name") or "Sheet1"
        df.to_excel(path, sheet_name=sheet, index=False, engine="openpyxl")
        log(f"Exported {len(df)} rows to {os.path.basename(path)}")
        return {}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        path = params.get("file_path", "output.xlsx")
        sheet = params.get("sheet_name") or "Sheet1"
        return [f'{iv}.to_excel(r"{path}", sheet_name="{sheet}", index=False, engine="openpyxl")']

    def subtitle(self, params):
        p = params.get("file_path", "")
        return os.path.basename(p) if p else "no file"
