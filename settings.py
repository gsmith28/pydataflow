"""User settings that persist across sessions.

Stored as JSON in ``~/.pydataflow/settings.json``. This is per-user preference
(window geometry, last-used folder, collapsed palette sections) — distinct from
``project_io`` which serialises the pipeline graph itself.

A module-level cache backs simple ``get``/``set`` helpers so both ``app.py`` and
``nodes/base.py`` (which builds file-browse buttons) share one source of truth
without threading the ``FlowApp`` instance through every widget helper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_APP_DIR = Path.home() / ".pydataflow"
_SETTINGS_PATH = _APP_DIR / "settings.json"

_DEFAULTS: dict[str, Any] = {
    "window_geometry": "",
    "last_dir": "",
    "palette_collapsed": [],
}

_cache: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    data = dict(_DEFAULTS)
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            stored = json.load(f)
        if isinstance(stored, dict):
            for k in _DEFAULTS:
                if k in stored:
                    data[k] = stored[k]
    except (OSError, ValueError):
        pass  # Missing or corrupt file → fall back to defaults.
    return data


def _all() -> dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def _save() -> None:
    try:
        _APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(_all(), f, indent=2)
    except OSError:
        pass  # Persistence is best-effort; never block the UI on a write failure.


def get(key: str) -> Any:
    return _all().get(key, _DEFAULTS.get(key))


def set(key: str, value: Any) -> None:  # noqa: A001 - mirrors dict semantics intentionally
    _all()[key] = value
    _save()


def last_dir() -> str | None:
    """Directory for a file dialog's ``initialdir`` (``None`` if unset)."""
    return get("last_dir") or None


def remember_path(path: str | None) -> None:
    """Record the folder of a chosen file so the next dialog opens there."""
    if path:
        set("last_dir", str(Path(path).parent))
