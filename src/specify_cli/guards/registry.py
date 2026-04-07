"""Registry for guard types and guard instances."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import Category, GuardKind, GuardType
from .utils import generate_guard_id, load_yaml, save_json, save_yaml


class GuardRegistry:
    def __init__(self, guards_base_path: Path):
        self.base_path = guards_base_path.resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.base_path / "manifest.yaml"
        self._guard_types_cache: dict[str, GuardType] | None = None
        self.builtin_types_path = Path(__file__).resolve().parent / "builtin_types"
        self.custom_types_path = self.base_path / "types-custom"

    def get_guard_types(self) -> list[GuardType]:
        if self._guard_types_cache is None:
            self._load_guard_types()
        assert self._guard_types_cache is not None
        return list(self._guard_types_cache.values())

    def get_guard_type(self, type_id: str) -> GuardType | None:
        if self._guard_types_cache is None:
            self._load_guard_types()
        assert self._guard_types_cache is not None
        return self._guard_types_cache.get(type_id)

    def _iter_type_dirs(self):
        for root in (self.builtin_types_path, self.custom_types_path):
            if not root.exists():
                continue
            for entry in sorted(root.iterdir()):
                if entry.is_dir() and (entry / "guard-type.yaml").exists():
                    yield entry

    def _load_guard_types(self) -> None:
        self._guard_types_cache = {}
        for type_dir in self._iter_type_dirs():
            metadata = load_yaml(type_dir / "guard-type.yaml")
            category = Category(
                name=str(metadata.get("category", type_dir.name)),
                description=str(metadata.get("category_description", metadata.get("description", ""))),
            )
            kind = GuardKind(
                name=str(metadata.get("type", type_dir.name)),
                description=str(metadata.get("type_description", metadata.get("description", ""))),
            )
            guard_type = GuardType(
                id=type_dir.name,
                category=category,
                type=kind,
                templates_dir=type_dir / "templates",
                scaffolder_path=(type_dir / "scaffolder.py") if (type_dir / "scaffolder.py").exists() else None,
                metadata=metadata,
            )
            self._guard_types_cache[guard_type.id] = guard_type

    def generate_id(self) -> str:
        existing_ids = [guard["id"] for guard in self.list_guards()]
        return generate_guard_id(existing_ids)

    def add_guard(
        self,
        guard_id: str,
        guard_type: str,
        name: str,
        command: str,
        files: list[str],
        tags: list[str] | None = None,
        tasks: list[str] | None = None,
    ) -> None:
        guard_dir = self.base_path / guard_id
        guard_dir.mkdir(parents=True, exist_ok=True)

        guard_type_obj = self.get_guard_type(guard_type)
        data = {
            "id": guard_id,
            "guard_type": guard_type,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
            "command": command,
            "params": guard_type_obj.default_params if guard_type_obj else {},
            "tags": tags or [],
            "tasks": tasks or [],
        }
        save_yaml(guard_dir / "guard.yaml", data)
        save_json(guard_dir / "history.json", [])
        self._update_manifest(guard_id, guard_type, name, tags or [], tasks or [])

    def get_guard(self, guard_id: str) -> dict[str, Any] | None:
        path = self.base_path / guard_id / "guard.yaml"
        return load_yaml(path) if path.exists() else None

    def list_guards(self) -> list[dict[str, Any]]:
        guards: list[dict[str, Any]] = []
        for guard_dir in sorted(self.base_path.iterdir()):
            if not guard_dir.is_dir() or not guard_dir.name.startswith("G"):
                continue
            guard = self.get_guard(guard_dir.name)
            if guard:
                guards.append(guard)
        return guards

    def _update_manifest(
        self,
        guard_id: str,
        guard_type: str,
        name: str,
        tags: list[str],
        tasks: list[str],
    ) -> None:
        manifest = load_yaml(self.manifest_path) if self.manifest_path.exists() else {"guards": {}, "tasks": {}, "tags": {}}
        manifest.setdefault("guards", {})
        manifest.setdefault("tasks", {})
        manifest.setdefault("tags", {})
        manifest["guards"][guard_id] = {
            "type": guard_type,
            "name": name,
            "created": datetime.now(timezone.utc).isoformat(),
            "tags": tags,
            "tasks": tasks,
        }
        for tag in tags:
            manifest["tags"].setdefault(tag, [])
            if guard_id not in manifest["tags"][tag]:
                manifest["tags"][tag].append(guard_id)
        for task in tasks:
            manifest["tasks"].setdefault(task, {"guards": []})
            if guard_id not in manifest["tasks"][task]["guards"]:
                manifest["tasks"][task]["guards"].append(guard_id)
        save_yaml(self.manifest_path, manifest)
