"""Execute guard instances and persist run history."""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .types import Comment, GuardRun
from .utils import generate_run_id, load_json, save_json


class GuardExecutor:
    def __init__(self, guard_id: str, command: str | None = None, timeout: int = 300, registry=None):
        self.guard_id = guard_id
        self.timeout = timeout
        self.registry = registry
        self.guard_data = registry.get_guard(guard_id) if registry else None
        self.command = command or (self.guard_data or {}).get("command")

    def execute(self) -> GuardRun:
        if not self.command:
            raise ValueError(f"No command configured for guard {self.guard_id}")
        start = time.time()
        project_root = self.registry.base_path.parent.parent if self.registry else None
        command = self._build_command()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=project_root,
            )
            duration_ms = int((time.time() - start) * 1000)
            payload = self._parse_payload(proc.stdout)
            passed = bool(payload.get("passed", proc.returncode == 0))
            result = GuardRun(
                run_id=self._next_run_id(),
                guard_id=self.guard_id,
                timestamp=datetime.now(timezone.utc),
                passed=passed,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                stdout=proc.stdout,
                stderr=proc.stderr,
                analysis=str(payload.get("analysis", proc.stderr.strip() or proc.stdout.strip() or "Guard completed")),
                details=payload.get("details", {}) if isinstance(payload.get("details", {}), dict) else {},
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.time() - start) * 1000)
            result = GuardRun(
                run_id=self._next_run_id(),
                guard_id=self.guard_id,
                timestamp=datetime.now(timezone.utc),
                passed=False,
                exit_code=124,
                duration_ms=duration_ms,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "Guard execution timed out",
                analysis="Guard execution timed out",
            )
        if self.registry:
            self._save_run(result)
        return result

    def _build_command(self) -> str:
        params_json = json.dumps((self.guard_data or {}).get("params", {}))
        command = self.command
        quoted = shlex.quote(params_json)
        command = command.replace("'{params_json}'", quoted)
        command = command.replace('{params_json}', quoted)
        return command

    def _parse_payload(self, stdout: str) -> dict[str, Any]:
        try:
            payload = json.loads(stdout.strip()) if stdout.strip() else {}
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _history_path(self):
        if not self.registry:
            raise ValueError("Registry is required for history operations")
        return self.registry.base_path / self.guard_id / "history.json"

    def _next_run_id(self) -> str:
        if not self.registry:
            return f"{self.guard_id}-R0001"
        history_path = self._history_path()
        existing = load_json(history_path) if history_path.exists() else []
        existing_ids = [item.get("run_id", "") for item in existing if isinstance(item, dict)]
        return generate_run_id(self.guard_id, existing_ids)

    def _save_run(self, run: GuardRun) -> None:
        history_path = self._history_path()
        history = load_json(history_path) if history_path.exists() else []
        history.append(_run_to_dict(run))
        save_json(history_path, history)


class GuardHistory:
    def __init__(self, guard_id: str, registry):
        self.guard_id = guard_id
        self.registry = registry
        self.history_path = registry.base_path / guard_id / "history.json"

    def get_lineage(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        history = load_json(self.history_path)
        history.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return history[:limit] if limit else history

    def add_comment(self, comment: Comment, run_id: str | None = None) -> None:
        history = self.get_lineage()
        if not history:
            raise ValueError(f"No runs found for {self.guard_id}")
        target = None
        if run_id:
            target = next((item for item in history if item.get("run_id") == run_id), None)
            if target is None:
                raise ValueError(f"Run {run_id} not found")
        else:
            target = history[0]
        target.setdefault("comments", []).append(_comment_to_dict(comment))
        history.sort(key=lambda item: item.get("timestamp", ""))
        save_json(self.history_path, history)


def _comment_to_dict(comment: Comment) -> dict[str, Any]:
    return {
        "timestamp": comment.timestamp.isoformat(),
        "category": comment.category.value,
        "note": asdict(comment.note),
    }


def _run_to_dict(run: GuardRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "guard_id": run.guard_id,
        "timestamp": run.timestamp.isoformat(),
        "passed": run.passed,
        "exit_code": run.exit_code,
        "duration_ms": run.duration_ms,
        "stdout": run.stdout,
        "stderr": run.stderr,
        "analysis": run.analysis,
        "details": run.details,
        "comments": [_comment_to_dict(comment) for comment in run.comments],
    }
