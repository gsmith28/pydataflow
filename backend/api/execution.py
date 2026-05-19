from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from models.workflow import Workflow, WorkflowRunResult, RunRequest
from engine.executor import execute_workflow
from engine.codegen import generate_python
from storage.project_store import get_workflow
from storage.run_history import save_run, list_runs

router = APIRouter(prefix="/api", tags=["execution"])

_PROJECT_DIR = Path(".")
_TEMP_DIR = Path("/tmp/pydataflow")


def _get_dirs() -> tuple[Path, Path]:
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return _PROJECT_DIR, _TEMP_DIR


@router.post("/workflows/{workflow_id}/run", response_model=WorkflowRunResult)
async def run_workflow(workflow_id: str, req: RunRequest, background_tasks: BackgroundTasks):
    wf = await get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    proj, tmp = _get_dirs()
    result = execute_workflow(
        wf, project_dir=proj, temp_dir=tmp,
        preview_limit=req.preview_limit,
        parameters=req.parameters,
    )
    background_tasks.add_task(save_run, result)
    return result


@router.post("/workflows/{workflow_id}/run-node/{node_id}", response_model=WorkflowRunResult)
async def run_node(workflow_id: str, node_id: str, req: RunRequest, background_tasks: BackgroundTasks):
    wf = await get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    proj, tmp = _get_dirs()
    result = execute_workflow(
        wf, project_dir=proj, temp_dir=tmp,
        preview_limit=req.preview_limit,
        parameters=req.parameters,
        node_id_filter=node_id,
    )
    background_tasks.add_task(save_run, result)
    return result


@router.post("/workflows/{workflow_id}/run-inline", response_model=WorkflowRunResult)
async def run_inline(workflow: Workflow, req: RunRequest, background_tasks: BackgroundTasks):
    """Run a workflow from the request body without saving it first."""
    proj, tmp = _get_dirs()
    result = execute_workflow(
        workflow, project_dir=proj, temp_dir=tmp,
        preview_limit=req.preview_limit,
        parameters=req.parameters,
    )
    background_tasks.add_task(save_run, result)
    return result


@router.post("/workflows/{workflow_id}/export/python")
async def export_python(workflow_id: str):
    wf = await get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    code = generate_python(wf)
    return {"code": code, "filename": f"{wf.name.replace(' ', '_').lower()}.py"}


@router.post("/workflows/export/python-inline")
async def export_python_inline(workflow: Workflow):
    code = generate_python(workflow)
    return {"code": code, "filename": f"{workflow.name.replace(' ', '_').lower()}.py"}


@router.get("/workflows/{workflow_id}/runs")
async def get_runs(workflow_id: str):
    return await list_runs(workflow_id)


@router.get("/runs")
async def get_all_runs(limit: int = 50):
    return await list_runs(limit=limit)
