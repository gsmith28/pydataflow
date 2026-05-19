"""Per-tool configuration form renderers using NiceGUI components."""
from __future__ import annotations
from typing import Any, Callable
from nicegui import ui


def _label(text: str) -> None:
    ui.label(text).classes("text-xs font-medium text-gray-500 uppercase tracking-wide mt-2")


def render_text(key: str, schema: dict, config: dict, on_change: Callable) -> None:
    _label(schema.get("label", key))
    val = config.get(key, schema.get("default", ""))
    ui.input(value=str(val) if val is not None else "").classes("w-full").on(
        "update:model-value", lambda e: (config.update({key: e.args}), on_change())
    )


def render_number(key: str, schema: dict, config: dict, on_change: Callable) -> None:
    _label(schema.get("label", key))
    val = config.get(key, schema.get("default", 0))
    ui.number(value=float(val) if val is not None else 0).classes("w-full").on(
        "update:model-value", lambda e: (config.update({key: e.args}), on_change())
    )


def render_checkbox(key: str, schema: dict, config: dict, on_change: Callable) -> None:
    val = config.get(key, schema.get("default", False))
    ui.checkbox(schema.get("label", key), value=bool(val)).on(
        "update:model-value", lambda e: (config.update({key: e.args}), on_change())
    )


def render_select(key: str, schema: dict, config: dict, on_change: Callable) -> None:
    _label(schema.get("label", key))
    options = schema.get("options", [])
    val = config.get(key, schema.get("default", options[0] if options else ""))
    ui.select(options=options, value=val).classes("w-full").on(
        "update:model-value", lambda e: (config.update({key: e.args}), on_change())
    )


def render_filepath(key: str, schema: dict, config: dict, on_change: Callable) -> None:
    _label(schema.get("label", key))
    val = config.get(key, "")
    inp = ui.input(value=str(val) if val else "", placeholder="/path/to/file.csv").classes("w-full")
    inp.on("update:model-value", lambda e: (config.update({key: e.args}), on_change()))


def render_textarea(key: str, schema: dict, config: dict, on_change: Callable) -> None:
    _label(schema.get("label", key))
    val = config.get(key, "")
    ui.textarea(value=str(val) if val else "").classes("w-full h-24").on(
        "update:model-value", lambda e: (config.update({key: e.args}), on_change())
    )


def render_field_selector(key: str, schema: dict, config: dict, columns: list[str], on_change: Callable) -> None:
    _label(schema.get("label", key))
    val = config.get(key, "")
    opts = [""] + columns
    ui.select(options=opts, value=val if val in opts else "").classes("w-full").on(
        "update:model-value", lambda e: (config.update({key: e.args}), on_change())
    )


def render_multi_field_selector(key: str, schema: dict, config: dict, columns: list[str], on_change: Callable) -> None:
    _label(schema.get("label", key))
    selected = config.get(key) or []

    state = {"selected": list(selected)}

    with ui.column().classes("w-full gap-1"):
        for col in columns:
            checked = col in state["selected"]

            def make_handler(c=col):
                def handler(e):
                    if e.args:
                        if c not in state["selected"]:
                            state["selected"].append(c)
                    else:
                        if c in state["selected"]:
                            state["selected"].remove(c)
                    config.update({key: list(state["selected"])})
                    on_change()
                return handler

            ui.checkbox(col, value=checked).on("update:model-value", make_handler())


def render_sort_list(key: str, schema: dict, config: dict, columns: list[str], on_change: Callable) -> None:
    _label(schema.get("label", key))
    sort_fields = config.get(key) or []

    container = ui.column().classes("w-full gap-1")

    def redraw():
        container.clear()
        with container:
            for i, sf in enumerate(sort_fields):
                with ui.row().classes("w-full items-center gap-1"):
                    opts = [""] + columns
                    val = sf.get("field", "")
                    ui.select(options=opts, value=val if val in opts else "").classes("flex-1").on(
                        "update:model-value",
                        lambda e, idx=i: (_update_sf(idx, "field", e.args), on_change()),
                    )
                    asc = sf.get("ascending", True)
                    ui.select(options=["asc", "desc"], value="asc" if asc else "desc").classes("w-20").on(
                        "update:model-value",
                        lambda e, idx=i: (_update_sf(idx, "ascending", e.args == "asc"), on_change()),
                    )
                    ui.button(icon="delete", color="red").props("flat dense").on(
                        "click", lambda _, idx=i: (_remove_sf(idx), redraw(), on_change())
                    )
            ui.button("+ Add sort field", icon="add").props("flat dense").classes("text-blue-600").on(
                "click", lambda: (_add_sf(), redraw(), on_change())
            )

    def _update_sf(idx: int, field: str, val: Any) -> None:
        sort_fields[idx][field] = val
        config.update({key: sort_fields})

    def _remove_sf(idx: int) -> None:
        sort_fields.pop(idx)
        config.update({key: sort_fields})

    def _add_sf() -> None:
        sort_fields.append({"field": "", "ascending": True})
        config.update({key: sort_fields})

    redraw()


