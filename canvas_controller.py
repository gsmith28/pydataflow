from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from constants import (
    CONTAINER_DEFAULT_H,
    CONTAINER_DEFAULT_W,
    NODE_H,
    NODE_W,
    PANEL_BG,
    TEXT_FG,
)
from nodes import get_tool

if TYPE_CHECKING:
    from app import FlowApp


class CanvasController:
    """Canvas view interaction: zoom, pan, and screen↔world coordinate transforms.

    Interaction state (``zoom``, ``pan_x``, ``pan_y``, ``panning`` …) lives on
    ``FlowApp`` because ``renderer.py`` reads it directly each frame; this
    controller operates on that shared state rather than owning a private copy.
    """

    def __init__(self, app: FlowApp) -> None:
        self.app = app
        self._drag_moved = False

    # ── Coordinate helpers ────────────────────────────────────────────────
    def s2w(self, sx: float, sy: float) -> tuple[float, float]:
        app = self.app
        return (sx - app.pan_x) / app.zoom, (sy - app.pan_y) / app.zoom

    # ── Pan (middle mouse button) ─────────────────────────────────────────
    def start_pan(self, event) -> None:
        app = self.app
        app.panning = True
        app.pan_start = (event.x, event.y)
        app.pan_start_off = (app.pan_x, app.pan_y)

    def do_pan(self, event) -> None:
        app = self.app
        app.pan_x = app.pan_start_off[0] + event.x - app.pan_start[0]
        app.pan_y = app.pan_start_off[1] + event.y - app.pan_start[1]
        app.redraw()

    # ── Zoom (mouse wheel) ────────────────────────────────────────────────
    def on_scroll(self, event) -> None:
        self.scroll_delta(event, event.delta)

    def scroll_delta(self, event, delta: int) -> None:
        app = self.app
        factor = 1.1 if delta > 0 else (1 / 1.1)
        new_zoom = max(0.15, min(4.0, app.zoom * factor))
        wx = (event.x - app.pan_x) / app.zoom
        wy = (event.y - app.pan_y) / app.zoom
        app.pan_x = event.x - wx * new_zoom
        app.pan_y = event.y - wy * new_zoom
        app.zoom = new_zoom
        app.redraw()

    # ── View framing ──────────────────────────────────────────────────────
    def fit_view(self) -> None:
        app = self.app
        if not app.nodes:
            app.pan_x, app.pan_y, app.zoom = 40, 40, 1.0
            app.redraw()
            return
        margin = 60
        xs = [n.x for n in app.nodes]
        ys = [n.y for n in app.nodes]
        x_min, x_max = min(xs), max(xs) + NODE_W + 100
        y_min, y_max = min(ys), max(ys) + NODE_H + 60
        cw = app.canvas.winfo_width() or 800
        ch = app.canvas.winfo_height() or 500
        available_w = cw - 2 * margin
        available_h = ch - 2 * margin
        world_w = x_max - x_min
        world_h = y_max - y_min
        if world_w < 1 or world_h < 1:
            app.zoom = 1.0
        else:
            app.zoom = max(0.15, min(2.0, min(available_w / world_w, available_h / world_h)))
        app.pan_x = margin - x_min * app.zoom
        app.pan_y = margin - y_min * app.zoom
        app.redraw()

    def reset_zoom(self) -> None:
        self.app.zoom = 1.0
        self.app.redraw()

    # ── Event binding ─────────────────────────────────────────────────────
    def bind_canvas(self) -> None:
        c = self.app.canvas
        c.bind("<Button-1>", self.on_click)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-2>", self.start_pan)
        c.bind("<B2-Motion>", self.do_pan)
        c.bind("<Button-3>", self.on_right_click)
        c.bind("<Double-Button-1>", self.on_double_click)
        c.bind("<MouseWheel>", self.on_scroll)  # Windows / macOS
        c.bind("<Button-4>", lambda e: self.scroll_delta(e, 120))  # Linux up
        c.bind("<Button-5>", lambda e: self.scroll_delta(e, -120))  # Linux down

    # ── Click / drag / release ────────────────────────────────────────────
    def on_click(self, event) -> None:
        app = self.app
        node, hit, port = app.renderer.hit_test(app, event.x, event.y)

        if hit == "port_out":
            app.wire_start_node = node
            app.wire_start_port = port
            app.wire_start_dir = "out"
            app.wire_pos = (event.x, event.y)
        elif hit == "port_in":
            app.wire_start_node = node
            app.wire_start_port = port
            app.wire_start_dir = "in"
            app.wire_pos = (event.x, event.y)
        elif hit == "resize" and node:
            app.resizing = node
            app.resize_start_mouse = (event.x, event.y)
            app.resize_start_size = (
                node.params.get("_w", CONTAINER_DEFAULT_W),
                node.params.get("_h", CONTAINER_DEFAULT_H),
            )
        elif hit in ("title", "body") and node:
            app._select_node(node)
            wx, wy = self.s2w(event.x, event.y)
            app.drag_node = node
            self._drag_moved = False
            app.drag_offset_x = wx - node.x
            app.drag_offset_y = wy - node.y
            if node.kind == "container" and not node.params.get("collapsed"):
                app.drag_children = app._container_children(node)
                app.drag_child_offsets = {
                    c.id: (c.x - node.x, c.y - node.y) for c in app.drag_children
                }
            else:
                app.drag_children = []
        else:
            app._deselect()
            app.panning = True
            app.pan_start = (event.x, event.y)
            app.pan_start_off = (app.pan_x, app.pan_y)
        app.redraw()

    def on_drag(self, event) -> None:
        app = self.app
        if app.wire_start_node:
            app.wire_pos = (event.x, event.y)
            n, hit, port = app.renderer.hit_test(app, event.x, event.y)
            app.hover_port = (
                (n.id, port, "in" if hit == "port_in" else "out")
                if n and hit in ("port_in", "port_out")
                else None
            )
            app.redraw()
        elif app.drag_node:
            self._drag_moved = True
            wx, wy = self.s2w(event.x, event.y)
            app.drag_node.x = wx - app.drag_offset_x
            app.drag_node.y = wy - app.drag_offset_y
            for child in app.drag_children:
                ox, oy = app.drag_child_offsets[child.id]
                child.x = app.drag_node.x + ox
                child.y = app.drag_node.y + oy
            app.mark_dirty()
            app.redraw()
        elif app.panning:
            app.pan_x = app.pan_start_off[0] + event.x - app.pan_start[0]
            app.pan_y = app.pan_start_off[1] + event.y - app.pan_start[1]
            app.redraw()
        elif app.resizing:
            dx = (event.x - app.resize_start_mouse[0]) / app.zoom
            dy = (event.y - app.resize_start_mouse[1]) / app.zoom
            min_w, min_h = app._container_min_size(app.resizing)
            app.resizing.params["_w"] = max(min_w, app.resize_start_size[0] + dx)
            app.resizing.params["_h"] = max(min_h, app.resize_start_size[1] + dy)
            app.mark_dirty()
            app.redraw()
        else:
            n, hit, port = app.renderer.hit_test(app, event.x, event.y)
            new_hp = (
                (n.id, port, "in" if hit == "port_in" else "out")
                if n and hit in ("port_in", "port_out")
                else None
            )
            if new_hp != app.hover_port:
                app.hover_port = new_hp
                app.redraw()

    def on_release(self, event) -> None:
        app = self.app
        if app.wire_start_node:
            n, hit, port = app.renderer.hit_test(app, event.x, event.y)
            if n and hit in ("port_in", "port_out"):
                src_n, src_p, src_d = (
                    app.wire_start_node,
                    app.wire_start_port,
                    app.wire_start_dir,
                )
                dst_d = "in" if hit == "port_in" else "out"
                if src_d == "out" and dst_d == "in":
                    app._add_edge(src_n, src_p, n, port)
                elif src_d == "in" and dst_d == "out":
                    app._add_edge(n, port, src_n, src_p)
        dragged = app.drag_node
        if dragged is not None and self._drag_moved and dragged.kind != "container":
            app._update_node_membership(dragged)
        self.reset_interaction()
        app.redraw()

    def reset_interaction(self) -> None:
        app = self.app
        app.wire_start_node = None
        app.wire_start_port = None
        app.wire_start_dir = None
        app.wire_pos = None
        app.drag_node = None
        app.drag_children = []
        app.panning = False
        app.resizing = None
        app.hover_port = None

    # ── Context menu / double-click ───────────────────────────────────────
    def on_right_click(self, event) -> None:
        app = self.app
        node, hit, port = app.renderer.hit_test(app, event.x, event.y)
        menu = tk.Menu(
            app.root,
            tearoff=0,
            bg=PANEL_BG,
            fg=TEXT_FG,
            activebackground="#3a3a5a",
            activeforeground=TEXT_FG,
        )
        if node:
            tool = get_tool(node.kind)
            menu.add_command(
                label=f"{tool.display_name if tool else node.kind}  [{node.id}]", state="disabled"
            )
            menu.add_separator()
            menu.add_command(label="Delete", command=lambda: app.delete_node(node))
            label = "Enable" if node.disabled else "Disable"
            menu.add_command(label=label, command=lambda: app.toggle_disabled(node))
            if node.result:
                menu.add_command(label="View data…", command=lambda: app.show_table_viewer(node))
        else:
            menu.add_command(label="Fit view", command=self.fit_view)
            menu.add_command(label="Reset zoom", command=self.reset_zoom)
            wx, wy = self.s2w(event.x, event.y)
            menu.add_separator()
            menu.add_command(
                label="Add Comment here", command=lambda: app.add_node("comment", wx, wy)
            )
            menu.add_command(
                label="Add Container here", command=lambda: app.add_node("container", wx, wy)
            )
        menu.post(event.x_root, event.y_root)

    def on_double_click(self, event) -> None:
        app = self.app
        node, hit, _ = app.renderer.hit_test(app, event.x, event.y)
        if node and node.kind == "container" and hit == "title":
            if node.params.get("collapsed"):
                app._expand_container(node)
            else:
                app._collapse_container(node)
            app.redraw()
