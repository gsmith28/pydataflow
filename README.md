# PyDataFlow

A local, offline visual data pipeline builder written in Python. Connect data transformation nodes on a canvas, configure them in a properties panel, run the pipeline, and export it as a standalone pandas script.

No cloud, no server, no licence fees. Just Python.

---

## Quick start

**Requirements:** Python 3.10+

```bash
pip install pandas openpyxl
python main.py
```

That's it. No install step needed — run from source.

---

## What it does

PyDataFlow presents a node-based canvas (think Alteryx or Tableau Prep, but pure Python):

- **Drag** a tool from the left palette onto the canvas
- **Wire** nodes together by clicking and dragging between ports
- **Configure** each node in the right-hand properties panel — column dropdowns populate automatically from upstream data
- **Run** the pipeline with the ▶ Run button
- **Export** the result as a self-contained `.py` script (`Export .py`)
- **Save / load** pipelines as `.json` files

---

## Tool catalogue (23 tools)

| Category | Tools |
|---|---|
| Input / Output | Import CSV, Import Excel, Show Table, Export CSV, Export Excel |
| Preparation | Select Columns, Filter Rows, Sort, Head/Tail, Rename Columns, Edit Columns, Add Columns, Cleansing, Record ID |
| Join / Reconcile | Merge/Join, Union, Unique/Duplicate |
| Transform / Summarize | Summarize, Group By, Pivot, Unpivot |
| Documentation | Comment, Container |

---

## Project layout

```
pydataflow/
├── main.py              # Entry point — boots FlowApp
├── app.py               # FlowApp: main window, palette/properties, orchestration
├── canvas_controller.py # Canvas interaction: click/drag/wire, zoom/pan, view framing
├── engine.py            # Topological sort + flow execution
├── renderer.py          # Canvas drawing: nodes, edges, ports, bezier curves
├── properties.py        # Right-hand properties panel
├── column_inference.py  # Traces upstream nodes to infer available columns
├── project_io.py        # Save/load .json project files
├── settings.py          # Per-user prefs persisted to ~/.pydataflow/settings.json
├── export_script.py     # Generate standalone pandas .py scripts
├── constants.py         # UI colours, geometry, tool categories
├── nodes/
│   ├── __init__.py      # Tool registry: get_tool(), all_tools()
│   ├── base.py          # BaseTool abstract class + widget helpers
│   ├── input_output.py  # Import/export tools
│   ├── columns.py       # Column tools: select, rename, retype, derive, cleanse, record id
│   ├── rows.py          # Row tools: filter, sort, head/tail
│   ├── join.py          # Merge, union, deduplication tools
│   ├── transform.py     # Aggregation and pivot tools
│   └── documentation.py # Comment and Container (visual only)
├── tests/               # pytest test suite
├── pyproject.toml       # Project metadata, dependencies, tool config
└── backend/             # ⚠ Prior NiceGUI/FastAPI prototype — not active
```

---

## Architecture

### Execution model

```
FlowApp.run_flow()
  └─ engine.execute_flow(nodes, edges, log)
       ├─ topological_sort()        — Kahn's algorithm, raises on cycles
       └─ for each node in order:
            tool.execute(params, inputs, log)  → dict[port, DataFrame]
```

Each **tool** is a subclass of `BaseTool` in `nodes/`. It implements three methods:

| Method | Purpose |
|---|---|
| `build_config(parent, params, on_change, columns)` | Build the tkinter config UI for this tool |
| `execute(params, inputs, log)` | Run the transformation; return `dict[port_name, DataFrame]` |
| `to_code(params, input_vars, output_var, connected_outs)` | Emit the equivalent Python lines for export |

### Column inference

Before a pipeline is run, `column_inference.infer_columns()` traces the graph backwards from each node to find what columns are available at each input port. This populates dropdowns without requiring a full execution. For CSV/Excel imports it reads file headers directly.

### Canvas / renderer

The canvas is a raw `tkinter.Canvas`. `renderer.py` redraws it on every frame (no dirty-tracking). Coordinates live in two spaces:

- **World space**: where nodes actually are (float, unbounded)
- **Screen space**: world × zoom + pan offset

`Renderer.hit_test()` maps a mouse event back to world space to determine what was clicked (node title, port, resize handle, background). `canvas_controller.py` owns the interaction logic — click/drag/wire, zoom/pan, and view framing — operating on shared state that still lives on `FlowApp` (so `renderer.py` keeps reading `app.zoom`/`app.pan_x`/`app.pan_y` directly).

---

## Adding a new tool

1. Create a subclass of `BaseTool` in the appropriate `nodes/` file (or a new file):

```python
class MyTool(BaseTool):
    node_type    = "my_tool"        # unique snake_case key
    display_name = "My Tool"
    color        = "#2a85c4"
    ins          = ["data"]         # input port names
    outs         = ["data"]         # output port names

    def build_config(self, parent, params, on_change, columns=None):
        self.add_entry(parent, "Label", "param_key", params, on_change, row=0)

    def execute(self, params, inputs, log):
        df = inputs.get("data")
        if df is None:
            raise ValueError("No input")
        # ... transform df ...
        log(f"MyTool: {len(result)} rows")
        return {"data": result}

    def to_code(self, params, input_vars, output_var, connected_outs=None):
        iv = input_vars[0] if input_vars else "df"
        return [f"{output_var} = {iv}.copy()  # TODO"]
```

2. Register it in `nodes/__init__.py` — add the import and include the class in `_TOOL_CLASSES`.

3. Add its colour to `TOOL_COLORS` in `constants.py`.

4. Add it to the right category in `CATEGORIES` in `constants.py`.

---

## Development

### Install dev dependencies

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
pytest --cov --cov-report=term-missing   # with coverage
```

### Lint / format

```bash
ruff check .        # lint
ruff format .       # format
```

---

## Project file format

Pipelines are saved as JSON (`.json`). The format is human-readable and version-controlled cleanly.

```jsonc
{
  "version": 3,
  "nodes": [
    { "id": "a1b2c3d4", "kind": "import_csv", "x": 80, "y": 120,
      "params": { "file_path": "data/sales.csv", "delimiter": "comma" },
      "disabled": false, "annotation": "" }
  ],
  "edges": [
    { "id": "e1f2g3h4", "src_node": "a1b2c3d4", "src_port": "data",
      "dst_node": "i9j8k7l6", "dst_port": "data" }
  ]
}
```

`FORMAT_VERSION` is bumped when the schema changes. `load_project()` validates the version field.

---

## Known limitations (current scope)

- Input sources: CSV and Excel only — no database connectors
- Single-user, single-machine — no collaboration or sharing
- Batch processing only — no streaming
- No scheduling — pipelines run interactively
- No visualisation — output is tabular data or Python scripts

See [ROADMAP.md](ROADMAP.md) for planned enhancements.