def render_condition_builder(key: str, schema: dict, config: dict, columns: list[str], on_change: Callable) -> None:
    """Simple single-condition builder. Advanced compound conditions via JSON editor."""
    _label(schema.get("label", key))
    cond = config.get(key) or {}

    ops = ["==", "!=", ">", ">=", "<", "<=", "contains", "starts_with", "ends_with", "is_null", "is_not_null", "in", "not_in", "between"]

    with ui.column().classes("w-full gap-1"):
        with ui.row().classes("w-full items-center gap-1"):
            opts = [""] + columns
            field_val = cond.get("field", "")
            field_sel = ui.select(options=opts, value=field_val if field_val in opts else "", label="Field").classes("flex-1").on(
                "update:model-value",
                lambda e: (_upd("field", e.args), on_change()),
            )
            op_val = cond.get("op", "==")
            ui.select(options=ops, value=op_val if op_val in ops else "==", label="Op").classes("w-36").on(
                "update:model-value",
                lambda e: (_upd("op", e.args), on_change()),
            )
            val = cond.get("value", "")
            ui.input(value=str(val) if val is not None else "", placeholder="Value").classes("flex-1").on(
                "update:model-value",
                lambda e: (_upd_value(e.args), on_change()),
            )

    def _upd(k: str, v: Any) -> None:
        cond["type"] = "comparison"
        cond[k] = v
        config.update({key: cond})

    def _upd_value(v: str) -> None:
        cond["type"] = "comparison"
        try:
            cond["value"] = int(v)
        except (ValueError, TypeError):
            try:
                cond["value"] = float(v)
            except (ValueError, TypeError):
                cond["value"] = v
        config.update({key: cond})


