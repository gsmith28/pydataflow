# PyDataFlow — AI Context

This file gives an AI assistant everything it needs to work on this codebase cold.

---

## What this project is

A **local desktop data pipeline builder** written in Python. The user drags tool nodes onto a canvas, wires them together, configures them in a properties panel, runs the pipeline, and optionally exports it as a standalone pandas script.

- GUI: tkinter (stdlib) — no web server, no Electron
- Data engine: pandas
- Format: pipelines saved as `.json`
- Entry point: `python main.py`

---

## Repository layout

```
pydataflow/
├── main.py              # Entry point — boots FlowApp
├── app.py               # FlowApp class: orchestrator (window, palette, props, project I/O)
├── canvas_controller.py # CanvasController: click/drag/wire, zoom/pan, view framing
├── engine.py            # Topological sort + execute_flow()
├── renderer.py          # Canvas drawing — redraws every frame, no dirty tracking
├── properties.py        # Right-hand properties panel, calls tool.build_config()
├── column_inference.py  # Traces graph to infer columns without running pipeline
├── project_io.py        # save_project() / load_project() — JSON format v3
├── settings.py          # Per-user prefs (window, last dir, palette) → ~/.pydataflow/
├── export_script.py     # generate_python() — emits standalone pandas .py
├── constants.py         # Colours, geometry, CATEGORIES list, TOOL_COLORS
├── nodes/
│   ├── __init__.py      # Registry: get_tool(kind) → BaseTool | None
│   ├── base.py          # BaseTool abstract class + widget builder helpers
│   ├── input_output.py  # ImportCSV, ImportExcel, ShowTable, ExportCSV, ExportExcel
│   ├── columns.py       # SelectColumns, RenameColumns, EditColumns, AddColumns, Cleansing, RecordID
│   ├── rows.py          # FilterRows, Sort, HeadTail
│   ├── join.py          # MergeJoin, Union, UniqueDuplicate
│   ├── transform.py     # Summarize, GroupBy, Pivot, Unpivot
│   └── documentation.py # Comment, Container (visual-only, no data flow)
├── tests/               # pytest suite
├── pyproject.toml       # Deps: pandas>=2.0, openpyxl>=3.1; ruff; pytest
├── README.md            # Developer quickstart + architecture
└── ROADMAP.md           # Planned enhancements
```

---

## Key design patterns

### Tool contract (BaseTool)

Every data-processing node is a `BaseTool` subclass:

```python
class BaseTool:
    node_type: str      # unique snake_case key, e.g. "filter_rows"
    display_name: str   # shown in palette and node header
    color: str          # hex colour for palette indicator and node border
    ins: list[str]      # input port names, e.g. ["data"] or ["left", "right"]
    outs: list[str]     # output port names, e.g. ["data"] or ["true", "false"]

    def build_config(self, parent, params, on_change, columns=None): ...
    # Builds tkinter widgets directly into `parent`. Widgets call on_change()
    # when the user edits them, which updates `params` in place.

    def execute(self, params: dict, inputs: dict[str, DataFrame], log) -> dict[str, DataFrame]:
    # Receives params (from UI) and inputs (DataFrames from upstream ports).
    # Returns dict mapping output port name → DataFrame.
    # Raises ValueError with a user-readable message on failure.

    def to_code(self, params, input_vars, output_var, connected_outs) -> list[str]:
    # Returns Python source lines for export_script.py.
    # input_vars: list of variable names matching tool.ins order.
    # output_var: base variable name for outputs.
    # connected_outs: which output ports are actually wired (None = all).
```

### Param storage

`node.params` is a plain `dict[str, Any]`. Keys are set by `build_config()` widget helpers. Common keys you'll see:

- `file_path` — file path string (ImportCSV, ImportExcel)
- `delimiter` — `"comma"` | `"tab"` | `"pipe"` | `"semicolon"` | `"custom"`
- `conditions` — list of `{"column": str, "operator": str, "value": str}` (FilterRows)
- `rules` — list of `{"column": str, "order": "ascending"|"descending"}` (Sort)
- `group_cols` — list of column names (GroupBy)
- `aggs` — list of `{"column": str, "func": str, "alias": str}` (GroupBy)
- `_w`, `_h` — width/height in world units (Container only)

### Execution flow

```
FlowApp.run_flow()
  └─ engine.execute_flow(nodes, edges, log)
       ├─ topological_sort()   — raises ValueError on cycle
       └─ for node in order:
            inputs = {dst_port: upstream_outputs[src_port]}
            out = tool.execute(node.params, inputs, log)
            node.result = out   # stored for preview/properties panel
```

### Coordinate system

The canvas has two spaces:

- **World space**: where nodes live (float, unbounded, stored in `node.x`, `node.y`)
- **Screen space**: `screen = world * zoom + pan`

`CanvasController.s2w(sx, sy)` converts screen → world.  
`renderer.py` uses `app.zoom`, `app.pan_x`, `app.pan_y` for all transforms. Interaction
state (zoom, pan, drag, wire, resize) lives on `FlowApp` so the renderer can read it
directly each frame; `canvas_controller.py` holds the event-handling *methods* and
mutates that shared state.

### Container membership

A container "owns" nodes via an explicit `container.params["_children"]` id list — not
geometry. Membership is recomputed only when a node is added or actually dragged
(`FlowApp._update_node_membership`), never on container resize, so resizing never silently
adopts a node beneath it. The container also grows to enclose its children's footprint and
cannot be resized smaller than it.

### Column inference

`column_inference.infer_columns(app, node, port_index)` traces the graph upstream from a node to return a list of available column names. For CSV/Excel imports it reads file headers without loading the data. For other nodes it uses cached `node.result` if available.

---

## Things NOT to do

- **Do not move files into a package** — imports use `sys.path.insert` at the root level. Restructuring would break all relative imports.
- **Do not add pip dependencies** beyond what's in `pyproject.toml` without updating it.

---

## How to run

```bash
python main.py
```

## How to test

```bash
pytest                                    # run all tests
pytest tests/test_engine.py -v           # specific file
pytest --cov --cov-report=term-missing   # with coverage
```

## How to lint

```bash
ruff check .
ruff format .
```

---

## Current known gaps

- `app.py` still owns several concerns (palette/properties UI, project I/O, logging,
  preview). Canvas interaction was extracted to `canvas_controller.py`; further splits
  (e.g. project I/O) are possible but not yet done.
