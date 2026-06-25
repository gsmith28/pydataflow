from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import export_script
import project_io
from canvas_controller import CanvasController
from constants import (
    CANVAS_BG,
    CATEGORIES,
    CONTAINER_DEFAULT_H,
    CONTAINER_DEFAULT_W,
    DARK_BG,
    DIM_FG,
    ENTRY_BG,
    NODE_H,
    NODE_W,
    PANEL_BG,
    SELECT_OUTLINE,
    TEXT_FG,
    TOOL_COLORS,
)
from engine import Edge, Node, execute_flow
from nodes import all_tools, get_tool
from properties import PropertiesPanel
from renderer import Renderer


class FlowApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("PyDataFlow")
        self.root.geometry("1400x820")
        self.root.minsize(900, 600)

        # ── State ──────────────────────────────────────────────────────────
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []
        self.nodes_by_id: dict[str, Node] = {}

        self.selected_ids: set[str] = set()
        self.selected_edge_ids: set[str] = set()
        self.hover_port: tuple | None = None

        self.zoom: float = 1.0
        self.pan_x: float = 40.0
        self.pan_y: float = 40.0

        # drag
        self.drag_node: Node | None = None
        self.drag_offset_x: float = 0.0
        self.drag_offset_y: float = 0.0
        self.drag_children: list[Node] = []
        self.drag_child_offsets: dict = {}

        # wire
        self.wire_start_node: Node | None = None
        self.wire_start_port: str | None = None
        self.wire_start_dir: str | None = None
        self.wire_pos: tuple | None = None

        # pan
        self.panning: bool = False
        self.pan_start: tuple = (0, 0)
        self.pan_start_off: tuple = (0.0, 0.0)

        # resize
        self.resizing: Node | None = None
        self.resize_start_mouse: tuple = (0, 0)
        self.resize_start_size: tuple = (0, 0)

        # project
        self.project_path: str | None = None
        self._dirty: bool = False

        # palette drag-to-canvas
        self.palette_drag_kind: str | None = None
        self.palette_drag_ghost: tk.Toplevel | None = None

        self.controller = CanvasController(self)

        self._apply_theme()
        self._build_ui()
        self.renderer = Renderer(self.canvas)
        self.root.after(50, self.redraw)

    # ── Theme ───────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        bg, fg, entry, sel = DARK_BG, TEXT_FG, ENTRY_BG, "#3a3a5a"
        btn, btn_a = "#353548", "#454560"
        style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 9))
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure(
            "TButton", background=btn, foreground=fg, borderwidth=1, relief="flat", padding=(6, 3)
        )
        style.map("TButton", background=[("active", btn_a)])
        style.configure("Accent.TButton", background="#3a6fa8", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#4a8fc8")])
        style.configure("TEntry", fieldbackground=entry, foreground=fg, insertcolor=fg)
        style.configure("TCombobox", fieldbackground=entry, foreground=fg, selectbackground=sel)
        style.map("TCombobox", fieldbackground=[("readonly", entry)])
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.map("TCheckbutton", background=[("active", bg)])
        style.configure("TScrollbar", background=PANEL_BG, troughcolor=bg, arrowcolor=fg)
        style.configure(
            "Treeview", background=entry, foreground=fg, fieldbackground=entry, rowheight=22
        )
        style.configure("Treeview.Heading", background=PANEL_BG, foreground=fg, relief="flat")
        style.map("Treeview", background=[("selected", sel)])
        style.configure("TNotebook", background=bg)
        style.configure("TNotebook.Tab", background=PANEL_BG, foreground=fg, padding=(8, 4))
        style.map("TNotebook.Tab", background=[("selected", sel)])
        style.configure("TPanedwindow", background="#111120")
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TSeparator", background="#3a3a5a")
        self.root.configure(bg=bg)

    # ── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Toolbar
        tb = tk.Frame(self.root, bg="#15152a", height=40)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)
        self._build_toolbar(tb)

        # Bottom log / preview — packed before the canvas area so it anchors to bottom
        bottom = ttk.Notebook(self.root)
        self._log_text = self._make_log_tab(bottom)
        self._preview_frame = self._make_preview_tab(bottom)
        bottom.pack(fill="x", side="bottom", ipady=4)
        self._log_notebook = bottom

        # Separator between canvas and log
        sep = tk.Frame(self.root, bg="#3a3a5a", height=2)
        sep.pack(fill="x", side="bottom")

        # Top area (horizontal: palette | canvas | props) fills remaining space
        top = tk.PanedWindow(
            self.root, orient="horizontal", bg="#111120", sashwidth=5, sashrelief="flat"
        )
        top.pack(fill="both", expand=True)
        self._top_pane = top

        # Left palette
        pal_outer = tk.Frame(top, bg=PANEL_BG, width=200)
        self._build_palette(pal_outer)
        top.add(pal_outer, minsize=160, width=200)

        # Canvas
        canvas_frame = tk.Frame(top, bg=CANVAS_BG)
        self.canvas = tk.Canvas(
            canvas_frame, bg=CANVAS_BG, highlightthickness=0, cursor="crosshair"
        )
        self.canvas.pack(fill="both", expand=True)
        top.add(canvas_frame, minsize=400)

        # Right properties
        props_outer = tk.Frame(top, bg=PANEL_BG, width=280)
        self.props_panel = PropertiesPanel(props_outer, self)
        top.add(props_outer, minsize=220, width=280)

        self.controller.bind_canvas()

        # Set horizontal sash positions once window dimensions are known
        self.root.bind("<Configure>", self._on_first_configure)
        self._sash_set = False

    def _on_first_configure(self, _event=None) -> None:
        if self._sash_set:
            return
        w = self.root.winfo_width()
        if w < 100:
            return
        self._sash_set = True
        self._top_pane.sash_place(0, 200, 0)
        self._top_pane.sash_place(1, w - 285, 0)

    def _build_toolbar(self, tb: tk.Frame) -> None:
        def btn(text, cmd, accent=False, pad=2):
            style = "Accent.TButton" if accent else "TButton"
            b = ttk.Button(tb, text=text, command=cmd, style=style)
            b.pack(side="left", padx=pad, pady=4)
            return b

        btn("▶  Run", self.run_flow, accent=True)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=4, pady=6)
        btn("Open", self.open_project)
        btn("Save", self.save_project)
        btn("Save As", self.save_project_as)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=4, pady=6)
        btn("Export .py", self.export_python)
        btn("Clear", self.clear_canvas)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=4, pady=6)
        btn("Fit", self.controller.fit_view)
        btn("1:1", self.controller.reset_zoom)

        self._title_var = tk.StringVar(value="PyDataFlow — untitled")
        tk.Label(
            tb, textvariable=self._title_var, bg="#15152a", fg=DIM_FG, font=("Segoe UI", 9)
        ).pack(side="right", padx=12)

    def _build_palette(self, parent: tk.Frame) -> None:
        header = tk.Label(
            parent,
            text="NODES",
            bg=PANEL_BG,
            fg=DIM_FG,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
            padx=8,
        )
        header.pack(fill="x")

        # Scrollable area
        cv = tk.Canvas(parent, bg=PANEL_BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(fill="both", expand=True)

        inner = tk.Frame(cv, bg=PANEL_BG)
        win = cv.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e=None):
            cv.configure(scrollregion=cv.bbox("all"))
            cv.itemconfigure(win, width=cv.winfo_width())

        inner.bind("<Configure>", _resize)
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=cv.winfo_width()))

        def _wheel(e):
            cv.yview_scroll(int(-1 * (e.delta / 120)), "units")

        cv.bind("<MouseWheel>", _wheel)

        tool_map = {t.node_type: t for t in all_tools()}
        for cat_name, kinds in CATEGORIES:
            cat_lbl = tk.Label(
                inner,
                text=cat_name.upper(),
                bg=PANEL_BG,
                fg=DIM_FG,
                font=("Segoe UI", 7, "bold"),
                anchor="w",
                padx=6,
                pady=4,
            )
            cat_lbl.pack(fill="x", pady=(8, 0))
            for kind in kinds:
                tool = tool_map.get(kind)
                if not tool:
                    continue
                color = TOOL_COLORS.get(kind, "#4a4a70")

                row = tk.Frame(inner, bg=PANEL_BG, cursor="fleur")
                row.pack(fill="x", padx=4, pady=1)
                indicator = tk.Frame(row, bg=color, width=4)
                indicator.pack(side="left", fill="y")
                lbl = tk.Label(
                    row,
                    text=tool.display_name,
                    bg=PANEL_BG,
                    fg=TEXT_FG,
                    font=("Segoe UI", 9),
                    anchor="w",
                    padx=6,
                    pady=4,
                    cursor="fleur",
                )
                lbl.pack(side="left", fill="x", expand=True)

                # Drag-to-canvas: press starts ghost, release on canvas adds node
                for widget in (row, lbl):
                    widget.bind(
                        "<ButtonPress-1>",
                        lambda e, k=kind, c=color: self._palette_drag_start(e, k, c),
                    )
                    widget.bind("<B1-Motion>", self._palette_drag_motion)
                    widget.bind("<ButtonRelease-1>", self._palette_drag_release)

                row.bind("<Enter>", lambda e, r=row: r.configure(bg="#333350"))
                row.bind("<Leave>", lambda e, r=row: r.configure(bg=PANEL_BG))
                lbl.bind("<Enter>", lambda e, r=row: r.configure(bg="#333350"))
                lbl.bind("<Leave>", lambda e, r=row: r.configure(bg=PANEL_BG))

    def _make_log_tab(self, nb: ttk.Notebook) -> tk.Text:
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Log  ")
        text = tk.Text(
            frame,
            bg="#0d0d1a",
            fg=TEXT_FG,
            font=("Courier New", 8),
            state="disabled",
            relief="flat",
            height=6,
        )
        sb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        return text

    def _make_preview_tab(self, nb: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Preview  ")
        return frame

    # ── Graph operations ─────────────────────────────────────────────────────

    def add_node(self, kind: str, x: float, y: float) -> Node:
        get_tool(kind)
        node = Node(kind, x, y)
        if kind == "container":
            node.params.setdefault("_w", CONTAINER_DEFAULT_W)
            node.params.setdefault("_h", CONTAINER_DEFAULT_H)
            node.params.setdefault("title", "Group")
            node.params.setdefault("color", "#404060")
            node.params.setdefault("_children", [])
        self.nodes.append(node)
        self.nodes_by_id[node.id] = node
        self._update_node_membership(node)
        self.mark_dirty()
        self._select_node(node)
        self.redraw()
        return node

    def delete_node(self, node: Node) -> None:
        self.edges = [e for e in self.edges if e.src_node != node.id and e.dst_node != node.id]
        for c in self.nodes:
            if c.kind == "container":
                kids = c.params.get("_children")
                if kids and node.id in kids:
                    kids.remove(node.id)
        self.nodes.remove(node)
        self.nodes_by_id.pop(node.id, None)
        self.selected_ids.discard(node.id)
        self.props_panel.clear()
        self.mark_dirty()
        self.redraw()

    def toggle_disabled(self, node: Node) -> None:
        node.disabled = not node.disabled
        self.mark_dirty()
        self.redraw()
        self.props_panel.refresh()

    def _add_edge(self, src: Node, src_port: str, dst: Node, dst_port: str) -> None:
        # Remove any existing edge to this input port
        self.edges = [
            e for e in self.edges if not (e.dst_node == dst.id and e.dst_port == dst_port)
        ]
        self.edges.append(Edge(src.id, src_port, dst.id, dst_port))
        self.mark_dirty()

    def _select_node(self, node: Node) -> None:
        self.selected_ids = {node.id}
        self.selected_edge_ids = set()
        self.props_panel.show_node(node)
        self._update_preview(node)

    def _deselect(self) -> None:
        self.selected_ids = set()
        self.selected_edge_ids = set()
        self.props_panel.clear()

    # ── Container ────────────────────────────────────────────────────────────

    def _container_children(self, container: Node) -> list[Node]:
        ids = container.params.get("_children", [])
        return [self.nodes_by_id[i] for i in ids if i in self.nodes_by_id]

    def _node_in_container(self, node: Node, container: Node) -> bool:
        w = container.params.get("_w", CONTAINER_DEFAULT_W)
        h = container.params.get("_h", CONTAINER_DEFAULT_H)
        return (
            container.x <= node.x <= container.x + w
            and container.y <= node.y <= container.y + h
        )

    def _container_containing(self, node: Node) -> Node | None:
        for c in self.nodes:
            if c.kind == "container" and c.id != node.id and self._node_in_container(node, c):
                return c
        return None

    def _update_node_membership(self, node: Node) -> None:
        """Recompute which container (if any) owns ``node`` based on its position.

        Called only when a node is added or actually dragged — never on container
        resize — so resizing a container never silently adopts a node beneath it.
        """
        if node.kind == "container":
            return
        for c in self.nodes:
            if c.kind == "container":
                kids = c.params.get("_children")
                if kids and node.id in kids:
                    kids.remove(node.id)
        parent = self._container_containing(node)
        if parent is not None:
            parent.params.setdefault("_children", []).append(node.id)
            self._grow_container_to_fit(parent)

    def _grow_container_to_fit(self, container: Node) -> None:
        """Expand the container so it fully encloses its children's footprint.

        Grow-only: a child dragged to or past an edge pushes the boundary out,
        but this never shrinks the container (manual resize handles that).
        """
        min_w, min_h = self._container_min_size(container)
        container.params["_w"] = max(container.params.get("_w", CONTAINER_DEFAULT_W), min_w)
        container.params["_h"] = max(container.params.get("_h", CONTAINER_DEFAULT_H), min_h)

    def _container_min_size(self, container: Node) -> tuple[float, float]:
        """Smallest (w, h) that still encloses every child node's footprint.

        The resize handle is the bottom-right corner, so the container's top-left
        stays put; the minimum is driven by how far each child extends right/down.
        Falls back to the absolute floor (80, 50) when there are no children.
        """
        children = self._container_children(container)
        if not children:
            return 80.0, 50.0
        pad = 12.0
        min_w = max(c.x + NODE_W - container.x for c in children) + pad
        min_h = max(c.y + NODE_H - container.y for c in children) + pad
        return max(80.0, min_w), max(50.0, min_h)

    def _collapse_container(self, container: Node) -> None:
        children = self._container_children(container)
        container.params["_child_offsets"] = {
            c.id: (c.x - container.x, c.y - container.y) for c in children
        }
        container.params["collapsed"] = True
        self.mark_dirty()

    def _expand_container(self, container: Node) -> None:
        offsets = container.params.get("_child_offsets", {})
        for node in self.nodes:
            if node.id in offsets:
                ox, oy = offsets[node.id]
                node.x = container.x + ox
                node.y = container.y + oy
        container.params["collapsed"] = False
        container.params.pop("_child_offsets", None)
        self.mark_dirty()

    # ── Palette drag-to-canvas ───────────────────────────────────────────────

    def _palette_drag_start(self, event, kind: str, color: str) -> None:
        self.palette_drag_kind = kind
        tool = get_tool(kind)
        ghost = tk.Toplevel(self.root)
        ghost.overrideredirect(True)
        try:
            ghost.attributes("-alpha", 0.80)
            ghost.attributes("-topmost", True)
        except Exception:
            pass
        tk.Label(
            ghost,
            text=f"  {tool.display_name}  ",
            bg=color,
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6,
            relief="flat",
        ).pack()
        ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        self.palette_drag_ghost = ghost

    def _palette_drag_motion(self, event) -> None:
        if self.palette_drag_ghost:
            self.palette_drag_ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
            # Highlight canvas edge when hovering over it
            cx = self.canvas.winfo_rootx()
            cy = self.canvas.winfo_rooty()
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            over = cx <= event.x_root <= cx + cw and cy <= event.y_root <= cy + ch
            self.canvas.configure(
                highlightthickness=2 if over else 0, highlightbackground=SELECT_OUTLINE
            )

    def _palette_drag_release(self, event) -> None:
        self.canvas.configure(highlightthickness=0)
        if self.palette_drag_ghost:
            self.palette_drag_ghost.destroy()
            self.palette_drag_ghost = None
        kind = self.palette_drag_kind
        self.palette_drag_kind = None
        if not kind:
            return
        cx = self.canvas.winfo_rootx()
        cy = self.canvas.winfo_rooty()
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cx <= event.x_root <= cx + cw and cy <= event.y_root <= cy + ch:
            sx = event.x_root - cx
            sy = event.y_root - cy
            wx, wy = self.controller.s2w(sx, sy)
            self.add_node(kind, wx, wy)

    # ── Redraw ───────────────────────────────────────────────────────────────

    def redraw(self) -> None:
        self.renderer.redraw(self)

    # ── Execution ────────────────────────────────────────────────────────────

    def run_flow(self) -> None:
        self._log_clear()
        self._log("Running flow…")
        try:
            execute_flow(self.nodes, self.edges, log=self._log)
            self._log("Done ✓")
        except Exception as e:
            self._log(f"Flow failed: {e}", "error")
        self.redraw()
        # Refresh properties to show result counts
        self.props_panel.refresh()
        # Show preview for selected node
        for nid in self.selected_ids:
            node = self.nodes_by_id.get(nid)
            if node:
                self._update_preview(node)
                # Auto-open table viewers for show_table nodes
                if node.kind == "show_table" and node.result:
                    df = node.result.get("_show_viewer") or node.result.get("data")
                    if df is not None and hasattr(df, "columns"):
                        _open_table_window(self.root, f"Show Table [{node.id}]", df)

    # ── Preview ──────────────────────────────────────────────────────────────

    def _update_preview(self, node: Node) -> None:
        for w in self._preview_frame.winfo_children():
            w.destroy()
        if not node.result:
            ttk.Label(
                self._preview_frame, text="No data — run the flow first.", foreground=DIM_FG
            ).pack(expand=True)
            return

        # Port buttons if multiple outputs
        ports = [(p, df) for p, df in node.result.items() if hasattr(df, "columns")]
        if not ports:
            ttk.Label(self._preview_frame, text="No tabular output.", foreground=DIM_FG).pack(
                expand=True
            )
            return

        if len(ports) > 1:
            btn_bar = ttk.Frame(self._preview_frame)
            btn_bar.pack(fill="x")
            for pname, pdf in ports:

                def show_port(df=pdf, lbl=pname):
                    self._render_preview_df(df, lbl)

                ttk.Button(btn_bar, text=pname, command=show_port).pack(side="left", padx=2, pady=2)

        self._render_preview_df(ports[0][1], ports[0][0])

    def _render_preview_df(self, df, label: str = "") -> None:
        # Clear existing tree
        for w in self._preview_frame.winfo_children():
            if isinstance(w, (ttk.Frame, tk.Frame)):
                if hasattr(w, "_is_tree_frame"):
                    w.destroy()

        cols = list(df.columns)
        frame = ttk.Frame(self._preview_frame)
        frame._is_tree_frame = True  # type: ignore
        frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(frame, columns=cols, show="headings", height=5)
        vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=max(60, min(180, len(str(col)) * 9)), minwidth=40)

        hs.pack(side="bottom", fill="x")
        vs.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        limit = min(200, len(df))
        for _, row in df.head(limit).iterrows():
            tree.insert("", "end", values=[str(v) if v is not None else "" for v in row])

        ttk.Label(
            self._preview_frame,
            text=f"{label}  {len(df):,} rows × {len(df.columns)} cols  (showing {limit})",
            foreground=DIM_FG,
            font=("Segoe UI", 8),
        ).pack(side="bottom")

    def show_table_viewer(self, node: Node) -> None:
        if not node.result:
            return
        for port, df in node.result.items():
            if hasattr(df, "columns"):
                tool = get_tool(node.kind)
                title = f"{tool.display_name if tool else node.kind} [{node.id}] — {port}"
                _open_table_window(self.root, title, df)
                break

    # ── Logging ──────────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info") -> None:
        t = self._log_text
        t.configure(state="normal")
        tag_colors = {"error": "#ff6666", "warning": "#ffaa44", "info": TEXT_FG}
        color = tag_colors.get(level, TEXT_FG)
        t.tag_configure(level, foreground=color)
        t.insert("end", msg + "\n", level)
        t.see("end")
        t.configure(state="disabled")

    def _log_clear(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ── Project operations ───────────────────────────────────────────────────

    def mark_dirty(self) -> None:
        self._dirty = True
        self._update_title()

    def _update_title(self) -> None:
        name = os.path.basename(self.project_path) if self.project_path else "untitled"
        dirty_star = " *" if self._dirty else ""
        self._title_var.set(f"PyDataFlow — {name}{dirty_star}")

    def save_project(self) -> None:
        if not self.project_path:
            self.save_project_as()
            return
        project_io.save_project(self.project_path, self.nodes, self.edges)
        self._dirty = False
        self._update_title()
        self._log(f"Saved: {self.project_path}")

    def save_project_as(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("PyDataFlow project", "*.json"), ("All", "*.*")],
            title="Save project",
        )
        if path:
            self.project_path = path
            self.save_project()

    def open_project(self) -> None:
        if self._dirty and not messagebox.askyesno("Unsaved changes", "Discard unsaved changes?"):
            return
        path = filedialog.askopenfilename(
            filetypes=[("PyDataFlow project", "*.json"), ("All", "*.*")],
            title="Open project",
        )
        if path:
            try:
                nodes, edges = project_io.load_project(path)
            except Exception as e:
                messagebox.showerror("Load error", str(e))
                return
            self.nodes = nodes
            self.edges = edges
            self.nodes_by_id = {n.id: n for n in nodes}
            self.project_path = path
            self._dirty = False
            self._update_title()
            self._deselect()
            self.controller.fit_view()

    def export_python(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python script", "*.py"), ("All", "*.*")],
            title="Export Python",
        )
        if path:
            code = export_script.generate_python(self.nodes, self.edges)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            self._log(f"Exported: {path}")

    def clear_canvas(self) -> None:
        if self._dirty and not messagebox.askyesno("Clear canvas", "Clear all nodes?"):
            return
        self.nodes.clear()
        self.edges.clear()
        self.nodes_by_id.clear()
        self._deselect()
        self._dirty = False
        self._update_title()
        self.redraw()

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.root.mainloop()


# ── Module-level table viewer (also used by main.py) ─────────────────────────


def _open_table_window(root: tk.Tk | tk.Toplevel, title: str, df) -> None:
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=PANEL_BG)
    win.geometry("900x520")

    cols = list(df.columns)
    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(frame, columns=cols, show="headings")
    vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hs = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

    for col in cols:
        tree.heading(col, text=str(col))
        tree.column(col, width=max(60, min(180, len(str(col)) * 9)), minwidth=40)

    hs.pack(side="bottom", fill="x")
    vs.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    limit = min(500, len(df))
    for _, row in df.head(limit).iterrows():
        tree.insert("", "end", values=[str(v) if v is not None else "" for v in row])

    ttk.Label(
        win,
        text=f"{len(df):,} rows × {len(df.columns)} cols  (showing {limit})",
        background=PANEL_BG,
        foreground=DIM_FG,
    ).pack(pady=4)
