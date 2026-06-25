"""
Base class and widget helpers for all PyDataFlow tool nodes.

Every tool is a subclass of BaseTool registered in nodes/__init__.py.
Subclasses must set the class attributes and override the three contract
methods: build_config, execute, to_code.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Any


class BaseTool:
    """Abstract base for all PyDataFlow tool nodes.

    Subclass contract
    -----------------
    Set class attributes:
        node_type     -- unique snake_case key used in the registry and .json files
        display_name  -- shown in the palette and node header
        color         -- hex colour for palette indicator and node border
        ins           -- ordered list of input port names, e.g. ["data"]
        outs          -- ordered list of output port names, e.g. ["true", "false"]

    Override the three contract methods:
        build_config  -- build tkinter widgets into the properties panel
        execute       -- run the transformation, return {port: DataFrame}
        to_code       -- return Python source lines for the export script

    Widget helpers (add_entry, add_combobox, etc.) handle widget layout and
    keep params in sync. Call them inside build_config.
    """

    node_type: str = ""
    display_name: str = ""
    color: str = "#4a9eff"
    ins: list[str] = []
    outs: list[str] = []
    is_visual_only: bool = False

    # --- contract methods ---------------------------------------------------

    def build_config(self, parent: tk.Widget, params: dict,
                     on_change, columns: list[str] | None = None) -> None:
        """Build the configuration UI for this tool into *parent*.

        *params* is mutated in place as the user edits widgets.
        *on_change* must be called after every param update so the canvas
        redraws the subtitle and marks the project dirty.
        *columns* is the list of column names inferred from upstream data;
        pass to column-aware widgets (dropdowns, multiselects).
        """

    def execute(self, params: dict, inputs: dict, log) -> dict:
        """Run the transformation and return outputs.

        *inputs* maps input port name → DataFrame (may be empty for source nodes).
        *log* is a callable: log(message: str, level: str = "info").

        Return a dict mapping output port name → DataFrame.
        Raise ValueError with a user-readable message on misconfiguration.
        """
        return {}

    def to_code(self, params: dict, input_vars: list[str],
                output_var: str, connected_outs: list[str] | None = None) -> list[str]:
        """Return Python source lines equivalent to execute() for export.

        *input_vars*     -- variable names for each input port (same order as self.ins)
        *output_var*     -- base variable name to assign outputs to
        *connected_outs* -- output port names that are wired downstream
                            (None means emit all ports)

        Multi-output nodes should suffix output_var with the port name,
        e.g. f"{output_var}_true" and f"{output_var}_false".
        """
        return []

    def subtitle(self, params: dict) -> str:
        """Return a short summary string shown below the node title on the canvas."""
        return ""

    # --- config-widget helpers (use inside build_config) --------------------

    def _lbl(self, parent: tk.Widget, text: str, row: int) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="nw", padx=(4, 2), pady=2)
        parent.columnconfigure(1, weight=1)

    def add_entry(self, parent: tk.Widget, label: str, key: str,
                  params: dict, on_change, row: int,
                  width: int = 22) -> tk.StringVar:
        var = tk.StringVar(value=str(params.get(key, "")))
        def _cb(*_):
            params[key] = var.get()
            on_change()
        var.trace_add("write", _cb)
        self._lbl(parent, label, row)
        ttk.Entry(parent, textvariable=var, width=width).grid(
            row=row, column=1, sticky="ew", padx=4, pady=2)
        return var

    def add_combobox(self, parent: tk.Widget, label: str, key: str,
                     values: list[str], params: dict, on_change,
                     row: int) -> tk.StringVar:
        cur = str(params.get(key, values[0] if values else ""))
        var = tk.StringVar(value=cur)
        def _cb(*_):
            params[key] = var.get()
            on_change()
        var.trace_add("write", _cb)
        self._lbl(parent, label, row)
        ttk.Combobox(parent, textvariable=var, values=values,
                     state="readonly").grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        return var

    def add_checkbox(self, parent: tk.Widget, label: str, key: str,
                     params: dict, on_change, row: int) -> tk.BooleanVar:
        var = tk.BooleanVar(value=bool(params.get(key, False)))
        def _cb(*_):
            params[key] = var.get()
            on_change()
        var.trace_add("write", _cb)
        ttk.Checkbutton(parent, text=label, variable=var).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        return var

    def add_file_picker(self, parent: tk.Widget, label: str, key: str,
                        params: dict, on_change, row: int,
                        filetypes: list | None = None,
                        save: bool = False,
                        default_ext: str = "") -> tk.StringVar:
        var = tk.StringVar(value=str(params.get(key, "")))
        def _cb(*_):
            params[key] = var.get()
            on_change()
        var.trace_add("write", _cb)

        def browse():
            ft = filetypes or [("All files", "*.*")]
            if save:
                p = filedialog.asksaveasfilename(filetypes=ft, defaultextension=default_ext)
            else:
                p = filedialog.askopenfilename(filetypes=ft)
            if p:
                var.set(p)

        self._lbl(parent, label, row)
        fr = ttk.Frame(parent)
        fr.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        fr.columnconfigure(0, weight=1)
        ttk.Entry(fr, textvariable=var).grid(row=0, column=0, sticky="ew")
        ttk.Button(fr, text="…", width=3, command=browse).grid(row=0, column=1, padx=(2, 0))
        return var

    def add_column_dropdown(self, parent: tk.Widget, label: str, key: str,
                             params: dict, on_change, row: int,
                             columns: list[str]) -> tk.StringVar:
        vals = columns or []
        cur = str(params.get(key, ""))
        var = tk.StringVar(value=cur)
        def _cb(*_):
            params[key] = var.get()
            on_change()
        var.trace_add("write", _cb)
        self._lbl(parent, label, row)
        cb = ttk.Combobox(parent, textvariable=var, values=vals)
        cb.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        return var

    def add_column_multiselect(self, parent: tk.Widget, label: str, key: str,
                                params: dict, on_change, row: int,
                                columns: list[str]) -> tk.Listbox:
        cols = columns or []
        current = params.get(key, [])
        if isinstance(current, str):
            current = [c.strip() for c in current.split(",") if c.strip()]

        self._lbl(parent, label, row)
        fr = ttk.Frame(parent)
        fr.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
        fr.columnconfigure(0, weight=1)

        lb = tk.Listbox(fr, selectmode=tk.MULTIPLE, height=5,
                        bg="#1a1a28", fg="#c0c0d8",
                        selectbackground="#5588ff", exportselection=False,
                        font=("Segoe UI", 8))
        sb = ttk.Scrollbar(fr, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.grid(row=0, column=0, sticky="ew")
        sb.grid(row=0, column=1, sticky="ns")

        for col in cols:
            lb.insert(tk.END, col)
        for i, col in enumerate(cols):
            if col in current:
                lb.selection_set(i)

        def on_sel(event=None):
            sel = [cols[i] for i in lb.curselection()]
            params[key] = sel
            on_change()

        lb.bind("<<ListboxSelect>>", on_sel)
        return lb

    def add_textarea(self, parent: tk.Widget, label: str, key: str,
                     params: dict, on_change, row: int,
                     height: int = 4) -> tk.Text:
        if label:
            self._lbl(parent, label, row)
            col = 1
        else:
            col = 0

        fr = ttk.Frame(parent)
        fr.grid(row=row, column=col, columnspan=(2 - col), sticky="ew", padx=4, pady=2)
        fr.columnconfigure(0, weight=1)

        ta = tk.Text(fr, height=height, bg="#1a1a28", fg="#c0c0d8",
                     insertbackground="#ffffff", font=("Segoe UI", 8), wrap="word",
                     relief="flat")
        sb = ttk.Scrollbar(fr, orient="vertical", command=ta.yview)
        ta.configure(yscrollcommand=sb.set)
        ta.grid(row=0, column=0, sticky="ew")
        sb.grid(row=0, column=1, sticky="ns")
        ta.insert("1.0", str(params.get(key, "")))

        def on_key(event=None):
            params[key] = ta.get("1.0", "end-1c")
            on_change()

        ta.bind("<KeyRelease>", on_key)
        return ta

    def add_dynamic_rows(self, parent: tk.Widget, key: str, params: dict,
                         on_change, fields: list[dict],
                         default_row: dict | None = None,
                         add_label: str = "+ Add row") -> None:
        """
        fields: list of {"key": str, "label": str, "type": "entry"|"combobox",
                          "values": [...], "width": int}
        """
        rows: list[dict] = params.setdefault(key, [])

        container = ttk.Frame(parent)
        container.grid(row=parent.grid_size()[1], column=0, columnspan=2,
                       sticky="ew", padx=4, pady=2)
        parent.columnconfigure(0, weight=1)

        def rebuild():
            for w in container.winfo_children():
                w.destroy()
            for ri, rdata in enumerate(rows):
                rf = ttk.Frame(container)
                rf.pack(fill="x", pady=1)
                for fi, fdef in enumerate(fields):
                    fkey = fdef["key"]
                    ftype = fdef.get("type", "entry")
                    fwidth = fdef.get("width", 10)
                    if ftype == "combobox":
                        fvals = fdef.get("values", [])
                        var = tk.StringVar(value=str(rdata.get(fkey, fvals[0] if fvals else "")))
                        def _cb(*_, r=rdata, k=fkey, v=var):
                            r[k] = v.get(); on_change()
                        var.trace_add("write", _cb)
                        ttk.Combobox(rf, textvariable=var, values=fvals,
                                     state="readonly", width=fwidth).pack(side="left", padx=1)
                    else:
                        var = tk.StringVar(value=str(rdata.get(fkey, "")))
                        def _cb(*_, r=rdata, k=fkey, v=var):
                            r[k] = v.get(); on_change()
                        var.trace_add("write", _cb)
                        ttk.Entry(rf, textvariable=var, width=fwidth).pack(side="left", padx=1)

                def remove_row(i=ri):
                    rows.pop(i)
                    rebuild()
                    on_change()
                ttk.Button(rf, text="×", width=2, command=remove_row).pack(side="left", padx=1)

            def add_row():
                rows.append(dict(default_row or {f["key"]: "" for f in fields}))
                rebuild()
                on_change()
            ttk.Button(container, text=add_label, command=add_row).pack(anchor="w", pady=(2, 0))

        rebuild()
