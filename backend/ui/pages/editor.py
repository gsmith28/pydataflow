"""Main workflow editor page."""
from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Any

from nicegui import ui, app

from models.workflow import Workflow, WorkflowNode, WorkflowEdge, Position
from engine.executor import execute_workflow
from engine.codegen import generate_python
from storage.project_store import list_workflows, get_workflow, save_workflow
from storage.run_history import save_run
from tools.registry import all_tools
from ui.components.config_forms import render_config_schema
from ui.components.data_preview import render_data_preview, render_schema_view


TOOL_COLORS: dict[str, str] = {
    "Input / Output": "#3b82f6",
    "Preparation": "#10b981",
    "Join / Reconcile": "#f59e0b",
    "Transform / Summarize": "#8b5cf6",
    "Data Quality / Profiling": "#06b6d4",
    "Audit Tests / Controls": "#ef4444",
    "Parse / Standardize": "#ec4899",
    "Custom Tools": "#6366f1",
}

TOOL_ICONS: dict[str, str] = {
    "input_data": "upload_file",
    "browse_preview": "preview",
    "output_data": "save",
    "count_records": "tag",
    "select_fields": "view_column",
    "filter": "filter_alt",
    "formula": "functions",
    "sort": "sort",
    "unique_duplicate": "content_copy",
    "record_id": "pin",
    "data_cleansing": "cleaning_services",
    "sample": "shuffle",
    "join": "merge",
    "union": "call_merge",
    "find_replace_lookup": "find_replace",
    "summarize": "summarize",
    "crosstab_pivot": "pivot_table_chart",
    "transpose_unpivot": "swap_vert",
    "field_summary": "assessment",
    "frequency_table": "bar_chart",
    "test": "fact_check",
    "message": "message",
    "field_info": "info",
    "expect_equal": "compare",
    "datetime_parse": "schedule",
    "text_to_columns": "table_chart",
    "regex": "code",
}


def _group_tools() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for t in all_tools():
        cat = t["category"]
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(t)
    return groups


def _node_label(node: WorkflowNode) -> str:
    return node.display_name or node.tool_type.replace("_", " ").title()


def _drawflow_node_data(node: WorkflowNode, tool_info: dict | None) -> dict:
    color = TOOL_COLORS.get(tool_info["category"] if tool_info else "Custom Tools", "#6366f1")
    icon = TOOL_ICONS.get(node.tool_type, "extension")
    label = _node_label(node)
    inputs = {p: {} for p in (tool_info["input_ports"] if tool_info else node.input_ports)}
    outputs = {p: {} for p in (tool_info["output_ports"] if tool_info else node.output_ports)}
    return {
        "name": node.tool_type,
        "data": {
            "node_id": node.node_id,
            "label": label,
            "color": color,
            "icon": icon,
            "tool_type": node.tool_type,
        },
        "class": "pydataflow-node",
        "html": _node_html(label, color, icon, node.node_id),
        "inputs": {f"input_{p}": {"connections": []} for p in inputs},
        "outputs": {f"output_{p}": {"connections": []} for p in outputs},
        "pos_x": node.position.x,
        "pos_y": node.position.y,
    }


def _node_html(label: str, color: str, icon: str, node_id: str) -> str:
    return f"""
    <div class="pf-node" data-node-id="{node_id}" style="border-top:3px solid {color}">
      <div class="pf-node-header" style="background:{color}20">
        <span class="material-icons" style="color:{color};font-size:16px">{icon}</span>
        <span class="pf-node-label">{label}</span>
      </div>
    </div>
    """


