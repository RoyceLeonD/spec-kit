"""Data models for the guard CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Category:
    name: str
    description: str = ""


@dataclass(frozen=True)
class GuardKind:
    name: str
    description: str = ""


@dataclass(frozen=True)
class GuardType:
    id: str
    category: Category
    type: GuardKind
    templates_dir: Path
    scaffolder_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def description(self) -> str:
        return str(self.metadata.get("description", ""))

    @property
    def default_params(self) -> dict[str, Any]:
        raw = self.metadata.get("default_params", {})
        return dict(raw) if isinstance(raw, dict) else {}


class CommentCategory(str, Enum):
    ROOT_CAUSE = "root-cause"
    FIX_APPLIED = "fix-applied"
    INVESTIGATION = "investigation"
    WORKAROUND = "workaround"
    FALSE_POSITIVE = "false-positive"


@dataclass(frozen=True)
class CommentNote:
    done: str
    expected: str
    todo: str


@dataclass(frozen=True)
class Comment:
    timestamp: datetime
    category: CommentCategory
    note: CommentNote


@dataclass
class GuardRun:
    run_id: str
    guard_id: str
    timestamp: datetime
    passed: bool
    exit_code: int
    duration_ms: int
    stdout: str
    stderr: str = ""
    analysis: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    comments: list[Comment] = field(default_factory=list)
