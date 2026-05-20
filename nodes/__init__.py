from nodes.input_output import ImportCSV, ImportExcel, ShowTable, ExportCSV, ExportExcel
from nodes.preparation import (SelectColumns, FilterRows, Sort, HeadTail, RenameColumns,
                                EditColumns, AddColumns, Cleansing, RecordID)
from nodes.join import MergeJoin, Union, UniqueDuplicate
from nodes.transform import Summarize, GroupBy, Pivot, Unpivot
from nodes.documentation import Comment, Container

_tools: list = [
    ImportCSV(), ImportExcel(), ShowTable(), ExportCSV(), ExportExcel(),
    SelectColumns(), FilterRows(), Sort(), HeadTail(), RenameColumns(),
    EditColumns(), AddColumns(), Cleansing(), RecordID(),
    MergeJoin(), Union(), UniqueDuplicate(),
    Summarize(), GroupBy(), Pivot(), Unpivot(),
    Comment(), Container(),
]

REGISTRY: dict = {t.node_type: t for t in _tools}


def get_tool(kind: str):
    return REGISTRY.get(kind)


def all_tools() -> list:
    return _tools