_DRAWFLOW_CSS = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/drawflow@0.0.59/dist/drawflow.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
<style>
  .drawflow { background-color: #f8fafc; }
  .drawflow .drawflow-node { background:#fff; border:1px solid #e2e8f0; border-radius:8px;
    box-shadow:0 1px 4px rgba(0,0,0,.08); padding:0; min-width:160px; cursor:pointer; }
  .drawflow .drawflow-node.selected { border-color:#3b82f6; box-shadow:0 0 0 2px #93c5fd; }
  .pf-node-header { display:flex; align-items:center; gap:6px; padding:6px 10px 6px 8px;
    border-radius:5px 5px 0 0; }
  .pf-node-label { font-size:12px; font-weight:600; color:#1e293b; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; max-width:130px; }
  .drawflow .input, .drawflow .output { width:12px; height:12px; border-radius:50%;
    border:2px solid #94a3b8; background:#fff; }
  .drawflow .input:hover, .drawflow .output:hover { border-color:#3b82f6; background:#dbeafe; }
  .drawflow-delete { background:#ef4444; border:none; border-radius:50%; width:18px; height:18px;
    font-size:12px; color:#fff; cursor:pointer; display:flex; align-items:center; justify-content:center; }
  #drawflow-canvas { width:100%; height:100%; }
  .pf-node-badge { background:#f1f5f9; border-radius:0 0 6px 6px; padding:2px 8px;
    font-size:10px; color:#64748b; display:flex; justify-content:space-between; }
</style>
"""

_DRAWFLOW_INIT_JS = """
<script src="https://cdn.jsdelivr.net/npm/drawflow@0.0.59/dist/drawflow.min.js"></script>
<script>
window._pf = window._pf || {};

function pfInitDrawflow() {
  const container = document.getElementById('drawflow-canvas');
  if (!container) { setTimeout(pfInitDrawflow, 200); return; }

  const editor = new Drawflow(container);
  editor.reroute = true;
  editor.reroute_fix_curvature = true;
  editor.force_first_input = false;
  editor.start();
  window._pf.editor = editor;
  window._pf.nodeMap = {};   // drawflow_id -> node_id
  window._pf.nodeMapRev = {}; // node_id -> drawflow_id

  editor.on('nodeSelected', function(id) {
    const node = editor.getNodeFromId(id);
    const nodeId = node && node.data && node.data.node_id;
    if (nodeId) {
      fetch('/pf/node-selected', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({node_id: nodeId})
      });
    }
  });

  editor.on('nodeUnselected', function() {
    fetch('/pf/node-selected', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({node_id: null})
    });
  });

  editor.on('nodeMoved', function(id) {
    const node = editor.getNodeFromId(id);
    const nodeId = node && node.data && node.data.node_id;
    if (nodeId) {
      fetch('/pf/node-moved', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({node_id: nodeId, x: node.pos_x, y: node.pos_y})
      });
    }
  });

  editor.on('connectionCreated', function(info) {
    const srcNode = editor.getNodeFromId(info.output_id);
    const tgtNode = editor.getNodeFromId(info.input_id);
    if (!srcNode || !tgtNode) return;
    const srcPort = info.output_class.replace('output_', '');
    const tgtPort = info.input_class.replace('input_', '');
    fetch('/pf/edge-created', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_node_id: srcNode.data.node_id,
        source_port: srcPort,
        target_node_id: tgtNode.data.node_id,
        target_port: tgtPort,
        df_src_id: info.output_id,
        df_tgt_id: info.input_id,
      })
    });
  });

  editor.on('connectionRemoved', function(info) {
    const srcNode = editor.getNodeFromId(info.output_id);
    const tgtNode = editor.getNodeFromId(info.input_id);
    if (!srcNode || !tgtNode) return;
    const srcPort = info.output_class.replace('output_', '');
    const tgtPort = info.input_class.replace('input_', '');
    fetch('/pf/edge-removed', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_node_id: srcNode.data.node_id,
        source_port: srcPort,
        target_node_id: tgtNode.data.node_id,
        target_port: tgtPort,
      })
    });
  });

  editor.on('nodeRemoved', function(id) {
    const nodeId = window._pf.nodeMap[id];
    if (nodeId) {
      fetch('/pf/node-removed', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({node_id: nodeId})
      });
      delete window._pf.nodeMapRev[nodeId];
      delete window._pf.nodeMap[id];
    }
  });

  // Load workflow if already stored
  const wf = window._pf.pendingWorkflow;
  if (wf) { pfLoadWorkflow(wf); window._pf.pendingWorkflow = null; }
}

