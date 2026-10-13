from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileInfo:
    path: str
    size: int
    modified: float
    extension: str


@dataclass(frozen=True)
class Pattern:
    kind: str
    title: str
    detail: str
    files: tuple[str, ...] = ()


@dataclass(frozen=True)
class MoveAction:
    source: str
    destination: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    root: str
    files: list[FileInfo] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.files)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
