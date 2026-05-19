"""Custom Tool Builder page."""
from __future__ import annotations
import json
from nicegui import ui, app

from models.custom_tool import CustomTool, CustomToolCreate
from storage.custom_tool_store import list_custom_tools, get_custom_tool, save_custom_tool, delete_custom_tool
from tools.registry import register_custom_tool, unregister_custom_tool
from tools.custom import run_custom_tool_code
from tools.base import ExecutionContext
from pathlib import Path
import uuid
import pandas as pd


_DEFAULT_CODE = '''\
import pandas as pd

def execute(inputs, config, context):
    df = inputs.get("in", pd.DataFrame()).copy()

    # --- Your logic here ---
    # Example: add a flag column
    # threshold = config.get("threshold", 0)
    # df["flagged"] = df["amount"] > threshold
    # -----------------------

    return {"out": df}
'''


def create_custom_tool_page() -> None:
    @ui.page("/custom-tools")
    async def custom_tools_page():
        await _render_page()


async def _render_page() -> None:
    storage = app.storage.user
    if "ct_editing" not in storage:
        storage["ct_editing"] = None

    # ── Header ────────────────────────────────────────────────────────────────
    with ui.header().classes("bg-slate-800 text-white items-center px-4 py-2 gap-3"):
        ui.link("← Editor", "/").classes("text-blue-300 text-sm hover:text-blue-100")
        ui.separator().props("vertical").classes("opacity-30")
        ui.label("Custom Tool Builder").classes("text-lg font-bold")

    with ui.row().classes("w-full flex-nowrap").style("height: calc(100vh - 52px); overflow:hidden"):

        # ── Left: Tool list ───────────────────────────────────────────────────
        with ui.scroll_area().classes("bg-slate-50 border-r p-3 gap-2 flex flex-col").style("width:260px;min-width:260px"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("My Tools").classes("font-bold text-slate-700")

                async def new_tool():
                    storage["ct_editing"] = CustomTool(
                        name="My Custom Tool",
                        python_code=_DEFAULT_CODE,
                    ).model_dump()
                    builder_panel.refresh()

                ui.button(icon="add", on_click=new_tool).props("flat dense color=blue").tooltip("New tool")

            @ui.refreshable
            async def tool_list():
                tools = await list_custom_tools()
                if not tools:
                    ui.label("No custom tools yet.").classes("text-gray-400 text-sm")
                    return
                for t in tools:
                    raw = json.loads(t["data"])
                    with ui.row().classes(
                        "w-full items-center gap-1 px-2 py-1 rounded cursor-pointer "
                        "hover:bg-blue-50"
                    ):
                        ui.icon("extension", size="xs").classes("text-indigo-500")
                        ui.label(t["name"]).classes("flex-1 text-sm").on(
                            "click",
                            lambda _, data=raw: (storage.update({"ct_editing": data}), builder_panel.refresh()),
                        )

                        async def del_tool(tid=t["tool_id"]):
                            await delete_custom_tool(tid)
                            unregister_custom_tool(tid)
                            if storage.get("ct_editing", {}).get("tool_id") == tid:
                                storage["ct_editing"] = None
                            tool_list.refresh()
                            builder_panel.refresh()
                            ui.notify("Tool deleted", type="warning")

                        ui.button(icon="delete", color="red").props("flat dense").on("click", del_tool)

            await tool_list()

        # ── Right: Builder ────────────────────────────────────────────────────
        @ui.refreshable
        async def builder_panel():
            with ui.scroll_area().classes("flex-1 p-4"):
                editing = storage.get("ct_editing")
                if not editing:
                    with ui.column().classes("w-full items-center gap-4 mt-16"):
                        ui.icon("extension", size="xl").classes("text-gray-300")
                        ui.label("Select a tool or create a new one").classes("text-gray-400 text-center")
                    return

                tool_data = dict(editing)

                def upd(key, val):
                    tool_data[key] = val
                    storage["ct_editing"] = tool_data

                with ui.column().classes("w-full max-w-3xl gap-4"):
                    ui.label("Tool Definition").classes("text-xl font-bold text-slate-800")

                    with ui.grid(columns=2).classes("w-full gap-3"):
                        with ui.column():
                            ui.label("Tool Name").classes("text-xs font-medium text-gray-500")
                            ui.input(value=tool_data.get("name", "")).classes("w-full").on(
                                "update:model-value", lambda e: upd("name", e.args)
                            )
                        with ui.column():
                            ui.label("Category").classes("text-xs font-medium text-gray-500")
                            ui.input(value=tool_data.get("category", "Custom Tools")).classes("w-full").on(
                                "update:model-value", lambda e: upd("category", e.args)
                            )
                        with ui.column().classes("col-span-2"):
                            ui.label("Description").classes("text-xs font-medium text-gray-500")
                            ui.input(value=tool_data.get("description", "")).classes("w-full").on(
                                "update:model-value", lambda e: upd("description", e.args)
                            )

                    ui.separator()
                    ui.label("Python Code").classes("font-medium text-slate-700")
                    ui.label("Define an execute(inputs, config, context) function. Return a dict of port_name → DataFrame.").classes("text-xs text-gray-500")

                    code_area = ui.textarea(
                        value=tool_data.get("python_code", _DEFAULT_CODE)
                    ).classes("w-full font-mono text-sm").style("height:320px;white-space:pre;overflow-wrap:normal")
                    code_area.props("autogrow")
                    code_area.on("update:model-value", lambda e: upd("python_code", e.args))

                    ui.separator()
                    ui.label("Test").classes("font-medium text-slate-700")
                    ui.label("Provide sample input as JSON array of row objects.").classes("text-xs text-gray-500")
                    test_data_area = ui.textarea(
                        value='[{"amount": 100}, {"amount": 20000}]',
                        placeholder='[{"col": "value"}, ...]',
                    ).classes("w-full font-mono text-sm").style("height:80px")
                    test_result_box = ui.column().classes("w-full")

                    async def run_test():
                        test_result_box.clear()
                        raw_code = tool_data.get("python_code", "")
                        try:
                            input_rows = json.loads(test_data_area.value or "[]")
                            input_df = pd.DataFrame(input_rows)
                        except Exception as e:
                            with test_result_box:
                                ui.label(f"Invalid test data: {e}").classes("text-red-600 text-sm")
                            return

                        log_msgs: list[str] = []

                        def logger(msg: str, level: str = "info") -> None:
                            log_msgs.append(f"[{level.upper()}] {msg}")

                        ctx = ExecutionContext(
                            run_id=str(uuid.uuid4()),
                            project_dir=Path("."),
                            temp_dir=Path("/tmp/pydataflow_test"),
                            logger=logger,
                            preview_limit=20,
                        )
                        ctx.temp_dir.mkdir(parents=True, exist_ok=True)

                        try:
                            result = run_custom_tool_code(raw_code, {"in": input_df}, {}, ctx)
                            with test_result_box:
                                ui.label("✓ Test passed").classes("text-green-600 font-medium")
                                for port, df in result.items():
                                    ui.label(f"Port '{port}': {len(df)} rows, {len(df.columns)} columns").classes("text-sm text-gray-600")
                                    from ui.components.data_preview import render_data_preview
                                    cols = list(df.columns)
                                    rows_data = df.head(10).fillna("").to_dict(orient="records")
                                    render_data_preview(cols, rows_data, len(df))
                                if log_msgs:
                                    with ui.expansion("Logs").classes("w-full"):
                                        for m in log_msgs:
                                            ui.label(m).classes("text-xs font-mono")
                        except Exception as e:
                            with test_result_box:
                                ui.label(f"✗ Error: {e}").classes("text-red-600 font-medium")

                    with ui.row().classes("gap-2"):
                        ui.button("▶ Run test", on_click=run_test, color="green").props("dense")

                        async def save_tool():
                            td = dict(storage.get("ct_editing", {}))
                            if not td.get("name"):
                                ui.notify("Tool name is required", type="warning")
                                return
                            existing_id = td.get("tool_id")
                            if existing_id and (await get_custom_tool(existing_id)):
                                existing = await get_custom_tool(existing_id)
                                for k, v in td.items():
                                    if hasattr(existing, k):
                                        setattr(existing, k, v)
                                saved = await save_custom_tool(existing)
                            else:
                                new = CustomTool(**{k: v for k, v in td.items() if k in CustomTool.model_fields})
                                saved = await save_custom_tool(new)
                            register_custom_tool(saved.model_dump())
                            storage["ct_editing"] = saved.model_dump()
                            tool_list.refresh()
                            ui.notify(f"Saved: {saved.name}", type="positive")

                        ui.button("Save tool", on_click=save_tool, icon="save", color="blue").props("dense")

        await builder_panel()