def render_formula_list(key: str, schema: dict, config: dict, columns: list[str], on_change: Callable) -> None:
    _label("Formulas")
    formulas = config.get(key) or []
    container = ui.column().classes("w-full gap-2")

    def redraw():
        container.clear()
        with container:
            for i, f in enumerate(formulas):
                with ui.card().classes("w-full p-2"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(f"Formula {i+1}").classes("text-sm font-medium")
                        ui.button(icon="delete", color="red").props("flat dense").on(
                            "click", lambda _, idx=i: (_remove(idx), redraw(), on_change())
                        )
                    ui.input(label="Target field", value=f.get("target_field", "")).classes("w-full").on(
                        "update:model-value",
                        lambda e, idx=i: (_update(idx, "target_field", e.args), on_change()),
                    )
                    ui.input(label="Expression (Python)", value=f.get("expression", "")).classes("w-full font-mono").on(
                        "update:model-value",
                        lambda e, idx=i: (_update(idx, "expression", e.args), on_change()),
                    )
            ui.button("+ Add formula", icon="add").props("flat dense").classes("text-blue-600").on(
                "click", lambda: (_add(), redraw(), on_change())
            )

    def _update(idx: int, k: str, v: Any) -> None:
        formulas[idx][k] = v
        config.update({key: formulas})

    def _remove(idx: int) -> None:
        formulas.pop(idx)
        config.update({key: formulas})

    def _add() -> None:
        formulas.append({"target_field": "", "expression": ""})
        config.update({key: formulas})

    redraw()


def render_aggregation_list(key: str, schema: dict, config: dict, columns: list[str], on_change: Callable) -> None:
    _label("Aggregations")
    aggs = config.get(key) or []
    agg_fns = ["count", "count_distinct", "sum", "min", "max", "mean", "median", "first", "last", "concat"]
    container = ui.column().classes("w-full gap-1")

    def redraw():
        container.clear()
        with container:
            for i, a in enumerate(aggs):
                with ui.row().classes("w-full items-center gap-1"):
                    opts = [""] + columns
                    fv = a.get("field", "")
                    ui.select(options=opts, value=fv if fv in opts else "", label="Field").classes("flex-1").on(
                        "update:model-value",
                        lambda e, idx=i: (_upd(idx, "field", e.args), on_change()),
                    )
                    fnv = a.get("function", "count")
                    ui.select(options=agg_fns, value=fnv if fnv in agg_fns else "count", label="Function").classes("w-32").on(
                        "update:model-value",
                        lambda e, idx=i: (_upd(idx, "function", e.args), on_change()),
                    )
                    ui.input(label="Output field", value=a.get("output_field", "")).classes("flex-1").on(
                        "update:model-value",
                        lambda e, idx=i: (_upd(idx, "output_field", e.args), on_change()),
                    )
                    ui.button(icon="delete", color="red").props("flat dense").on(
                        "click", lambda _, idx=i: (_remove(idx), redraw(), on_change())
                    )
            ui.button("+ Add aggregation", icon="add").props("flat dense").classes("text-blue-600").on(
                "click", lambda: (_add(), redraw(), on_change())
            )

    def _upd(idx: int, k: str, v: Any) -> None:
        aggs[idx][k] = v
        config.update({key: aggs})

    def _remove(idx: int) -> None:
        aggs.pop(idx)
        config.update({key: aggs})

    def _add() -> None:
        aggs.append({"field": "", "function": "count", "output_field": ""})
        config.update({key: aggs})

    redraw()


def render_field_list(key: str, schema: dict, config: dict, columns: list[str], on_change: Callable) -> None:
    """Render an include/exclude/rename field list."""
    _label(schema.get("label", key))
    fields_cfg = config.get(key) or [{"name": c, "include": True, "rename_to": "", "output_type": ""} for c in columns]
    container = ui.column().classes("w-full gap-1")
    types = ["", "string", "integer", "float", "datetime", "boolean"]

    def redraw():
        container.clear()
        with container:
            with ui.row().classes("w-full text-xs text-gray-500 font-medium gap-1"):
                ui.label("Include").classes("w-12")
                ui.label("Field").classes("flex-1")
                ui.label("Rename to").classes("flex-1")
                ui.label("Type").classes("w-28")
            for i, f in enumerate(fields_cfg):
                with ui.row().classes("w-full items-center gap-1"):
                    ui.checkbox(value=f.get("include", True)).classes("w-12").on(
                        "update:model-value",
                        lambda e, idx=i: (_upd(idx, "include", e.args), on_change()),
                    )
                    ui.label(f.get("name", "")).classes("flex-1 text-sm")
                    ui.input(value=f.get("rename_to", ""), placeholder="(keep name)").classes("flex-1").on(
                        "update:model-value",
                        lambda e, idx=i: (_upd(idx, "rename_to", e.args), on_change()),
                    )
                    tv = f.get("output_type", "")
                    ui.select(options=types, value=tv if tv in types else "").classes("w-28").on(
                        "update:model-value",
                        lambda e, idx=i: (_upd(idx, "output_type", e.args), on_change()),
                    )

    def _upd(idx: int, k: str, v: Any) -> None:
        fields_cfg[idx][k] = v
        config.update({key: fields_cfg})

    redraw()


WIDGET_RENDERERS = {
    "text": render_text,
    "number": render_number,
    "checkbox": render_checkbox,
    "select": render_select,
    "filepath": render_filepath,
    "textarea": render_textarea,
}

COLUMN_AWARE_RENDERERS = {
    "field_selector": render_field_selector,
    "multi_field_selector": render_multi_field_selector,
    "sort_list": render_sort_list,
    "condition_builder": render_condition_builder,
    "formula_list": render_formula_list,
    "aggregation_list": render_aggregation_list,
    "field_list": render_field_list,
}


def render_config_schema(
    schema: dict[str, dict],
    config: dict,
    columns: list[str],
    on_change: Callable,
) -> None:
    for key, field_schema in schema.items():
        widget_type = field_schema.get("type", "text")
        if widget_type in WIDGET_RENDERERS:
            WIDGET_RENDERERS[widget_type](key, field_schema, config, on_change)
        elif widget_type in COLUMN_AWARE_RENDERERS:
            COLUMN_AWARE_RENDERERS[widget_type](key, field_schema, config, columns, on_change)
        else:
            render_text(key, field_schema, config, on_change)