function pfLoadWorkflow(wfData) {
  const editor = window._pf.editor;
  if (!editor) { window._pf.pendingWorkflow = wfData; return; }
  editor.clearModuleSelected();
  window._pf.nodeMap = {};
  window._pf.nodeMapRev = {};

  const nodes = wfData.nodes || [];
  const edges = wfData.edges || [];

  for (const node of nodes) {
    const dfId = editor.addNode(
      node.tool_type,
      node.input_ports.length,
      node.output_ports.length,
      node.position.x || 100,
      node.position.y || 100,
      'pydataflow-node',
      { node_id: node.node_id, label: node.display_name, color: node.color || '#3b82f6',
        icon: node.icon || 'extension', tool_type: node.tool_type },
      node._html || pfNodeHtml(node)
    );
    window._pf.nodeMap[dfId] = node.node_id;
    window._pf.nodeMapRev[node.node_id] = dfId;
  }

  for (const edge of edges) {
    const srcDfId = window._pf.nodeMapRev[edge.source_node_id];
    const tgtDfId = window._pf.nodeMapRev[edge.target_node_id];
    if (srcDfId && tgtDfId) {
      try {
        editor.addConnection(srcDfId, tgtDfId,
          'output_' + edge.source_port, 'input_' + edge.target_port);
      } catch(e) { console.warn('Could not add edge:', e); }
    }
  }
}

function pfNodeHtml(node) {
  const color = node.color || '#3b82f6';
  const icon = node.icon || 'extension';
  const label = node.display_name || node.tool_type;
  return `<div class="pf-node" data-node-id="${node.node_id}" style="border-top:3px solid ${color}">
    <div class="pf-node-header" style="background:${color}20">
      <span class="material-icons" style="color:${color};font-size:16px">${icon}</span>
      <span class="pf-node-label">${label}</span>
    </div>
  </div>`;
}

function pfAddNode(nodeData) {
  const editor = window._pf.editor;
  if (!editor) return;
  const color = nodeData.color || '#3b82f6';
  const icon = nodeData.icon || 'extension';
  const label = nodeData.display_name || nodeData.tool_type;
  const html = pfNodeHtml({...nodeData, display_name: label, color, icon});
  const inputCount = (nodeData.input_ports || []).length;
  const outputCount = (nodeData.output_ports || []).length;

  const dfId = editor.addNode(
    nodeData.tool_type,
    inputCount,
    outputCount,
    nodeData.position ? nodeData.position.x : 200,
    nodeData.position ? nodeData.position.y : 200,
    'pydataflow-node',
    { node_id: nodeData.node_id, label, color, icon, tool_type: nodeData.tool_type },
    html
  );
  window._pf.nodeMap[dfId] = nodeData.node_id;
  window._pf.nodeMapRev[nodeData.node_id] = dfId;
}

function pfHighlightNode(nodeId, success) {
  const dfId = window._pf.nodeMapRev && window._pf.nodeMapRev[nodeId];
  if (!dfId) return;
  const el = document.querySelector(`.drawflow-node[id="node-${dfId}"]`);
  if (!el) return;
  el.style.outline = success ? '2px solid #10b981' : '2px solid #ef4444';
  setTimeout(() => { el.style.outline = ''; }, 2000);
}

function pfClearCanvas() {
  const editor = window._pf.editor;
  if (editor) editor.clearModuleSelected();
  window._pf.nodeMap = {};
  window._pf.nodeMapRev = {};
}

