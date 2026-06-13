import os
import platform
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from app.cli.client import AgentsClient

app = typer.Typer(
    name="agents",
    help="Enterprise AI Agents CLI — generate production-ready projects from your terminal.",
    no_args_is_help=True,
)
console = Console()


def _get_platform_agent():
    if platform.system() == "Windows":
        from app.cli.platforms.windows import WindowsPlatformAgent
        return WindowsPlatformAgent()
    from app.cli.platforms.linux import LinuxPlatformAgent
    return LinuxPlatformAgent()


def _collect_artifacts(result: dict) -> list[dict]:
    artifacts = result.get("artifacts", [])
    if not artifacts:
        artifacts = (
            result.get("backend_artifacts", []) +
            result.get("frontend_artifacts", [])
        )
    return artifacts


@app.command()
def generate(
    description: str = typer.Argument(..., help="Describe the project you want to generate"),
    name: str = typer.Option(..., "--name", "-n", help="Project name"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory (default: current directory)"),
    language: str = typer.Option("go", "--language", "-l", help="Backend language (go, python)"),
    framework: str = typer.Option("fiber", "--framework", "-f", help="Framework (fiber, gin, echo, fastapi)"),
    scope: str = typer.Option("backend", "--scope", "-s", help="Scope: backend, frontend, fullstack"),
    api_url: Optional[str] = typer.Option(None, "--api-url", hidden=True, help="Override API URL"),
):
    """Generate a production-ready project from a natural language description."""
    client = AgentsClient(base_url=api_url) if api_url else AgentsClient()
    agent = _get_platform_agent()

    output_path = agent.resolve_output_path(output or os.getcwd(), name)

    console.print(f"\n[bold cyan]Agents CLI[/bold cyan] — generating [bold]{name}[/bold]")
    console.print(f"[dim]Output: {output_path}[/dim]\n")

    # health check
    try:
        client.health()
    except Exception:
        console.print("[bold red]✗[/bold red] Could not reach the Agents API. Check your connection.")
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Generating project...", total=None)

        try:
            result = client.generate(
                objective=description,
                project_name=name,
                language=language,
                framework=framework,
                scope=scope,
            )
        except Exception as e:
            progress.stop()
            console.print(f"[bold red]✗[/bold red] Generation failed: {e}")
            raise typer.Exit(1)

        progress.update(task, description="Writing files...")
        artifacts = _collect_artifacts(result)

        if artifacts:
            written = agent.write_artifacts(artifacts, output_path)
        else:
            written = result.get("files", [])

        progress.stop()

    console.print(f"[bold green]✓[/bold green] Project created at [bold]{output_path}[/bold]")
    console.print(f"[dim]{len(written)} files written[/dim]\n")

    if result.get("errors"):
        console.print("[yellow]Warnings:[/yellow]")
        for err in result["errors"]:
            console.print(f"  [dim]• {err}[/dim]")


@app.command("list-skills")
def list_skills(
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Filter by agent name"),
    api_url: Optional[str] = typer.Option(None, "--api-url", hidden=True),
):
    """List all available skills."""
    client = AgentsClient(base_url=api_url) if api_url else AgentsClient()

    try:
        skills = client.list_skills(agent=agent)
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] {e}")
        raise typer.Exit(1)

    table = Table(title="Available Skills", show_lines=False)
    table.add_column("Skill", style="cyan")
    table.add_column("Category", style="dim")
    table.add_column("Description")

    for s in skills:
        table.add_row(s.get("name", ""), s.get("category", ""), s.get("description", ""))

    console.print(table)


@app.command()
def improve(
    instruction: str = typer.Argument(..., help="What to implement or improve in the project"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Path to the existing project (default: current directory)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory for generated files (default: project path)"),
    api_url: Optional[str] = typer.Option(None, "--api-url", hidden=True),
):
    """Apply improvements or add new features to an existing project."""
    from app.cli.project_scanner import scan_project

    client = AgentsClient(base_url=api_url) if api_url else AgentsClient()
    agent = _get_platform_agent()

    project_path = Path(path or os.getcwd()).resolve()
    output_path = Path(output).resolve() if output else project_path

    if not project_path.is_dir():
        console.print(f"[bold red]✗[/bold red] Path not found: {project_path}")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Agents CLI[/bold cyan] — improving [bold]{project_path.name}[/bold]")
    console.print(f"[dim]Instruction: {instruction}[/dim]\n")

    try:
        client.health()
    except Exception:
        console.print("[bold red]✗[/bold red] Could not reach the Agents API. Check your connection.")
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Scanning project structure...", total=None)

        project_context = scan_project(str(project_path))
        progress.update(
            task,
            description=f"Scanned {project_context['file_count']} files ({project_context['project_type']}) — sending to agents...",
        )

        try:
            result = client.improve(instruction=instruction, project_context=project_context)
        except Exception as e:
            progress.stop()
            console.print(f"[bold red]✗[/bold red] Improve failed: {e}")
            raise typer.Exit(1)

        progress.update(task, description="Writing files...")
        artifacts = _collect_artifacts(result)

        if artifacts:
            written = agent.write_artifacts(artifacts, output_path)
        else:
            written = result.get("files", [])

        progress.stop()

    console.print(f"[bold green]✓[/bold green] Changes written to [bold]{output_path}[/bold]")
    console.print(f"[dim]{len(written)} files written[/dim]\n")

    if result.get("errors"):
        console.print("[yellow]Warnings:[/yellow]")
        for err in result["errors"]:
            console.print(f"  [dim]• {err}[/dim]")


@app.command()
def version():
    """Show CLI version and API status."""
    client = AgentsClient()
    console.print("[bold cyan]Agents CLI[/bold cyan] v0.1.0")
    console.print(f"Platform: [dim]{platform.system()} {platform.machine()}[/dim]")

    try:
        health = client.health()
        console.print(f"API: [bold green]online[/bold green] — {health.get('skills_registered', 0)} skills registered")
    except Exception:
        console.print("API: [bold red]unreachable[/bold red]")


def cli():
    app()


if __name__ == "__main__":
    cli()
