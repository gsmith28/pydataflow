"""Reusable data preview table component."""
from __future__ import annotations
from nicegui import ui


def render_data_preview(columns: list[str], rows: list[dict], record_count: int | None = None) -> None:
    if record_count is not None:
        label = f"{record_count:,} rows" + (f" (showing {len(rows)})" if len(rows) < record_count else "")
        ui.label(label).classes("text-xs text-gray-500 mb-1")

    if not columns:
        ui.label("No data to display.").classes("text-gray-400 italic text-sm")
        return

    with ui.scroll_area().classes("w-full border rounded"):
        table = ui.table(
            columns=[{"name": c, "label": c, "field": c, "align": "left"} for c in columns],
            rows=rows,
            row_key=columns[0] if columns else "id",
        ).classes("w-full text-xs")
        table.props("dense flat bordered virtual-scroll")


def render_schema_view(schema: dict | None) -> None:
    if not schema or not schema.get("fields"):
        ui.label("No schema available.").classes("text-gray-400 italic text-sm")
        return

    fields = schema["fields"]
    rc = schema.get("record_count")
    if rc is not None:
        ui.label(f"{rc:,} records").classes("text-xs text-gray-500 mb-1")

    schema_rows = [
        {
            "field": f["name"],
            "type": f.get("type", ""),
            "nullable": "yes" if f.get("nullable") else "no",
        }
        for f in fields
    ]
    ui.table(
        columns=[
            {"name": "field", "label": "Field", "field": "field", "align": "left"},
            {"name": "type", "label": "Type", "field": "type", "align": "left"},
            {"name": "nullable", "label": "Nullable", "field": "nullable", "align": "center"},
        ],
        rows=schema_rows,
        row_key="field",
    ).classes("w-full text-xs").props("dense flat bordered")
