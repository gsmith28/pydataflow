# PyDataFlow — Roadmap

This document tracks planned enhancements. Items are grouped by theme and roughly ordered by priority within each theme. Nothing here is committed to a timeline.

Status labels: `[ ]` not started · `[~]` in progress · `[x]` done

---

## 1. Code quality & internal health

These are not visible to users but make the codebase safer to extend.

- [x] **Extract `DELIM_MAP` to `constants.py`** — single source of truth, used by `input_output.py` and `column_inference.py`.
- [x] **Extract `BaseTool._normalize_columns()`** — coercion of a `params` value to `list[str]` is now a single helper on `BaseTool`, applied across all node modules.
- [x] **Add type hints to `BaseTool` contract** — `build_config`, `execute`, `to_code`, and `subtitle` are fully typed (with `OnChange`/`Log` aliases) so subclasses get IDE support.
- [x] **Split `app.py`** — canvas interaction (click/drag/wire, zoom/pan, view framing) extracted to `canvas_controller.py`; `app.py` keeps graph ops, palette/properties UI, and project I/O. Verified by manual click-test (GUI has no automated coverage). Further splits (e.g. project I/O) remain possible.
- [x] **Split `nodes/preparation.py`** — split by concern into `nodes/columns.py` (select, rename, retype, derive, cleanse, record id) and `nodes/rows.py` (filter, sort, head/tail).
- [ ] **Typed `node.params`** — currently `dict[str, Any]`. Defining per-tool param dataclasses (or TypedDicts) would enable validation and IDE completion.
- [ ] **Custom exception type** — replace bare `raise ValueError(...)` in tool execute methods with a `FlowExecutionError` that carries the node ID, enabling better error display.

---

## 2. Test coverage

- [ ] **`tests/test_engine.py`** — topological sort (linear chain, diamond, cycle detection), execute_flow (correct order, disabled nodes, error propagation)
- [ ] **`tests/test_nodes.py`** — execute() for each tool class with representative inputs
- [ ] **`tests/test_export.py`** — generate_python() round-trip: build a small graph, export, exec the output, compare DataFrames
- [ ] **`tests/test_project_io.py`** — save/load round-trip, version field, malformed JSON
- [ ] **`tests/test_column_inference.py`** — column propagation through select, filter, join
- [x] **CI via GitHub Actions** — runs `ruff check` and `pytest` on every push and PR (`.github/workflows/ci.yml`).

---

## 3. New data sources

- [ ] **Database connector (SQLite)** — `Import SQLite` node: connection string + query. No extra dependencies (sqlite3 is stdlib).
- [ ] **Database connector (generic via SQLAlchemy)** — `Import SQL` node with a connection string field. Optional dependency; shows a helpful error if SQLAlchemy is not installed.
- [ ] **JSON import** — `Import JSON` node: path + optional `orient` parameter.
- [ ] **Parquet import/export** — `Import Parquet` / `Export Parquet` nodes. Requires `pyarrow` (already in the NiceGUI prototype's requirements).
- [ ] **Clipboard import** — `Paste from clipboard` node: reads tab-separated data from the system clipboard for quick paste from Excel.

---

## 4. New transformation tools

- [ ] **Text: Split Column** — split a string column into N columns on a delimiter (inverse of "Text to Columns" from the NiceGUI prototype).
- [ ] **Text: Regex Extract** — extract capture groups from a column into new columns.
- [ ] **Date: Date Parts** — extract year, month, day, weekday, quarter into separate columns.
- [ ] **Date: Date Diff** — compute the difference between two date columns in configurable units.
- [ ] **Window Functions** — rolling average, cumulative sum, rank within group.
- [ ] **Sample** — random sample by count or fraction; supports reproducible seed.
- [ ] **Transpose** — flip rows and columns (useful for wide-format data with row-oriented headers).
- [ ] **Cross-join** — produce the Cartesian product of two tables.
- [ ] **Lookup / Map values** — map a column's values to new values using a user-supplied dictionary.

---

## 5. Canvas and UX improvements

- [ ] **Keyboard shortcuts** — Delete to remove selected node, Ctrl+Z/Y undo/redo, Ctrl+S save, Space to pan.
- [ ] **Multi-select** — Ctrl+click or drag-select a region; move or delete multiple nodes at once.
- [ ] **Undo / redo** — command stack for node add/delete/move/connect. Currently every action is irreversible without "Open" reverting to saved state.
- [ ] **Minimap** — small overview panel in the corner showing the full canvas with a viewport indicator.
- [ ] **Auto-layout** — a "tidy layout" button that arranges nodes left-to-right in topological order.
- [ ] **Edge labels** — show port names on wires when a node has multiple output ports.
- [ ] **Inline data preview on node** — show row count badge directly on the node after a run (currently only in the properties panel).
- [x] **Collapsible palette sections** — each category header collapses/expands; the collapsed set persists across sessions via `settings.py`.
- [x] **Persisted preferences** — `settings.py` stores window geometry, last-used folder for file dialogs, and palette collapsed state in `~/.pydataflow/settings.json`.
- [ ] **Search palette** — type-to-filter the tool palette rather than scrolling.
- [ ] **Recent files** — File menu with last 5 opened projects. (`settings.py` already provides the persistence layer to build on.)

---

## 6. Execution improvements

- [ ] **Incremental execution** — only re-run nodes whose parameters or upstream data changed since the last run. Cache node results.
- [ ] **Run-to-node** — right-click a node → "Run up to here" without executing downstream.
- [ ] **Background execution** — run the pipeline in a thread so the UI stays responsive; show a progress indicator.
- [ ] **Row-count warnings** — warn the user if a node produces 0 rows (possible misconfiguration) or more than N rows (possible performance issue).
- [ ] **Execution profiling** — show per-node elapsed time in the log and as a visual badge on the node.

---

## 7. Export and sharing

- [ ] **Export to Jupyter notebook** — generate a `.ipynb` with cells per node, markdown explanations, and inline previews.
- [ ] **Export to SQL** — where possible, generate equivalent SQL instead of pandas code.
- [ ] **Pipeline sharing** — a CLI mode: `python main.py --run pipeline.json --input data.csv --output result.csv` (headless execution).
- [ ] **Pipeline parameters** — designate certain node params as "runtime parameters" that can be overridden on the CLI or via a launch dialog.

---

## 8. Longer-term / speculative

- [ ] **Custom tool builder** (port from NiceGUI prototype) — UI for defining a new tool by writing a Python snippet, without editing source code.
- [ ] **Plugin system** — load additional tool modules from a user-specified directory.
- [ ] **Dark / light theme toggle** — currently hardcoded dark theme.
- [ ] **Accessibility** — keyboard-navigable canvas, screen-reader-friendly widget labels.
- [ ] **Packaging** — `pyinstaller` or `cx_Freeze` build for a single-file executable that non-Python users can run.
