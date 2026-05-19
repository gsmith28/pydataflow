from __future__ import annotations
from typing import Any
from tools.base import BaseTool
from tools.input_output import InputDataTool, BrowsePreviewTool, OutputDataTool, CountRecordsTool
from tools.preparation import (
    SelectFieldsTool, FilterTool, FormulaTool, SortTool,
    UniqueDuplicateTool, RecordIDTool, DataCleansingTool, SampleTool,
)
from tools.join import JoinTool, UnionTool, FindReplaceLookupTool
from tools.transform import SummarizeTool, CrossTabPivotTool, TransposeUnpivotTool
from tools.profiling import FieldSummaryTool, FrequencyTableTool
from tools.audit_tests import TestTool, MessageTool, FieldInfoTool, ExpectEqualTool
from tools.parse import DateTimeParsetool, TextToColumnsTool, RegexTool
from tools.custom import CustomToolRunner


_BUILT_IN_TOOLS: list[type[BaseTool]] = [
    InputDataTool,
    BrowsePreviewTool,
    OutputDataTool,
    CountRecordsTool,
    SelectFieldsTool,
    FilterTool,
    FormulaTool,
    DataCleansingTool,
    SortTool,
    UniqueDuplicateTool,
    RecordIDTool,
    SampleTool,
    JoinTool,
    UnionTool,
    FindReplaceLookupTool,
    SummarizeTool,
    CrossTabPivotTool,
    TransposeUnpivotTool,
    FieldSummaryTool,
    FrequencyTableTool,
    TestTool,
    MessageTool,
    FieldInfoTool,
    ExpectEqualTool,
    DateTimeParsetool,
    TextToColumnsTool,
    RegexTool,
]

_registry: dict[str, BaseTool] = {}

for _cls in _BUILT_IN_TOOLS:
    _inst = _cls()
    _registry[_inst.tool_type] = _inst


def get_tool(tool_type: str) -> BaseTool | None:
    return _registry.get(tool_type)


def all_tools() -> list[dict[str, Any]]:
    return [t.tool_info() for t in _registry.values()]


def register_custom_tool(tool_def: dict[str, Any]) -> None:
    runner = CustomToolRunner(tool_def)
    _registry[runner.tool_type] = runner


def unregister_custom_tool(tool_id: str) -> None:
    _registry.pop(tool_id, None)


def get_tool_or_raise(tool_type: str) -> BaseTool:
    tool = get_tool(tool_type)
    if tool is None:
        raise KeyError(f"Unknown tool type: '{tool_type}'")
    return tool
