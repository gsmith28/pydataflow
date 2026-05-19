from __future__ import annotations
import hashlib
from datetime import datetime
from models.custom_tool import CustomTool
from storage.database import get_db


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:16]


async def list_custom_tools() -> list[dict]:
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT tool_id, name, data, created_at, updated_at FROM custom_tools ORDER BY name"
        )
        return [dict(r) for r in rows]


async def get_custom_tool(tool_id: str) -> CustomTool | None:
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT data FROM custom_tools WHERE tool_id = ?", (tool_id,)
        )
        if not rows:
            return None
        return CustomTool.model_validate_json(rows[0]["data"])


async def save_custom_tool(tool: CustomTool) -> CustomTool:
    tool.updated_at = datetime.utcnow().isoformat()
    tool.code_hash = _hash_code(tool.python_code)
    data = tool.model_dump_json()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO custom_tools (tool_id, name, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tool_id) DO UPDATE SET
                name = excluded.name,
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (tool.tool_id, tool.name, data, tool.created_at, tool.updated_at),
        )
        await db.commit()
    return tool


async def delete_custom_tool(tool_id: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM custom_tools WHERE tool_id = ?", (tool_id,))
        await db.commit()
        return cursor.rowcount > 0
