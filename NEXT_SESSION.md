# Next session handoff — Phase 4: split `app.py`

**Repo state at handoff:** clean. Everything committed and pushed to `origin/main`
(latest: `88448bb`). 42/42 tests pass, ruff clean. Safe to start fresh.

---

## The task

`app.py` is ~900 lines mixing four concerns: canvas event handling, zoom/pan,
project I/O, and UI construction. Split the **canvas event + zoom/pan** concern
into a new `canvas_controller.py`, leaving `app.py` as a thin orchestrator that
owns the window, the tool palette, the properties panel, and wiring between them.

This is GUI code with **no test coverage**, so it cannot be verified headlessly.
It must be split in small, runnable increments and click-tested by hand after each
meaningful step. Do NOT do it as one big move.

### Suggested approach (incremental, each step must keep `python main.py` working)
1. Read `app.py` end to end and map which methods touch: canvas events
   (mouse down/move/up, click hit-testing), zoom/pan (wheel, `_s2w`, pan offsets),
   project I/O, and palette/properties UI.
2. Introduce `canvas_controller.py` holding a `CanvasController` that takes a
   reference to the `FlowApp` (or the canvas + shared state it needs).
3. Move ONE cohesive group first — zoom/pan — then run + click-test before moving
   the event-handling group. Commit after each green click-test.
4. Keep coordinate-system invariants intact: `screen = world * zoom + pan`,
   `_s2w()` converts screen → world. `renderer.py` reads `app.zoom`,
   `app.pan_x`, `app.pan_y` — preserve those attribute names or update renderer
   in the same commit.

### Constraints (unchanged)
- "Just Python": stdlib tkinter + pandas/openpyxl only. No new deps, no packaging.
- Do NOT move files into a package — imports rely on root-level `sys.path.insert`.
- One concern per commit. Include the `Co-Authored-By` trailer.
- Owner pushes direct to `main`; the "Required status check expected" notice on
  push is expected/benign.

---

## Commands to run

```bash
# sanity check before starting
python -m ruff check .
python -m pytest -q          # expect 42 passed

# after each increment
python -m ruff check .
python -m pytest -q
python main.py               # MANUAL click-test (see checklist)
```

### Manual click-test checklist (after each increment and at the end)
- Drag a tool from the palette onto the canvas
- Wire two nodes together (drag port → port)
- Pan (drag background) and zoom (mouse wheel) — nodes track the cursor correctly
- Select a node; edit a param in the properties panel
- Run the pipeline (▶) — log updates, preview shows
- Save, then Open the project — graph round-trips

If anything misbehaves, revert the last increment (it's committed separately) and
narrow the move.
