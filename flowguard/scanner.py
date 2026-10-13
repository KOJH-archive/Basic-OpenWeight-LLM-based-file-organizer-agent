from __future__ import annotations

import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from .models import FileInfo, Pattern, ScanResult

SKIP_DIRS = {".git", ".flowguard", "node_modules", "__pycache__"}


def scan_folder(root: str | Path, *, max_files: int = 5000) -> ScanResult:
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise ValueError("선택한 경로가 폴더가 아닙니다.")
    files: list[FileInfo] = []
    for current, dirs, names in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not Path(current, d).is_symlink()]
        for name in names:
            path = Path(current, name)
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append(FileInfo(str(path), stat.st_size, stat.st_mtime, path.suffix.lower() or "(확장자 없음)"))
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            break
    return ScanResult(str(base), files, identify_patterns(files))


def identify_patterns(files: list[FileInfo]) -> list[Pattern]:
    patterns: list[Pattern] = []
    extensions = Counter(f.extension for f in files)
    common = [(ext, count) for ext, count in extensions.most_common(5) if count >= 3]
    if common:
        detail = ", ".join(f"{ext}: {count}개" for ext, count in common)
        patterns.append(Pattern("extensions", "반복되는 파일 형식", detail))

    names: dict[str, list[str]] = defaultdict(list)
    for item in files:
        names[Path(item.path).name.lower()].append(item.path)
    duplicate_names = [tuple(paths) for paths in names.values() if len(paths) > 1]
    if duplicate_names:
        flat = tuple(path for group in duplicate_names for path in group)
        patterns.append(Pattern("duplicate_names", "같은 이름의 파일", f"{len(duplicate_names)}개 이름이 여러 위치에 있습니다.", flat))

    cutoff = time.time() - 180 * 86400
    stale = tuple(f.path for f in files if f.modified < cutoff)
    if stale:
        patterns.append(Pattern("stale", "오래된 파일", f"180일 이상 수정되지 않은 파일 {len(stale)}개", stale[:100]))
    return patterns
