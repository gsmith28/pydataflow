from __future__ import annotations
from fastapi import APIRouter
from tools.registry import all_tools

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools():
    return all_tools()
