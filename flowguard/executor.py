from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import MoveAction, is_within


class SafetyError(RuntimeError):
    pass


def validate_actions(root: str | Path, actions: list[MoveAction]) -> None:
    base = Path(root).resolve()
    for action in actions:
        src, dst = Path(action.source).resolve(), Path(action.destination).resolve()
        if not is_within(src, base) or not is_within(dst, base):
            raise SafetyError("선택 폴더 밖의 경로가 계획에 포함되었습니다.")
        if src == dst:
            raise SafetyError("원본과 대상 경로가 같습니다.")


def execute_plan(root: str | Path, actions: list[MoveAction], *, dry_run: bool = True) -> dict:
    base = Path(root).resolve()
    validate_actions(base, actions)
    operations = []
    for action in actions:
        src, dst = Path(action.source), Path(action.destination)
        status = "would_move" if dry_run else "moved"
        actual_dst = dst
        if not dry_run:
            if not src.is_file():
                operations.append({**action.to_dict(), "status": "skipped_missing"})
                continue
            actual_dst = _available_destination(dst)
            actual_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(actual_dst))
        operations.append({**action.to_dict(), "destination": str(actual_dst), "status": status})

    record = {
        "id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(base), "dry_run": dry_run, "operations": operations,
    }
    if not dry_run:
        journal = base / ".flowguard" / "journal"
        journal.mkdir(parents=True, exist_ok=True)
        (journal / f"{record['id']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def rollback(journal_path: str | Path) -> dict:
    path = Path(journal_path)
    record = json.loads(path.read_text(encoding="utf-8"))
    base = Path(record["root"]).resolve()
    restored, skipped = [], []
    for operation in reversed(record["operations"]):
        if operation["status"] != "moved":
            continue
        original, current = Path(operation["source"]).resolve(), Path(operation["destination"]).resolve()
        if not is_within(original, base) or not is_within(current, base):
            raise SafetyError("저널에 선택 폴더 밖의 경로가 있습니다.")
        if current.is_file() and not original.exists():
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(current), str(original))
            restored.append(str(original))
        else:
            skipped.append(str(current))
    return {"restored": restored, "skipped": skipped}


def latest_journal(root: str | Path) -> Path | None:
    journal = Path(root) / ".flowguard" / "journal"
    candidates = list(journal.glob("*.json")) if journal.is_dir() else []
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _available_destination(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 10000):
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise SafetyError("대상 파일 이름을 안전하게 만들 수 없습니다.")
