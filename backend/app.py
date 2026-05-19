"""PyDataFlow — local visual audit analytics workflow builder."""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from nicegui import ui, app

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ── Storage init ──────────────────────────────────────────────────────────────
from storage.database import init_db, set_db_path

DB_PATH = Path("pydataflow.db")
set_db_path(DB_PATH)

# ── REST API routers ──────────────────────────────────────────────────────────
from api.workflows import router as workflows_router
from api.execution import router as execution_router
from api.tools_api import router as tools_router
from api.custom_tools_api import router as custom_tools_router
from api.files_api import router as files_router

for router in [workflows_router, execution_router, tools_router, custom_tools_router, files_router]:
    app.include_router(router)

# ── NiceGUI pages ─────────────────────────────────────────────────────────────
from ui.pages.editor import create_editor_page
from ui.pages.custom_tool_builder import create_custom_tool_page

create_editor_page(base_path=".")
create_custom_tool_page()

# ── Load saved custom tools into registry on startup ─────────────────────────
@app.on_startup
async def startup():
    await init_db()

    from storage.custom_tool_store import list_custom_tools
    from tools.registry import register_custom_tool
    import json

    rows = await list_custom_tools()
    for row in rows:
        tool_def = json.loads(row["data"])
        try:
            register_custom_tool(tool_def)
        except Exception as e:
            print(f"Warning: could not register custom tool {row['tool_id']}: {e}")

    print("PyDataFlow ready.")


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="PyDataFlow",
        host="127.0.0.1",
        port=8080,
        storage_secret="pydataflow-local-secret",
        show=True,
        reload=False,
        favicon="🔀",
    )
