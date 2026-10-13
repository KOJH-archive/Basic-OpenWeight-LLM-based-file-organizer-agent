from __future__ import annotations

from collections import Counter
from pathlib import Path

from .models import MoveAction, ScanResult, is_within

CATEGORY_BY_EXTENSION = {
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents", ".txt": "Documents",
    ".xlsx": "Spreadsheets", ".xls": "Spreadsheets", ".csv": "Spreadsheets",
    ".png": "Images", ".jpg": "Images", ".jpeg": "Images", ".gif": "Images", ".webp": "Images",
    ".zip": "Archives", ".7z": "Archives", ".rar": "Archives",
}


def build_organization_plan(result: ScanResult, *, minimum_group: int = 3) -> list[MoveAction]:
    root = Path(result.root).resolve()
    top_level = [f for f in result.files if Path(f.path).parent.resolve() == root]
    counts = Counter(f.extension for f in top_level)
    actions: list[MoveAction] = []
    for item in top_level:
        category = CATEGORY_BY_EXTENSION.get(item.extension)
        if not category or counts[item.extension] < minimum_group:
            continue
        source = Path(item.path).resolve()
        destination = (root / "FlowGuard Organized" / category / source.name).resolve()
        if is_within(source, root) and is_within(destination, root) and source != destination:
            actions.append(MoveAction(str(source), str(destination), f"{item.extension} 파일 {counts[item.extension]}개를 {category}로 정리"))
    return actions
