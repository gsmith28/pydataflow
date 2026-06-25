# backend/ — Prior NiceGUI/FastAPI Prototype

> **This directory is not part of the active application.**

## What this is

An earlier, alternative implementation of PyDataFlow built on a web-based stack:

- **FastAPI** for the REST API layer
- **NiceGUI** for the UI (served at `http://localhost:8080`)
- **Drawflow.js** for the canvas
- **SQLite via aiosqlite** for project persistence

It was built before the tkinter desktop app and explored a different architectural direction: a locally-served web app rather than a native desktop window.

## Why it was set aside

The tkinter approach better matched the product goals:
- No browser dependency
- Instant startup (no server boot)
- Simpler distribution (just `python main.py`)
- Easier file system access for local CSV/Excel files

## What it contains

| Directory | Description |
|---|---|
| `api/` | FastAPI routers: workflows, execution, tools, custom tools, files |
| `engine/` | Graph executor and Python code generator (parallel to root `engine.py` + `export_script.py`) |
| `models/` | Pydantic models for workflows, nodes, edges, run results |
| `storage/` | SQLite persistence via aiosqlite |
| `tools/` | 27 tool implementations (more than the tkinter version) |
| `ui/` | NiceGUI page components |
| `app.py` | Entry point: `python backend/app.py` |
| `requirements.txt` | Dependencies (**note:** `nicegui` is missing from this file — install separately) |

## If you want to run it

```bash
pip install nicegui fastapi uvicorn pandas openpyxl pyarrow aiosqlite python-multipart
python backend/app.py
# → open http://localhost:8080
```

## Should I delete this?

When the tkinter app reaches feature parity with what's here (notably: custom tool builder, run history, profiling tools, audit tests), this directory can be removed. Until then it is a useful reference for those features.