document.addEventListener('DOMContentLoaded', function() {
  setTimeout(pfInitDrawflow, 300);
});
</script>
"""


def create_editor_page(base_path: str = ".") -> None:
    """Register the /editor NiceGUI page."""

    @ui.page("/")
    async def editor_page():
        await _render_editor(base_path)

    @ui.page("/editor")
    async def editor_page2():
        await _render_editor(base_path)


async def _render_editor(base_path: str) -> None:
    ui.add_head_html(_DRAWFLOW_CSS)
    ui.add_head_html(_DRAWFLOW_INIT_JS)

    storage = app.storage.user
    if "workflow" not in storage:
        storage["workflow"] = Workflow(name="New Workflow").model_dump()
    if "run_result" not in storage:
        storage["run_result"] = None
    if "selected_node_id" not in storage:
        storage["selected_node_id"] = None

    def get_wf() -> Workflow:
        return Workflow.model_validate(storage["workflow"])

    def save_wf(wf: Workflow) -> None:
        storage["workflow"] = wf.model_dump()

    # ── Top bar ──────────────────────────────────────────────────────────────
    with ui.header().classes("bg-slate-800 text-white items-center px-4 py-2 gap-3"):
        ui.label("PyDataFlow").classes("text-lg font-bold text-blue-300")
        ui.separator().props("vertical").classes("opacity-30")

        name_input = ui.input(value=get_wf().name).classes("bg-slate-700 text-white rounded px-2 w-48").props("dense borderless")

        async def on_name_change(e):
            wf = get_wf()
            wf.name = e.value
            save_wf(wf)

        name_input.on("update:model-value", on_name_change)

        ui.space()

        async def new_workflow():
            wf = Workflow(name="New Workflow")
            save_wf(wf)
            storage["selected_node_id"] = None
            storage["run_result"] = None
            await ui.run_javascript("pfClearCanvas()")
            right_panel.refresh()
            ui.notify("New workflow created", type="info")

        async def open_dialog():
            workflows = await list_workflows()
            with ui.dialog() as dlg, ui.card().classes("min-w-96"):
                ui.label("Open Workflow").classes("text-lg font-bold mb-2")
                if not workflows:
                    ui.label("No saved workflows.").classes("text-gray-500")
                else:
                    for w in workflows:
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label(w["name"]).classes("flex-1")
                            ui.label(w["updated_at"][:10]).classes("text-xs text-gray-400")

                            async def load(wid=w["workflow_id"]):
                                loaded = await get_workflow(wid)
                                if loaded:
                                    save_wf(loaded)
                                    storage["selected_node_id"] = None
                                    wf_data = loaded.model_dump()
                                    await ui.run_javascript(f"pfLoadWorkflow({json.dumps(wf_data)})")
                                    name_input.value = loaded.name
                                    right_panel.refresh()
                                    dlg.close()
                                    ui.notify(f"Loaded: {loaded.name}", type="positive")

                            ui.button("Open", on_click=load).props("flat dense color=blue")
                ui.button("Cancel", on_click=dlg.close).props("flat")
            dlg.open()

        async def save_wf_to_db():
            wf = get_wf()
            saved = await save_workflow(wf)
            save_wf(saved)
            ui.notify("Saved", type="positive")

        async def run_all():
            wf = get_wf()
            with ui.notification("Running workflow…", spinner=True, timeout=None) as n:
                result = execute_workflow(
                    wf,
                    project_dir=Path(base_path),
                    temp_dir=Path("/tmp/pydataflow"),
                    preview_limit=50,
                )
                await save_run(result)
                storage["run_result"] = result.model_dump()
                for node_id, port_results in result.node_results.items():
                    ok = all(not r.errors for r in port_results)
                    await ui.run_javascript(f"pfHighlightNode({json.dumps(node_id)}, {json.dumps(ok)})")
                n.dismiss()
            status = result.status.upper()
            color = "positive" if status == "SUCCESS" else "negative"
            ui.notify(f"Run {status} — {len(result.errors)} error(s)", type=color)
            right_panel.refresh()

        async def export_python():
            wf = get_wf()
            code = generate_python(wf)
            with ui.dialog() as dlg, ui.card().classes("w-full max-w-4xl"):
                ui.label("Exported Python").classes("text-lg font-bold")
                ui.code(code, language="python").classes("w-full text-xs")
                with ui.row():
                    ui.button("Copy to clipboard", on_click=lambda: ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(code)}); ")).props("flat color=blue")
                    ui.button("Close", on_click=dlg.close).props("flat")
            dlg.open()

        ui.button(icon="add", on_click=new_workflow).props("flat dense color=white").tooltip("New")
        ui.button(icon="folder_open", on_click=open_dialog).props("flat dense color=white").tooltip("Open")
        ui.button(icon="save", on_click=save_wf_to_db).props("flat dense color=white").tooltip("Save")
        ui.button("▶ Run", on_click=run_all).classes("bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm font-medium")
        ui.button(icon="code", on_click=export_python).props("flat dense color=white").tooltip("Export Python")

    # ── Main layout ──────────────────────────────────────────────────────────
    with ui.row().classes("w-full flex-nowrap").style("height: calc(100vh - 52px); overflow:hidden"):

        # ── Left: Tool palette ────────────────────────────────────────────────
        with ui.scroll_area().classes("bg-slate-50 border-r").style("width:280px;min-width:280px;height:100%;"):
            ui.label("Tools").classes("text-xs font-bold text-gray-400 uppercase tracking-widest px-3 pt-4 pb-1")
            ui.label("Click any tool to add it to the canvas").classes("text-xs text-gray-400 italic px-3 pb-3")
            groups = _group_tools()
            for category, cat_tools in groups.items():
                color = TOOL_COLORS.get(category, "#6366f1")
                with ui.expansion(category).classes("w-full").props("default-opened dense"):
                    for tool in cat_tools:
                        t_icon = TOOL_ICONS.get(tool["tool_type"], "extension")

                        def make_add_handler(t=tool):
                            async def _handler():
                                await _add_node_from_tool(t, storage, save_wf, get_wf)
                            return _handler

                        with ui.button(on_click=make_add_handler()).classes(
                            "w-full text-left justify-start rounded-none"
                        ).props("flat dense no-caps").style("border-bottom:1px solid #f1f5f9; padding:6px 12px"):
                            ui.icon(t_icon, size="xs").style(f"color:{color};margin-right:8px;min-width:18px")
                            with ui.column().classes("items-start gap-0"):
                                ui.label(tool["display_name"]).classes("text-sm font-medium text-slate-700")
                                desc = tool.get("description", "")
                                if desc:
                                    ui.label(desc[:50]).classes("text-xs text-gray-400")


        # ── Center: Canvas ────────────────────────────────────────────────────
        with ui.element("div").classes("flex-1 relative overflow-hidden"):
            ui.html('<div id="drawflow-canvas" style="width:100%;height:100%;"></div>')

            # Load current workflow into canvas on page ready
            wf_json = json.dumps(get_wf().model_dump())
            ui.timer(
                0.5,
                lambda: ui.run_javascript(f"pfLoadWorkflow({wf_json})"),
                once=True,
            )

        # ── Right: Config + Results ───────────────────────────────────────────
        @ui.refreshable
        def right_panel():
            with ui.scroll_area().style("width:340px;min-width:340px;"):
                _render_right_panel(storage, get_wf, save_wf, base_path)

        right_panel()

    # Register FastAPI endpoints for canvas events
    _register_canvas_routes(storage, save_wf, get_wf, right_panel)


async def _add_node_from_tool(tool: dict, storage, save_wf, get_wf) -> None:
    wf = get_wf()
    # Stagger new nodes so they don't stack
    n = len(wf.nodes)
    x = 120 + (n % 4) * 220
    y = 80 + (n // 4) * 160
    node = WorkflowNode(
        tool_type=tool["tool_type"],
        display_name=tool["display_name"],
        input_ports=tool["input_ports"],
        output_ports=tool["output_ports"],
        position=Position(x=x, y=y),
    )
    wf.nodes.append(node)
    save_wf(wf)

    node_data = {
        **node.model_dump(),
        "color": TOOL_COLORS.get(tool["category"], "#6366f1"),
        "icon": TOOL_ICONS.get(tool["tool_type"], "extension"),
    }
    await ui.run_javascript(f"pfAddNode({json.dumps(node_data)})")


def _render_right_panel(storage, get_wf, save_wf, base_path: str) -> None:
    selected_id = storage.get("selected_node_id")
    run_result = storage.get("run_result")
    wf = get_wf()

    with ui.tabs().classes("w-full") as tabs:
        config_tab = ui.tab("Config")
        results_tab = ui.tab("Results")
        history_tab = ui.tab("Schema")

    with ui.tab_panels(tabs, value=config_tab).classes("w-full"):
        with ui.tab_panel(config_tab):
            if not selected_id:
                with ui.column().classes("w-full p-4 items-center gap-3"):
                    ui.icon("touch_app", size="xl").classes("text-gray-300")
                    ui.label("Click a node to configure it").classes("text-gray-400 text-sm text-center")
                return

            node = next((n for n in wf.nodes if n.node_id == selected_id), None)
            if not node:
                ui.label("Node not found").classes("text-gray-400 text-sm")
                return

            from tools.registry import get_tool
            tool = get_tool(node.tool_type)

            with ui.column().classes("w-full p-3 gap-1"):
                ui.label(_node_label(node)).classes("text-base font-bold text-slate-800")
                if tool:
                    ui.label(tool.description).classes("text-xs text-gray-500 mb-2")

                with ui.row().classes("w-full items-center gap-1 mb-2"):
                    ui.label("Display name").classes("text-xs text-gray-500 w-24")
                    dn_input = ui.input(value=node.display_name).classes("flex-1").props("dense")

                    def on_display_name(e):
                        n = next((x for x in get_wf().nodes if x.node_id == selected_id), None)
                        if n:
                            n.display_name = e.value
                            save_wf(get_wf())

                    dn_input.on("update:model-value", on_display_name)

                with ui.row().classes("w-full items-center gap-1 mb-2"):
                    ui.label("Annotation").classes("text-xs text-gray-500 w-24")
                    ann_input = ui.input(value=node.annotation).classes("flex-1").props("dense")

                    def on_annotation(e):
                        n = next((x for x in get_wf().nodes if x.node_id == selected_id), None)
                        if n:
                            n.annotation = e.value
                            save_wf(get_wf())

                    ann_input.on("update:model-value", on_annotation)

                ui.separator()

                if tool and tool.config_schema:
                    columns: list[str] = []
                    if run_result:
                        nr = run_result.get("node_results", {})
                        for nid, ports in nr.items():
                            for port_result in ports:
                                if port_result.get("output_schema"):
                                    columns = [f["name"] for f in port_result["output_schema"].get("fields", [])]

                    def on_config_change():
                        wf2 = get_wf()
                        n2 = next((x for x in wf2.nodes if x.node_id == selected_id), None)
                        if n2:
                            n2.config = node.config
                            save_wf(wf2)

                    render_config_schema(tool.config_schema, node.config, columns, on_config_change)
                else:
                    ui.label("No configuration required.").classes("text-gray-400 italic text-sm")

                ui.separator()
                with ui.row().classes("w-full gap-2 mt-2"):
                    async def delete_node():
                        wf3 = get_wf()
                        wf3.nodes = [n for n in wf3.nodes if n.node_id != selected_id]
                        wf3.edges = [e for e in wf3.edges if e.source_node_id != selected_id and e.target_node_id != selected_id]
                        storage["selected_node_id"] = None
                        save_wf(wf3)

                    ui.button("Delete node", icon="delete", color="red").props("flat dense").on("click", delete_node)

        with ui.tab_panel(results_tab):
            if not run_result:
                ui.label("Run the workflow to see results.").classes("text-gray-400 text-sm p-4")
                return

            nr = run_result.get("node_results", {})
            errors = run_result.get("errors", [])

            if errors:
                with ui.expansion("Errors", icon="error").classes("w-full"):
                    for err in errors:
                        ui.label(err).classes("text-red-600 text-xs")

            if not nr:
                ui.label("No node results available.").classes("text-gray-400 text-sm")
                return

            selected = storage.get("selected_node_id")
            wf2 = get_wf()
            display_node_id = selected if selected and selected in nr else (list(nr.keys())[-1] if nr else None)

            if not display_node_id:
                return

            node2 = next((n for n in wf2.nodes if n.node_id == display_node_id), None)
            node_name = _node_label(node2) if node2 else display_node_id

            ui.label(f"Results: {node_name}").classes("font-medium text-slate-700 px-3 pt-2")

            for port_result in nr.get(display_node_id, []):
                port = port_result.get("port", "out")
                rc = port_result.get("record_count", 0)
                with ui.expansion(f"Port: {port}  ({rc:,} rows)", icon="table_view").classes("w-full px-1"):
                    cols = port_result.get("preview_columns", [])
                    rows = port_result.get("preview_rows", [])
                    render_data_preview(cols, rows, rc)

        with ui.tab_panel(history_tab):
            if not run_result:
                ui.label("Run the workflow to see schema.").classes("text-gray-400 text-sm p-4")
                return
            nr = run_result.get("node_results", {})
            selected = storage.get("selected_node_id")
            display_node_id = selected if selected and selected in nr else (list(nr.keys())[-1] if nr else None)
            if not display_node_id:
                return
            for port_result in nr.get(display_node_id, []):
                port = port_result.get("port", "out")
                schema = port_result.get("output_schema")
                ui.label(f"Schema — port: {port}").classes("font-medium px-3 pt-2")
                render_schema_view(schema)


def _register_canvas_routes(storage, save_wf, get_wf, right_panel) -> None:
    from fastapi import Request
    from nicegui import app as ngapp

    @ngapp.post("/pf/node-selected")
    async def pf_node_selected(request: Request):
        body = await request.json()
        storage["selected_node_id"] = body.get("node_id")
        right_panel.refresh()
        return {}

    @ngapp.post("/pf/node-moved")
    async def pf_node_moved(request: Request):
        body = await request.json()
        node_id = body.get("node_id")
        x = body.get("x", 0)
        y = body.get("y", 0)
        wf = get_wf()
        node = next((n for n in wf.nodes if n.node_id == node_id), None)
        if node:
            node.position = Position(x=x, y=y)
            save_wf(wf)
        return {}

    @ngapp.post("/pf/edge-created")
    async def pf_edge_created(request: Request):
        body = await request.json()
        wf = get_wf()
        edge = WorkflowEdge(
            source_node_id=body["source_node_id"],
            source_port=body["source_port"],
            target_node_id=body["target_node_id"],
            target_port=body["target_port"],
        )
        duplicate = any(
            e.source_node_id == edge.source_node_id and e.source_port == edge.source_port
            and e.target_node_id == edge.target_node_id and e.target_port == edge.target_port
            for e in wf.edges
        )
        if not duplicate:
            wf.edges.append(edge)
            save_wf(wf)
        return {}

    @ngapp.post("/pf/edge-removed")
    async def pf_edge_removed(request: Request):
        body = await request.json()
        wf = get_wf()
        wf.edges = [
            e for e in wf.edges
            if not (
                e.source_node_id == body["source_node_id"]
                and e.source_port == body["source_port"]
                and e.target_node_id == body["target_node_id"]
                and e.target_port == body["target_port"]
            )
        ]
        save_wf(wf)
        return {}

    @ngapp.post("/pf/node-removed")
    async def pf_node_removed(request: Request):
        body = await request.json()
        node_id = body.get("node_id")
        wf = get_wf()
        wf.nodes = [n for n in wf.nodes if n.node_id != node_id]
        wf.edges = [e for e in wf.edges if e.source_node_id != node_id and e.target_node_id != node_id]
        if storage.get("selected_node_id") == node_id:
            storage["selected_node_id"] = None
        save_wf(wf)
        right_panel.refresh()
        return {}
