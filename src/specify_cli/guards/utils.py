"""Utility helpers for the guard CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def generate_guard_id(existing_ids: list[str]) -> str:
    numbers = []
    for candidate in existing_ids:
        if candidate.startswith("G") and candidate[1:].isdigit():
            numbers.append(int(candidate[1:]))
    return f"G{(max(numbers) + 1) if numbers else 1:03d}"


def generate_run_id(guard_id: str, existing_run_ids: list[str]) -> str:
    prefix = f"{guard_id}-R"
    numbers = []
    for candidate in existing_run_ids:
        if candidate.startswith(prefix) and candidate[len(prefix):].isdigit():
            numbers.append(int(candidate[len(prefix):]))
    return f"{guard_id}-R{(max(numbers) + 1) if numbers else 1:04d}"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
