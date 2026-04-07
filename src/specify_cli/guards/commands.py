"""Typer commands for the guard CLI."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .executor import GuardExecutor, GuardHistory
from .registry import GuardRegistry
from .scaffolder import GuardScaffolder
from .types import Comment, CommentCategory, CommentNote

console = Console()
guard_app = typer.Typer(name="guard", help="Manage validation guards")


def get_project_root() -> Path:
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / ".git").exists() or (current / ".specify").exists():
            return current
        current = current.parent
    return Path.cwd().resolve()


def get_registry() -> GuardRegistry:
    project_root = get_project_root()
    return GuardRegistry(project_root / ".specify" / "guards")


@guard_app.command("types")
def cmd_types(verbose: bool = typer.Option(False, "--verbose", "-v", help="Show descriptions")) -> None:
    registry = get_registry()
    guard_types = sorted(registry.get_guard_types(), key=lambda item: item.id)
    if not guard_types:
        console.print("[yellow]No guard types available.[/yellow]")
        return

    table = Table(title="Available Guard Types")
    table.add_column("Guard Type", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Type", style="magenta")
    if verbose:
        table.add_column("Description")
    for guard_type in guard_types:
        row = [guard_type.id, guard_type.category.name, guard_type.type.name]
        if verbose:
            row.append(guard_type.description)
        table.add_row(*row)
    console.print(table)


@guard_app.command("create")
def cmd_create(
    guard_type_id: str = typer.Option(..., "--type", help="Guard type ID"),
    name: str = typer.Option(..., "--name", help="Guard instance name"),
    tasks: Optional[str] = typer.Option(None, "--task", help="Comma-separated task IDs"),
    tags: Optional[str] = typer.Option(None, "--tag", help="Comma-separated tags"),
) -> None:
    registry = get_registry()
    guard_type = registry.get_guard_type(guard_type_id)
    if guard_type is None:
        console.print(f"[red]Unknown guard type:[/red] {guard_type_id}")
        raise typer.Exit(1)
    guard_id = registry.generate_id()
    scaffolder = GuardScaffolder(guard_id=guard_id, guard_type=guard_type, name=name, project_root=get_project_root())
    result = scaffolder.scaffold()
    registry.add_guard(
        guard_id=guard_id,
        guard_type=guard_type_id,
        name=name,
        command=result["command"],
        files=result["files"],
        tasks=[item.strip() for item in tasks.split(",")] if tasks else [],
        tags=[item.strip() for item in tags.split(",")] if tags else [],
    )
    console.print(f"[green]Created[/green] {guard_id} ({guard_type_id})")
    for file_path in result["files"]:
        console.print(f"  - {file_path}")


@guard_app.command("list")
def cmd_list() -> None:
    registry = get_registry()
    guards = registry.list_guards()
    if not guards:
        console.print("[yellow]No guards created yet.[/yellow]")
        return
    table = Table(title="Created Guards")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Name")
    table.add_column("Last Result")
    for guard in guards:
        history = GuardHistory(guard["id"], registry).get_lineage(limit=1)
        if history:
            status = "PASS" if history[0].get("passed") else "FAIL"
        else:
            status = "never"
        table.add_row(guard["id"], guard["guard_type"], guard["name"], status)
    console.print(table)


@guard_app.command("run")
def cmd_run(guard_id: str = typer.Argument(..., help="Guard ID"), verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    registry = get_registry()
    guard = registry.get_guard(guard_id)
    if guard is None:
        console.print(f"[red]Guard not found:[/red] {guard_id}")
        raise typer.Exit(1)
    result = GuardExecutor(guard_id=guard_id, registry=registry).execute()
    status = "PASSED" if result.passed else "FAILED"
    color = "green" if result.passed else "red"
    console.print(f"[{color}]Guard {guard_id} {status}[/{color}]")
    console.print(result.analysis)
    if verbose and result.stdout:
        console.print(Panel(result.stdout, title="stdout"))
    if verbose and result.stderr:
        console.print(Panel(result.stderr, title="stderr", border_style="red"))
    if not result.passed:
        raise typer.Exit(1)


@guard_app.command("history")
def cmd_history(guard_id: str = typer.Argument(..., help="Guard ID"), limit: int = typer.Option(10, "--limit", "-n")) -> None:
    registry = get_registry()
    guard = registry.get_guard(guard_id)
    if guard is None:
        console.print(f"[red]Guard not found:[/red] {guard_id}")
        raise typer.Exit(1)
    runs = GuardHistory(guard_id, registry).get_lineage(limit=limit)
    if not runs:
        console.print(f"[yellow]No execution history for {guard_id}[/yellow]")
        return
    console.print(f"[bold cyan]History for {guard_id}[/bold cyan]")
    for run in runs:
        icon = "✓" if run.get("passed") else "✗"
        console.print(f"{icon} {run.get('timestamp')} — {run.get('analysis')}")
        for comment in run.get("comments", []):
            note = comment.get("note", {})
            console.print(f"  [{comment.get('category')}] done={note.get('done')} expected={note.get('expected')} todo={note.get('todo')}")


@guard_app.command("comment")
def cmd_comment(
    guard_id: str = typer.Argument(..., help="Guard ID"),
    category: str = typer.Option(..., "--category", "-c"),
    done: str = typer.Option(..., "--done"),
    expected: str = typer.Option(..., "--expected"),
    todo: str = typer.Option(..., "--todo"),
    run_id: Optional[str] = typer.Option(None, "--run"),
) -> None:
    registry = get_registry()
    if registry.get_guard(guard_id) is None:
        console.print(f"[red]Guard not found:[/red] {guard_id}")
        raise typer.Exit(1)
    try:
        category_enum = CommentCategory(category)
    except ValueError:
        console.print(f"[red]Invalid comment category:[/red] {category}")
        raise typer.Exit(1)
    comment = Comment(
        timestamp=datetime.now(),
        category=category_enum,
        note=CommentNote(done=done, expected=expected, todo=todo),
    )
    history = GuardHistory(guard_id, registry)
    try:
        history.add_comment(comment, run_id=run_id)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Added comment to {guard_id}[/green]")
