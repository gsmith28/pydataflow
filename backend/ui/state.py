"""Shared application state (per-user session via NiceGUI storage)."""
from __future__ import annotations
from typing import Any
from models.workflow import Workflow


# Each NiceGUI client connection gets its own copy via app.storage.user.
# This module provides helper access patterns.

def get_workflow(storage) -> Workflow | None:
    data = storage.get("current_workflow")
    if not data:
        return None
    return Workflow.model_validate(data)


def set_workflow(storage, wf: Workflow) -> None:
    storage["current_workflow"] = wf.model_dump()


def get_selected_node_id(storage) -> str | None:
    return storage.get("selected_node_id")


def set_selected_node_id(storage, node_id: str | None) -> None:
    storage["selected_node_id"] = node_id


def get_run_result(storage) -> dict | None:
    return storage.get("last_run_result")


def set_run_result(storage, result: dict) -> None:
    storage["last_run_result"] = result
