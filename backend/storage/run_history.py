from __future__ import annotations
import json
from models.workflow import WorkflowRunResult
from storage.database import get_db


async def save_run(result: WorkflowRunResult) -> None:
    summary = json.dumps({
        "status": result.status,
        "errors": result.errors,
        "warnings": result.warnings,
        "output_files": result.output_files,
        "node_count": len(result.node_results),
    })
    async with get_db() as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO run_history
                (run_id, workflow_id, status, started_at, finished_at, summary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (result.run_id, result.workflow_id, result.status,
             result.started_at, result.finished_at, summary),
        )
        await db.commit()


async def list_runs(workflow_id: str | None = None, limit: int = 50) -> list[dict]:
    async with get_db() as db:
        if workflow_id:
            rows = await db.execute_fetchall(
                "SELECT run_id, workflow_id, status, started_at, finished_at, summary "
                "FROM run_history WHERE workflow_id = ? ORDER BY started_at DESC LIMIT ?",
                (workflow_id, limit),
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT run_id, workflow_id, status, started_at, finished_at, summary "
                "FROM run_history ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
        result = []
        for row in rows:
            d = dict(row)
            d["summary"] = json.loads(d["summary"])
            result.append(d)
        return result
