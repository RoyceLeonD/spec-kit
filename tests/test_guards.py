from pathlib import Path
from unittest.mock import patch
import sys

import yaml
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


runner = CliRunner()


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".git").mkdir()
    (project / ".specify").mkdir()
    return project


def test_registry_loads_builtin_guard_types():
    from specify_cli.guards.registry import GuardRegistry

    registry = GuardRegistry(Path("/tmp/nonexistent-guards-test"))
    guard_types = {guard_type.id for guard_type in registry.get_guard_types()}

    assert "unit-pytest" in guard_types
    assert "static-analysis-python" in guard_types
    assert "api-requests" in guard_types
    assert "ui-playwright" in guard_types


def test_guard_types_command_lists_builtin_types(tmp_path: Path):
    from specify_cli import app

    project = _make_project(tmp_path)

    with patch.object(Path, "cwd", return_value=project):
        result = runner.invoke(app, ["guard", "types"])

    assert result.exit_code == 0, result.output
    assert "unit-pytest" in result.output
    assert "static-analysis-python" in result.output


def test_guard_create_scaffolds_instance_files(tmp_path: Path):
    from specify_cli import app

    project = _make_project(tmp_path)

    with patch.object(Path, "cwd", return_value=project):
        result = runner.invoke(
            app,
            ["guard", "create", "--type", "unit-pytest", "--name", "sample-unit"],
        )

    assert result.exit_code == 0, result.output

    guard_dir = project / ".specify" / "guards" / "G001"
    guard_yaml = guard_dir / "guard.yaml"
    history_json = guard_dir / "history.json"
    guard_script = guard_dir / "G001.py"

    assert guard_yaml.exists()
    assert history_json.exists()
    assert guard_script.exists()

    data = yaml.safe_load(guard_yaml.read_text())
    assert data["id"] == "G001"
    assert data["guard_type"] == "unit-pytest"
    assert data["name"] == "sample-unit"
    assert data["command"].endswith("G001.py '{params_json}'")


def test_guard_run_and_comment_round_trip(tmp_path: Path):
    from specify_cli import app

    project = _make_project(tmp_path)
    tests_dir = project / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_sample.py").write_text(
        "def test_truth():\n"
        "    assert True\n"
    )

    with patch.object(Path, "cwd", return_value=project):
        create_result = runner.invoke(
            app,
            ["guard", "create", "--type", "unit-pytest", "--name", "sample-unit"],
        )
    assert create_result.exit_code == 0, create_result.output

    guard_yaml = project / ".specify" / "guards" / "G001" / "guard.yaml"
    guard_data = yaml.safe_load(guard_yaml.read_text())
    guard_data["params"] = {"test_paths": ["tests/unit/test_sample.py"]}
    guard_yaml.write_text(yaml.safe_dump(guard_data, sort_keys=False))

    with patch.object(Path, "cwd", return_value=project):
        run_result = runner.invoke(app, ["guard", "run", "G001"])
    assert run_result.exit_code == 0, run_result.output
    assert "PASSED" in run_result.output

    with patch.object(Path, "cwd", return_value=project):
        comment_result = runner.invoke(
            app,
            [
                "guard",
                "comment",
                "G001",
                "--category",
                "fix-applied",
                "--done",
                "created a passing test",
                "--expected",
                "guard stays green",
                "--todo",
                "keep coverage healthy",
            ],
        )
    assert comment_result.exit_code == 0, comment_result.output

    with patch.object(Path, "cwd", return_value=project):
        history_result = runner.invoke(app, ["guard", "history", "G001"])
    assert history_result.exit_code == 0, history_result.output
    assert "created a passing test" in history_result.output
