from __future__ import annotations
from fastapi import APIRouter, HTTPException
from models.workflow import Workflow, RunRequest
from storage.project_store import list_workflows, get_workflow, save_workflow, delete_workflow

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
async def list_all():
    return await list_workflows()


@router.post("", response_model=Workflow)
async def create_workflow(workflow: Workflow):
    return await save_workflow(workflow)


@router.get("/{workflow_id}", response_model=Workflow)
async def read_workflow(workflow_id: str):
    wf = await get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf


@router.put("/{workflow_id}", response_model=Workflow)
async def update_workflow(workflow_id: str, workflow: Workflow):
    workflow.workflow_id = workflow_id
    return await save_workflow(workflow)


@router.delete("/{workflow_id}")
async def remove_workflow(workflow_id: str):
    ok = await delete_workflow(workflow_id)
    if not ok:
        raise HTTPException(404, "Workflow not found")
    return {"deleted": True}
