from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from constants import PANEL_BG, DIM_FG, RESULT_OUTLINE, TEXT_FG
from nodes import get_tool
from column_inference import infer_columns


class PropertiesPanel:
    def __init__(self, parent: tk.Widget, app) -> None:
        self.parent = parent
        self.app = app
        self.current_node = None
        self._show_empty()

    def _show_empty(self) -> None:
        for w in self.parent.winfo_children():
            w.destroy()
        ttk.Label(self.parent, text="Select a node\nto configure",
                  justify="center", foreground=DIM_FG).pack(expand=True)

    def show_node(self, node) -> None:
        self.current_node = node
        self._rebuild()

    def clear(self) -> None:
        self.current_node = None
        self._show_empty()

    def refresh(self) -> None:
        if self.current_node:
            self._rebuild()

    def _rebuild(self) -> None:
        node = self.current_node
        if not node:
            self._show_empty()
            return

        for w in self.parent.winfo_children():
            w.destroy()

        tool = get_tool(node.kind)
        if not tool:
            ttk.Label(self.parent, text=f"Unknown: {node.kind}").pack()
            return

        # ── Title strip ──────────────────────────────────────────────────
        title_bar = tk.Frame(self.parent, bg=tool.color, height=32)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text=tool.display_name, bg=tool.color,
                 fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)
        tk.Label(title_bar, text=f"id:{node.id}", bg=tool.color,
                 fg="#cccccc", font=("Segoe UI", 7)).pack(side="right", padx=6)

        # ── Scrollable config area ────────────────────────────────────────
        outer = ttk.Frame(self.parent)
        outer.pack(fill="both", expand=True)

        cv = tk.Canvas(outer, bg=PANEL_BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        cfg = ttk.Frame(cv)
        cfg.columnconfigure(1, weight=1)
        win_id = cv.create_window((0, 0), window=cfg, anchor="nw")

        def _resize_cfg(event=None):
            cv.configure(scrollregion=cv.bbox("all"))
            cv.itemconfigure(win_id, width=cv.winfo_width())

        cfg.bind("<Configure>", _resize_cfg)
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win_id, width=cv.winfo_width()))

        def _wheel(event):
            cv.yview_scroll(int(-1 * (event.delta / 120)), "units")
        cv.bind("<MouseWheel>", _wheel)

        # ── Column inference (per port) ───────────────────────────────────
        if len(tool.ins) == 0:
            columns: object = []
        elif len(tool.ins) == 1:
            columns = infer_columns(node.id, tool.ins[0],
                                    self.app.nodes, self.app.edges)
        else:
            # Multi-input: pass dict keyed by port name
            columns = {
                port: infer_columns(node.id, port, self.app.nodes, self.app.edges)
                for port in tool.ins
            }

        # We keep a reference so the code preview can be refreshed
        code_text_ref: list[tk.Text] = []

        def on_change() -> None:
            self.app.mark_dirty()
            self.app.redraw()
            if code_text_ref:
                _update_code(code_text_ref[0], node)

        tool.build_config(cfg, node.params, on_change, columns)

        # ── Result info ───────────────────────────────────────────────────
        if node.result:
            r = cfg.grid_size()[1]
            ttk.Separator(cfg, orient="horizontal").grid(
                row=r, column=0, columnspan=2, sticky="ew", pady=4)
            for port, df in node.result.items():
                if hasattr(df, "__len__") and hasattr(df, "columns"):
                    r = cfg.grid_size()[1]
                    ttk.Label(cfg, text=f"{port}:",
                              foreground=RESULT_OUTLINE).grid(
                        row=r, column=0, sticky="w", padx=4)
                    ttk.Label(cfg, text=f"{len(df):,} rows × {len(df.columns)} cols",
                              foreground=RESULT_OUTLINE).grid(
                        row=r, column=1, sticky="w", padx=4)

        # ── Live code preview ─────────────────────────────────────────────
        r = cfg.grid_size()[1]
        ttk.Separator(cfg, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        r = cfg.grid_size()[1]
        ttk.Label(cfg, text="Generated code:", foreground=DIM_FG).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=4)
        r = cfg.grid_size()[1]

        code_frame = ttk.Frame(cfg)
        code_frame.grid(row=r, column=0, columnspan=2, sticky="ew", padx=4, pady=2)
        code_frame.columnconfigure(0, weight=1)

        code_text = tk.Text(code_frame, height=5, bg="#0d0d1a", fg="#88ccff",
                            font=("Courier New", 8), state="disabled",
                            relief="flat", wrap="none")
        hscroll = ttk.Scrollbar(code_frame, orient="horizontal",
                                 command=code_text.xview)
        code_text.configure(xscrollcommand=hscroll.set)
        code_text.grid(row=0, column=0, sticky="ew")
        hscroll.grid(row=1, column=0, sticky="ew")

        code_text_ref.append(code_text)
        _update_code(code_text, node)

        # ── Delete button ─────────────────────────────────────────────────
        r = cfg.grid_size()[1]
        ttk.Button(cfg, text="Delete Node",
                   command=lambda n=node: self.app.delete_node(n)).grid(
            row=r, column=0, columnspan=2, sticky="ew", padx=4, pady=(10, 4))


def _update_code(code_text: tk.Text, node) -> None:
    tool = get_tool(node.kind)
    if not tool:
        return
    placeholder_inputs = [f"df_{p}" for p in tool.ins]
    try:
        lines = tool.to_code(node.params, placeholder_inputs, "result")
    except Exception as e:
        lines = [f"# error: {e}"]
    code_text.configure(state="normal")
    code_text.delete("1.0", "end")
    code_text.insert("1.0", "\n".join(lines))
    code_text.configure(state="disabled")
