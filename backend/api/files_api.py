from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd

router = APIRouter(prefix="/api/files", tags=["files"])


class PreviewRequest(BaseModel):
    path: str
    source_type: str = "csv"
    delimiter: str = ","
    encoding: str = "utf-8"
    sheet_name: str | int = 0
    skip_rows: int = 0
    limit: int = 50


class BrowseRequest(BaseModel):
    path: str = "."


@router.post("/preview")
async def preview_file(req: PreviewRequest):
    file_path = Path(req.path)
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {req.path}")

    try:
        if req.source_type == "csv":
            df = pd.read_csv(file_path, delimiter=req.delimiter, encoding=req.encoding, skiprows=req.skip_rows)
        elif req.source_type == "excel":
            df = pd.read_excel(file_path, sheet_name=req.sheet_name, skiprows=req.skip_rows)
        elif req.source_type == "text":
            df = pd.read_csv(file_path, delimiter=req.delimiter, encoding=req.encoding, skiprows=req.skip_rows)
        else:
            raise HTTPException(400, f"Unknown source type: {req.source_type}")
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")

    preview = df.head(req.limit)
    for col in preview.select_dtypes(include=["datetime64"]).columns:
        preview[col] = preview[col].astype(str)

    return {
        "columns": list(df.columns),
        "dtypes": {col: str(df[col].dtype) for col in df.columns},
        "rows": preview.fillna("").to_dict(orient="records"),
        "total_rows_read": len(df),
        "preview_limit": req.limit,
    }


@router.post("/browse")
async def browse_directory(req: BrowseRequest):
    target = Path(req.path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(404, f"Path not found: {req.path}")

    entries = []
    try:
        for item in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            entries.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "suffix": item.suffix.lower(),
                "size": item.stat().st_size if item.is_file() else None,
            })
    except PermissionError:
        raise HTTPException(403, "Permission denied")

    return {
        "current": str(target),
        "parent": str(target.parent),
        "entries": entries,
    }


@router.get("/check")
async def check_file(path: str):
    p = Path(path)
    return {"path": path, "exists": p.exists(), "is_file": p.is_file()}


@router.get("/sheets")
async def list_sheets(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, "File not found")
    try:
        xl = pd.ExcelFile(p)
        return {"sheets": xl.sheet_names}
    except Exception as e:
        raise HTTPException(400, str(e))
