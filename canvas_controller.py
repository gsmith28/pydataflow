from __future__ import annotations

from typing import TYPE_CHECKING

from constants import NODE_H, NODE_W

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
