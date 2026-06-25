# PyDataFlow — UI constants
DARK_BG   = "#1e1e2e"
PANEL_BG  = "#252535"
CANVAS_BG = "#1a1a2e"
NODE_BG   = "#2d2d44"
ENTRY_BG  = "#1a1a28"
TEXT_FG   = "#c0c0d8"
DIM_FG    = "#7878a0"
GRID_COLOR = "#252535"
EDGE_COLOR = "#6878b0"
EDGE_WIRE  = "#88ccff"
SELECT_OUTLINE = "#5588ff"
PORT_IN_COLOR  = "#44aaff"
PORT_OUT_COLOR = "#ffaa44"
RESULT_OUTLINE = "#44cc88"

# Node geometry (world units)
NODE_W  = 170
NODE_H  = 76
TITLE_H = 26
PORT_R  = 5

# Container defaults
CONTAINER_DEFAULT_W = 280
CONTAINER_DEFAULT_H = 180

CATEGORIES = [
    ("Input / Output",       ["import_csv","import_excel","show_table","export_csv","export_excel"]),
    ("Preparation",          ["select_columns","filter_rows","sort","head_tail","rename_columns",
                              "edit_columns","add_columns","cleansing","record_id"]),
    ("Join / Reconcile",     ["merge_join","union","unique_duplicate"]),
    ("Transform / Summarize",["summarize","group_by","pivot","unpivot"]),
    ("Documentation",        ["comment","container"]),
]

DELIM_MAP = {
    "comma": ",",
    "tab": "\t",
    "pipe": "|",
    "semicolon": ";",
}

TOOL_COLORS = {
    "import_csv":       "#2d9e5a",
    "import_excel":     "#2d9e5a",
    "show_table":       "#2d9e5a",
    "export_csv":       "#2d9e5a",
    "export_excel":     "#2d9e5a",
    "select_columns":   "#2a85c4",
    "filter_rows":      "#2a85c4",
    "sort":             "#2a85c4",
    "head_tail":        "#2a85c4",
    "rename_columns":   "#2a85c4",
    "edit_columns":     "#2a85c4",
    "add_columns":      "#2a85c4",
    "cleansing":        "#2a85c4",
    "record_id":        "#2a85c4",
    "merge_join":       "#a03070",
    "union":            "#a03070",
    "unique_duplicate": "#a03070",
    "summarize":        "#a06020",
    "group_by":         "#a06020",
    "pivot":            "#a06020",
    "unpivot":          "#a06020",
    "comment":          "#5a5a8a",
    "container":        "#404060",
}
