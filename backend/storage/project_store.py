from __future__ import annotations
import json
from datetime import datetime
from models.workflow import Workflow
from storage.database import get_db


async def list_workflows() -> list[dict]:
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT workflow_id, name, created_at, updated_at FROM workflows ORDER BY updated_at DESC"
        )
        return [dict(r) for r in rows]


async def get_workflow(workflow_id: str) -> Workflow | None:
    async with get_db() as db:
        row = await db.execute_fetchall(
            "SELECT data FROM workflows WHERE workflow_id = ?", (workflow_id,)
        )
        if not row:
            return None
        return Workflow.model_validate_json(row[0]["data"])


async def save_workflow(workflow: Workflow) -> Workflow:
    workflow.updated_at = datetime.utcnow().isoformat()
    data = workflow.model_dump_json()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO workflows (workflow_id, name, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(workflow_id) DO UPDATE SET
                name = excluded.name,
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (workflow.workflow_id, workflow.name, data, workflow.created_at, workflow.updated_at),
        )
        await db.commit()
    return workflow


async def delete_workflow(workflow_id: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM workflows WHERE workflow_id = ?", (workflow_id,))
        await db.commit()
        return cursor.rowcount > 0
