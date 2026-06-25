"""
Canvas renderer for PyDataFlow.

Redraws the entire tkinter Canvas on every call to Renderer.redraw().
Handles: background grid, container boxes, bezier edge wires, nodes
(with ports, title, subtitle, result badge), and the in-progress wire
while the user is dragging a connection.

Also provides Renderer.hit_test() which maps a screen-space mouse
coordinate back to (node, hit_type, port_name).
"""

from __future__ import annotations

import tkinter as tk

from constants import (
    CONTAINER_DEFAULT_H,
    CONTAINER_DEFAULT_W,
    DIM_FG,
    EDGE_COLOR,
    EDGE_WIRE,
    GRID_COLOR,
    NODE_BG,
    NODE_H,
    NODE_W,
    PORT_IN_COLOR,
    PORT_OUT_COLOR,
    PORT_R,
    RESULT_OUTLINE,
    SELECT_OUTLINE,
    TITLE_H,
)
from nodes import get_tool


def bezier_pts(p0, p1, p2, p3, steps: int = 20) -> list:
    """Return flat [x0, y0, x1, y1, ...] for cubic bezier curve."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.extend([x, y])
    return pts


class Renderer:
    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas

    # ── coordinate helpers ────────────────────────────────────────────────

    def w2s(self, app, x: float, y: float) -> tuple[float, float]:
        return x * app.zoom + app.pan_x, y * app.zoom + app.pan_y

    def port_world(self, node, port_name: str, direction: str) -> tuple[float, float]:
        tool = get_tool(node.kind)
        if tool is None:
            return node.x, node.y
        ports = tool.ins if direction == "in" else tool.outs
        try:
            idx = ports.index(port_name)
        except ValueError:
            idx = 0
        count = max(len(ports), 1)

        if node.kind == "container":
            w = node.params.get("_w", CONTAINER_DEFAULT_W)
            px = node.x if direction == "in" else node.x + w
            py = node.y + TITLE_H / 2
            return px, py

        body_h = NODE_H - TITLE_H
        py = node.y + TITLE_H + body_h * (idx + 1) / (count + 1)
        px = node.x if direction == "in" else node.x + NODE_W
        return px, py

    def port_screen(self, app, node, port_name: str, direction: str) -> tuple[float, float]:
        wx, wy = self.port_world(node, port_name, direction)
        return self.w2s(app, wx, wy)

    # ── main redraw ───────────────────────────────────────────────────────

    def redraw(self, app) -> None:
        c = self.canvas
        c.delete("all")
        self._draw_grid(app)

        containers = [n for n in app.nodes if n.kind == "container"]
        regular = [n for n in app.nodes if n.kind != "container"]
        hidden = _hidden_ids(app)

        for node in containers:
            self._draw_container_body(app, node)

        for edge in app.edges:
            self._draw_edge(app, edge, hidden)

        for node in regular:
            if node.id not in hidden:
                self._draw_node(app, node)

        for node in containers:
            self._draw_container_bar(app, node)
            if node.params.get("collapsed"):
                self._draw_proxy_edges(app, node, hidden)

        if app.wire_start_node and app.wire_pos:
            self._draw_wire(app)

    # ── grid ──────────────────────────────────────────────────────────────

    def _draw_grid(self, app) -> None:
        c = self.canvas
        W = c.winfo_width() or 800
        H = c.winfo_height() or 600
        spacing = max(4, 40 * app.zoom)
        x0 = app.pan_x % spacing
        y0 = app.pan_y % spacing
        x = x0
        while x < W:
            y = y0
            while y < H:
                c.create_rectangle(x, y, x + 1, y + 1, fill=GRID_COLOR, outline="")
                y += spacing
            x += spacing

    # ── container ─────────────────────────────────────────────────────────

    def _draw_container_body(self, app, node) -> None:
        if node.params.get("collapsed"):
            return
        w = node.params.get("_w", CONTAINER_DEFAULT_W)
        h = node.params.get("_h", CONTAINER_DEFAULT_H)
        sx, sy = self.w2s(app, node.x, node.y)
        sw, sh = w * app.zoom, h * app.zoom
        th = TITLE_H * app.zoom
        color = node.params.get("color", "#404060")
        self.canvas.create_rectangle(
            sx, sy + th, sx + sw, sy + sh, fill="#1a1a2c", outline=color, dash=(4, 4), width=1
        )
        # Resize handle
        self.canvas.create_rectangle(
            sx + sw - 12,
            sy + sh - 12,
            sx + sw,
            sy + sh,
            fill=color,
            outline="",
            tags=(f"resize_{node.id}",),
        )

    def _draw_container_bar(self, app, node) -> None:
        w = node.params.get("_w", CONTAINER_DEFAULT_W)
        sx, sy = self.w2s(app, node.x, node.y)
        sw = w * app.zoom
        th = TITLE_H * app.zoom
        color = node.params.get("color", "#404060")
        sel = node.id in app.selected_ids
        outline, lw = (SELECT_OUTLINE, 2) if sel else (color, 1)
        self.canvas.create_rectangle(
            sx,
            sy,
            sx + sw,
            sy + th,
            fill=color,
            outline=outline,
            width=lw,
            tags=(f"node_{node.id}",),
        )
        title = node.params.get("title", "Container")
        arrow = " ▶" if node.params.get("collapsed") else " ▼"
        fs = max(7, int(9 * app.zoom))
        self.canvas.create_text(
            sx + sw / 2, sy + th / 2, text=title + arrow, fill="#ffffff", font=("Segoe UI", fs)
        )

    def _draw_proxy_edges(self, app, container, hidden: set) -> None:
        """Stub lines for edges crossing collapsed container boundary."""
        w = container.params.get("_w", CONTAINER_DEFAULT_W)
        sx, sy = self.w2s(app, container.x, container.y)
        th = TITLE_H * app.zoom
        proxy_x = sx + w * app.zoom
        proxy_y = sy + th / 2

        for edge in app.edges:
            src_hidden = edge.src_node in hidden
            dst_hidden = edge.dst_node in hidden
            if src_hidden and not dst_hidden:
                dst = app.nodes_by_id.get(edge.dst_node)
                if dst:
                    dx, dy = self.port_screen(app, dst, edge.dst_port, "in")
                    ctrl = max(40 * app.zoom, abs(dx - proxy_x) * 0.5)
                    pts = bezier_pts(
                        (proxy_x, proxy_y), (proxy_x + ctrl, proxy_y), (dx - ctrl, dy), (dx, dy)
                    )
                    self.canvas.create_line(
                        *pts,
                        fill=EDGE_COLOR,
                        width=1,
                        dash=(3, 3),
                        arrow=tk.LAST,
                        arrowshape=(7, 9, 3),
                    )
            elif dst_hidden and not src_hidden:
                src = app.nodes_by_id.get(edge.src_node)
                if src:
                    ox, oy = self.port_screen(app, src, edge.src_port, "out")
                    lx, ly = sx, sy + th / 2
                    ctrl = max(40 * app.zoom, abs(lx - ox) * 0.5)
                    pts = bezier_pts((ox, oy), (ox + ctrl, oy), (lx - ctrl, ly), (lx, ly))
                    self.canvas.create_line(*pts, fill=EDGE_COLOR, width=1, dash=(3, 3))

    # ── edges ─────────────────────────────────────────────────────────────

    def _draw_edge(self, app, edge, hidden: set) -> None:
        if edge.src_node in hidden and edge.dst_node in hidden:
            return
        if edge.src_node in hidden or edge.dst_node in hidden:
            return  # proxy edges drawn separately

        src = app.nodes_by_id.get(edge.src_node)
        dst = app.nodes_by_id.get(edge.dst_node)
        if not src or not dst:
            return

        sx, sy = self.port_screen(app, src, edge.src_port, "out")
        dx, dy = self.port_screen(app, dst, edge.dst_port, "in")
        ctrl = max(50 * app.zoom, abs(dx - sx) * 0.5)
        pts = bezier_pts((sx, sy), (sx + ctrl, sy), (dx - ctrl, dy), (dx, dy))

        sel = edge.id in app.selected_edge_ids
        color, lw = (SELECT_OUTLINE, 2) if sel else (EDGE_COLOR, 1.5)
        self.canvas.create_line(
            *pts,
            fill=color,
            width=lw,
            arrow=tk.LAST,
            arrowshape=(8, 10, 3),
            tags=(f"edge_{edge.id}",),
        )

    # ── nodes ─────────────────────────────────────────────────────────────

    def _draw_node(self, app, node) -> None:
        tool = get_tool(node.kind)
        if not tool:
            return
        sel = node.id in app.selected_ids
        has_result = node.result is not None

        sx, sy = self.w2s(app, node.x, node.y)
        nw, nh, th = NODE_W * app.zoom, NODE_H * app.zoom, TITLE_H * app.zoom

        if sel:
            outline, lw = SELECT_OUTLINE, 2
        elif has_result:
            outline, lw = RESULT_OUTLINE, 1
        else:
            outline, lw = "#3a3a5a", 1

        tag = f"node_{node.id}"
        self.canvas.create_rectangle(
            sx, sy, sx + nw, sy + nh, fill=NODE_BG, outline=outline, width=lw, tags=(tag,)
        )
        self.canvas.create_rectangle(
            sx, sy, sx + nw, sy + th, fill=tool.color, outline=outline, width=lw, tags=(tag,)
        )
        fs = max(7, int(9 * app.zoom))
        self.canvas.create_text(
            sx + nw / 2,
            sy + th / 2,
            text=tool.display_name,
            fill="#ffffff",
            font=("Segoe UI", fs, "bold"),
            tags=(tag,),
        )
        sub = tool.subtitle(node.params)
        if sub:
            self.canvas.create_text(
                sx + nw / 2,
                sy + th + (nh - th) / 2,
                text=sub,
                fill=DIM_FG,
                font=("Segoe UI", max(6, int(8 * app.zoom))),
                width=nw - 8,
                tags=(tag,),
            )

        if node.disabled:
            self.canvas.create_rectangle(
                sx, sy, sx + nw, sy + nh, fill="#000000", stipple="gray50", outline="", tags=(tag,)
            )

        pr = PORT_R * app.zoom
        for port in tool.ins:
            px, py = self.port_screen(app, node, port, "in")
            hov = app.hover_port == (node.id, port, "in")
            self.canvas.create_oval(
                px - pr,
                py - pr,
                px + pr,
                py + pr,
                fill="#ffffff" if hov else PORT_IN_COLOR,
                outline="#1a1a2e",
                width=1,
            )
            if app.zoom > 0.55:
                self.canvas.create_text(
                    px + pr + 3,
                    py,
                    text=port,
                    fill=DIM_FG,
                    font=("Segoe UI", max(5, int(7 * app.zoom))),
                    anchor="w",
                )
        for port in tool.outs:
            px, py = self.port_screen(app, node, port, "out")
            hov = app.hover_port == (node.id, port, "out")
            self.canvas.create_oval(
                px - pr,
                py - pr,
                px + pr,
                py + pr,
                fill="#ffffff" if hov else PORT_OUT_COLOR,
                outline="#1a1a2e",
                width=1,
            )
            if app.zoom > 0.55:
                self.canvas.create_text(
                    px - pr - 3,
                    py,
                    text=port,
                    fill=DIM_FG,
                    font=("Segoe UI", max(5, int(7 * app.zoom))),
                    anchor="e",
                )

    def _draw_wire(self, app) -> None:
        sx, sy = self.port_screen(app, app.wire_start_node, app.wire_start_port, app.wire_start_dir)
        tx, ty = app.wire_pos
        ctrl = max(50 * app.zoom, abs(tx - sx) * 0.5)
        if app.wire_start_dir == "out":
            pts = bezier_pts((sx, sy), (sx + ctrl, sy), (tx - ctrl, ty), (tx, ty))
        else:
            pts = bezier_pts((tx, ty), (tx + ctrl, ty), (sx - ctrl, sy), (sx, sy))
        self.canvas.create_line(*pts, fill=EDGE_WIRE, width=1.5, dash=(4, 3))

    # ── hit testing ───────────────────────────────────────────────────────

    def hit_test(self, app, sx: float, sy: float):
        """Returns (node | None, hit_type | None, port | None).

        Regular nodes are tested before containers so hit order matches draw
        order (containers are drawn behind all regular nodes): a node sitting
        on top of a container stays clickable.
        """
        hidden = _hidden_ids(app)
        pr_sq = (PORT_R * app.zoom + 4) ** 2

        # Regular nodes first (drawn on top)
        for node in reversed(app.nodes):
            if node.kind == "container" or node.id in hidden:
                continue
            tool = get_tool(node.kind)
            if not tool:
                continue

            nx, ny = self.w2s(app, node.x, node.y)
            nw, nh, th = NODE_W * app.zoom, NODE_H * app.zoom, TITLE_H * app.zoom

            # Ports first
            for port in tool.ins:
                px, py = self.port_screen(app, node, port, "in")
                if (sx - px) ** 2 + (sy - py) ** 2 <= pr_sq:
                    return (node, "port_in", port)
            for port in tool.outs:
                px, py = self.port_screen(app, node, port, "out")
                if (sx - px) ** 2 + (sy - py) ** 2 <= pr_sq:
                    return (node, "port_out", port)

            # Body
            if nx <= sx <= nx + nw and ny <= sy <= ny + nh:
                return (node, "title" if sy <= ny + th else "body", None)

        # Containers last (drawn behind)
        for node in reversed(app.nodes):
            if node.kind != "container" or node.id in hidden:
                continue
            if not get_tool(node.kind):
                continue

            w = node.params.get("_w", CONTAINER_DEFAULT_W)
            h = node.params.get("_h", CONTAINER_DEFAULT_H)
            nx, ny = self.w2s(app, node.x, node.y)
            nw, nh = w * app.zoom, h * app.zoom
            th = TITLE_H * app.zoom
            # Resize handle
            if not node.params.get("collapsed"):
                hx, hy = nx + nw - 12, ny + nh - 12
                if hx <= sx <= nx + nw and hy <= sy <= ny + nh:
                    return (node, "resize", None)
            # Title bar
            if nx <= sx <= nx + nw and ny <= sy <= ny + th:
                return (node, "title", None)
            # Body
            if (
                not node.params.get("collapsed")
                and nx <= sx <= nx + nw
                and ny + th <= sy <= ny + nh
            ):
                return (node, "body", None)

        return (None, None, None)


def _hidden_ids(app) -> set:
    hidden: set = set()
    for node in app.nodes:
        if node.kind == "container" and node.params.get("collapsed"):
            w = node.params.get("_w", CONTAINER_DEFAULT_W)
            h = node.params.get("_h", CONTAINER_DEFAULT_H)
            for other in app.nodes:
                if other.id == node.id or other.kind == "container":
                    continue
                if node.x <= other.x <= node.x + w and node.y <= other.y <= node.y + h:
                    hidden.add(other.id)
    return hidden
