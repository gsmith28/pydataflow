from __future__ import annotations
from fastapi import APIRouter, HTTPException
from models.custom_tool import CustomTool, CustomToolCreate, CustomToolUpdate, CustomToolTestRequest
from storage.custom_tool_store import (
    list_custom_tools, get_custom_tool, save_custom_tool, delete_custom_tool
)
from tools.registry import register_custom_tool, unregister_custom_tool
from tools.custom import run_custom_tool_code
from tools.base import ExecutionContext
from pathlib import Path
import pandas as pd
import uuid
import time

router = APIRouter(prefix="/api/custom-tools", tags=["custom-tools"])


@router.get("")
async def list_tools():
    rows = await list_custom_tools()
    return rows


@router.post("", response_model=CustomTool)
async def create_tool(body: CustomToolCreate):
    tool = CustomTool(**body.model_dump())
    saved = await save_custom_tool(tool)
    register_custom_tool(saved.model_dump())
    return saved


@router.get("/{tool_id}", response_model=CustomTool)
async def read_tool(tool_id: str):
    tool = await get_custom_tool(tool_id)
    if not tool:
        raise HTTPException(404, "Custom tool not found")
    return tool


@router.put("/{tool_id}", response_model=CustomTool)
async def update_tool(tool_id: str, body: CustomToolUpdate):
    tool = await get_custom_tool(tool_id)
    if not tool:
        raise HTTPException(404, "Custom tool not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(tool, field, val)
    saved = await save_custom_tool(tool)
    register_custom_tool(saved.model_dump())
    return saved


@router.delete("/{tool_id}")
async def remove_tool(tool_id: str):
    ok = await delete_custom_tool(tool_id)
    if not ok:
        raise HTTPException(404, "Custom tool not found")
    unregister_custom_tool(tool_id)
    return {"deleted": True}


@router.post("/{tool_id}/test")
async def test_tool(tool_id: str, req: CustomToolTestRequest):
    tool = await get_custom_tool(tool_id)
    if not tool:
        raise HTTPException(404, "Custom tool not found")

    inputs: dict[str, pd.DataFrame] = {}
    if req.input_data:
        for port, rows in req.input_data.items():
            inputs[port] = pd.DataFrame(rows)
    elif tool.input_ports:
        inputs[tool.input_ports[0].name] = pd.DataFrame()

    log_messages: list[str] = []

    def logger(msg: str, level: str = "info") -> None:
        log_messages.append(f"[{level.upper()}] {msg}")

    ctx = ExecutionContext(
        run_id=str(uuid.uuid4()),
        project_dir=Path("."),
        temp_dir=Path("/tmp/pydataflow_test"),
        logger=logger,
        preview_limit=50,
    )
    ctx.temp_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    try:
        result = run_custom_tool_code(tool.python_code, inputs, req.config, ctx)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        output_preview = {}
        for port, df in result.items():
            output_preview[port] = {
                "columns": list(df.columns),
                "rows": df.head(20).fillna("").to_dict(orient="records"),
                "record_count": len(df),
            }
        return {
            "success": True,
            "elapsed_ms": elapsed,
            "output": output_preview,
            "log": log_messages,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "log": log_messages,
        }
