"""Scaffold guard instance scripts from built-in templates."""

from __future__ import annotations

import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .types import GuardType


class BaseScaffolder(ABC):
    def __init__(self, guard_id: str, name: str, guard_type: str, project_root: Path):
        self.guard_id = guard_id
        self.name = name
        self.guard_type = guard_type
        self.project_root = project_root
        self.templates_dir = project_root / ".specify" / "guards" / "types" / guard_type / "templates"

    @abstractmethod
    def scaffold(self) -> dict[str, Any]:
        raise NotImplementedError

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
        return env.get_template(template_name).render(**context)

    def create_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class GuardScaffolder:
    def __init__(self, guard_id: str, guard_type: GuardType, name: str, project_root: Path):
        self.guard_id = guard_id
        self.guard_type = guard_type
        self.name = name
        self.project_root = project_root
        self.env = Environment(
            loader=FileSystemLoader(str(guard_type.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def scaffold(self) -> dict[str, Any]:
        if self.guard_type.scaffolder_path and self.guard_type.scaffolder_path.exists():
            return self._run_custom_scaffolder(self.guard_type.scaffolder_path)
        return self._default_scaffold()

    def _run_custom_scaffolder(self, scaffolder_path: Path) -> dict[str, Any]:
        spec = importlib.util.spec_from_file_location("guard_custom_scaffolder", scaffolder_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load scaffolder from {scaffolder_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        scaffolder_class = next(
            (
                getattr(module, name)
                for name in dir(module)
                if isinstance(getattr(module, name), type)
                and name.endswith("Scaffolder")
                and name != "BaseScaffolder"
            ),
            None,
        )
        if scaffolder_class is None:
            raise RuntimeError(f"No scaffolder class found in {scaffolder_path}")
        scaffolder = scaffolder_class(
            guard_id=self.guard_id,
            name=self.name,
            guard_type=self.guard_type.id,
            project_root=self.project_root,
        )
        result = scaffolder.scaffold()
        if "files_created" in result and "files" not in result:
            result["files"] = result.pop("files_created")
        return result

    def _default_scaffold(self) -> dict[str, Any]:
        template = self.env.get_template("guard.py.j2")
        guard_dir = self.project_root / ".specify" / "guards" / self.guard_id
        guard_dir.mkdir(parents=True, exist_ok=True)
        guard_file = guard_dir / f"{self.guard_id}.py"
        content = template.render(
            guard_id=self.guard_id,
            name=self.name,
            guard_type=self.guard_type.id,
            description=self.guard_type.description,
            default_params_repr=repr(self.guard_type.default_params),
        )
        guard_file.write_text(content, encoding="utf-8")
        return {
            "files": [str(guard_file)],
            "command": f"python {guard_file} '{{params_json}}'",
        }
