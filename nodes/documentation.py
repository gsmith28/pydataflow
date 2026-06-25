"""Documentation tool nodes: Comment and Container.

These are visual-only nodes (is_visual_only = True) — they have no input/output
ports and never participate in data flow or code export.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk

from nodes.base import BaseTool


class Comment(BaseTool):
    node_type = "comment"
    display_name = "Comment"
    color = "#5a5a8a"
    ins = []
    outs = []
    is_visual_only = True

    def build_config(self, parent, params, on_change, columns=None):
        self.add_entry(parent, "Title", "title", params, on_change, 0)
        self.add_textarea(parent, "Text", "text", params, on_change, 1, height=6)

    def execute(self, params, inputs, log):
        return {}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        lines = []
        title = params.get("title", "").strip()
        text = params.get("text", "").strip()
        if title:
            lines.append(f"# {title}")
        for line in text.splitlines():
            lines.append(f"# {line}")
        return lines

    def subtitle(self, params):
        title = params.get("title", "")
        return title[:30] if title else "no title"


class Container(BaseTool):
    node_type = "container"
    display_name = "Container"
    color = "#404060"
    ins = []
    outs = []
    is_visual_only = True

    def build_config(self, parent, params, on_change, columns=None):
        self.add_entry(parent, "Title", "title", params, on_change, 0)
        self.add_entry(parent, "Description", "description", params, on_change, 1)

        # Color picker
        tk.Label(parent, text="Color").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        color_frame = ttk.Frame(parent)
        color_frame.grid(row=2, column=1, sticky="ew", padx=4, pady=2)

        tk.StringVar(value=params.get("color", "#404060"))
        preview_lbl = tk.Label(
            color_frame, bg=params.get("color", "#404060"), width=4, relief="flat"
        )
        preview_lbl.pack(side="left", padx=(0, 4))

        def pick_color():
            c = colorchooser.askcolor(color=params.get("color", "#404060"), title="Container color")
            if c and c[1]:
                params["color"] = c[1]
                preview_lbl.configure(bg=c[1])
                on_change()

        ttk.Button(color_frame, text="Choose…", command=pick_color).pack(side="left")

        params.setdefault("title", "Group")
        params.setdefault("color", "#404060")

    def execute(self, params, inputs, log):
        return {}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        title = params.get("title", "Container")
        desc = params.get("description", "")
        lines = [f"# --- {title} ---"]
        if desc:
            lines.append(f"# {desc}")
        return lines

    def subtitle(self, params):
        return params.get("title", "")
