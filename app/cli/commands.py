import os
import platform
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from app.cli._version import CLI_VERSION
from app.cli.client import AgentsClient

app = typer.Typer(
    name="agents",
    help="Enterprise AI Agents CLI — generate production-ready projects from your terminal.",
    no_args_is_help=True,
)
console = Console()

_UPDATE_CHECK_FILE = Path.home() / ".agents-cli" / "update_check.json"
_UPDATE_CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # once a day, to avoid extra latency on every run


def _get_platform_agent():
    if platform.system() == "Windows":
        from app.cli.platforms.windows import WindowsPlatformAgent
        return WindowsPlatformAgent()
    from app.cli.platforms.linux import LinuxPlatformAgent
    return LinuxPlatformAgent()


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in v.strip().split("."))
    except Exception:
        return (0,)


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def _latest_known_version(api_url: Optional[str] = None) -> Optional[str]:
    """Best-effort, cached check for the latest published CLI version.

    Never raises — a failure here must never block a normal command. Cached
    for a day so it doesn't add a network round-trip to every invocation.
    """
    import json
    import time

    now = time.time()
    try:
        if _UPDATE_CHECK_FILE.exists():
            cached = json.loads(_UPDATE_CHECK_FILE.read_text())
            if now - cached.get("checked_at", 0) < _UPDATE_CHECK_INTERVAL_SECONDS:
                return cached.get("latest_version") or None
    except Exception:
        pass

    try:
        client = AgentsClient(base_url=api_url) if api_url else AgentsClient()
        latest = client.cli_version().get("version", "")
    except Exception:
        return None

    try:
        _UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        _UPDATE_CHECK_FILE.write_text(json.dumps({"checked_at": now, "latest_version": latest}))
    except Exception:
        pass

    return latest or None


@app.callback()
def _main(ctx: typer.Context):
    """Runs before every command — warns (cheaply, never blocking) if a newer CLI is out."""
    if ctx.invoked_subcommand in (None, "update"):
        return
    latest = _latest_known_version()
    if latest and _is_newer(latest, CLI_VERSION):
        console.print(
            f"[yellow]![/yellow] [dim]Nova versão do Agents CLI disponível: "
            f"{latest} (você está na {CLI_VERSION}). Rode [bold]agents update[/bold] para atualizar.[/dim]\n"
        )


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
def ask(
    query: str = typer.Argument(..., help="Describe in natural language what you want to do or what problem you have"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Path to the project (default: current directory)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Where to write generated files (default: project path)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts and apply everything automatically"),
    api_url: Optional[str] = typer.Option(None, "--api-url", hidden=True),
):
    """
    Ask the AI agent anything in natural language.

    Examples:
      agents ask "criar uma entidade Product no projeto Go"
      agents ask "minha aplicação não está iniciando"
      agents ask "adicionar autenticação NextAuth no meu projeto"
      agents ask "gerar suíte de testes para o módulo payment"
    """
    import json
    import subprocess
    from rich.panel import Panel
    from rich.prompt import Confirm
    from rich.text import Text
    from app.cli.project_scanner import scan_project
    from app.cli.intent_router import detect_user_language

    client = AgentsClient(base_url=api_url) if api_url else AgentsClient()
    plat_agent = _get_platform_agent()

    # Detect user language from the query for bilingual output
    _ul = detect_user_language(query)
    def _t(pt: str, en: str) -> str:
        return pt if _ul == "pt" else en

    project_path = Path(path or os.getcwd()).resolve()
    output_path = Path(output).resolve() if output else project_path

    if not project_path.is_dir():
        console.print(f"[bold red]✗[/bold red] Path not found: {project_path}")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Agents[/bold cyan] — [dim]{project_path.name}[/dim]\n")

    # Health check
    try:
        client.health()
    except Exception:
        console.print(f"[bold red]✗[/bold red] {_t('Não foi possível conectar à API. Verifique sua conexão.', 'Could not reach the Agents API. Check your connection.')}")
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task(_t("Analisando pedido...", "Analyzing request..."), total=None)
        project_context = scan_project(str(project_path))

        # Route intent via API
        try:
            intent = client.route_intent(query=query, project_context=project_context)
        except Exception as e:
            progress.stop()
            console.print(f"[bold red]✗[/bold red] Could not analyze request: {e}")
            raise typer.Exit(1)

        progress.stop()

    if intent.get("intent") == "unknown":
        console.print(f"[yellow]![/yellow] {_t('Não foi possível identificar sua solicitação.', 'Could not match your request to any available skill.')}")
        console.print(f"[dim]{_t('Seja mais específico. Ex: criar entidade User ou diagnosticar erro Go', 'Try being more specific. Example: create User entity or diagnose Go error')}[/dim]")
        raise typer.Exit(1)

    # ── Show plan ────────────────────────────────────────────────────────────

    is_diagnostic = intent.get("is_diagnostic", False)
    agent_name   = intent.get("agent", "")
    skill_name   = intent.get("skill", "")
    params       = intent.get("params", {})
    description  = intent.get("description", skill_name)
    suggestions  = intent.get("suggestions", [])

    plan_text = Text()
    plan_text.append(_t("Entendido: ", "Understood: "), style="bold")
    plan_text.append(f"{description}\n\n", style="white")
    plan_text.append(f"  {_t('Agente', 'Agent' )} : ", style="dim")
    plan_text.append(f"{agent_name}\n", style="cyan")
    plan_text.append(f"  {_t('Skill ', 'Skill' )} : ", style="dim")
    plan_text.append(f"{skill_name}\n", style="cyan")
    if params:
        plan_text.append(f"  {_t('Params', 'Params')} : ", style="dim")
        plan_text.append(f"{json.dumps(params, ensure_ascii=False)}\n", style="dim")
    if is_diagnostic:
        lang = intent.get("detected_language", "go")
        plan_text.append(f"\n  {_t('Ação  ', 'Action')} : ", style="dim")
        plan_text.append(
            _t(
                f"Rodar build, capturar erros e corrigir automaticamente ({lang})",
                f"Run build, capture errors and fix automatically ({lang})",
            ),
            style="yellow",
        )

    title = _t("Plano de Execução", "Execution Plan")
    console.print(Panel(plan_text, title=f"[bold]{title}[/bold]", border_style="cyan", padding=(0, 2)))

    # ── Confirm ──────────────────────────────────────────────────────────────

    proceed = yes or Confirm.ask(f"\n{_t('Executar?', 'Proceed?')}", default=False)
    if not proceed:
        console.print(f"[dim]{_t('Operação cancelada.', 'Operation cancelled.')}[/dim]")
        raise typer.Exit(0)

    console.print()

    # ── Execute ──────────────────────────────────────────────────────────────

    if is_diagnostic:
        lang = intent.get("detected_language", "go")

        # Verify commands: first run to capture errors; re-run after each fix to confirm
        verify_cmds: dict[str, list[str]] = {
            "go":     ["go", "build", "./..."],
            "nextjs": ["npx", "tsc", "--noEmit"],
            "python": ["python", "-m", "py_compile"],
        }
        # Docker-aware secondary verification when docker-compose.yml is present
        all_files = project_context.get("files", [])
        has_compose = any(
            f.get("path", "") in ("docker-compose.yml", "docker-compose.yaml")
            for f in all_files
        )
        verify_cmd = verify_cmds.get(lang, [])

        def _run_build(cmd: list[str]) -> tuple[bool, str]:
            """Run a build command; return (passed, output)."""
            if not cmd:
                return True, ""
            try:
                proc = subprocess.run(
                    cmd, cwd=str(project_path),
                    capture_output=True, text=True, timeout=120,
                )
                out = (proc.stderr + proc.stdout).strip()
                return proc.returncode == 0, out
            except Exception as exc:
                return False, str(exc)

        def _run_docker_build() -> tuple[bool, str]:
            try:
                proc = subprocess.run(
                    ["docker", "compose", "build"],
                    cwd=str(project_path),
                    capture_output=True, text=True, timeout=300,
                )
                out = (proc.stderr + proc.stdout).strip()
                return proc.returncode == 0, out
            except Exception as exc:
                return False, str(exc)

        def _collect_source_files(error_out: str) -> list[dict[str, str]]:
            priority_names = {"go.mod", "go.sum", "Dockerfile", "docker-compose.yml", "docker-compose.yaml"}
            priority = [f for f in all_files if f.get("path", "") in priority_names]
            # Always include cmd/*.go so the skill knows where main.go lives
            cmd_go = [
                f for f in all_files
                if f.get("path", "").startswith("cmd/") and f.get("path", "").endswith(".go")
                and f not in priority
            ]
            matched = [
                f for f in all_files
                if f.get("path", "") in error_out and f not in priority and f not in cmd_go
            ]
            combined = priority + cmd_go + matched
            return [
                {"path": f["path"], "content": f.get("content") or ""}
                for f in (combined or all_files[:20])
            ]

        module_name = ""
        for f in all_files:
            if f.get("path") == "go.mod":
                for line in (f.get("content") or "").splitlines():
                    if line.startswith("module "):
                        module_name = line.split()[1]
                        break

        # ── Initial error capture ─────────────────────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            cmd_str = " ".join(verify_cmd)
            p.add_task(_t(f"Rodando `{cmd_str}`...", f"Running `{cmd_str}`..."), total=None)
            passed, error_output = _run_build(verify_cmd)
            p.stop()

        # If local build passes, check docker build if available
        if passed and has_compose:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
                p.add_task(_t("Rodando docker compose build...", "Running docker compose build..."), total=None)
                passed, error_output = _run_docker_build()
                p.stop()

        # If everything passes, use user's description as the error source
        if passed:
            console.print(f"[dim]{_t('Build passou — analisando a descrição do erro...', 'Build passed — analyzing described error...')}[/dim]")
            error_output = query

        # ── Diagnostic + fix loop (max 3 iterations) ─────────────────────────
        MAX_RETRIES = 3
        result: dict[str, Any] = {}
        all_written: list[str] = []

        for attempt in range(1, MAX_RETRIES + 1):
            if not error_output:
                break

            if error_output != query:
                console.print(f"[yellow]{_t(f'Iteração {attempt} — {len(error_output.splitlines())} linha(s) de erro capturada(s)', f'Iteration {attempt} — {len(error_output.splitlines())} error line(s) captured')}[/yellow]")
            else:
                console.print(f"[yellow]{_t('Analisando erro descrito pelo usuário...', 'Analyzing described error...')}[/yellow]")

            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
                p.add_task(_t("Diagnóstico em andamento...", "Running diagnostic..."), total=None)
                try:
                    result = client.diagnose(
                        language=lang,
                        error_output=error_output,
                        source_files=_collect_source_files(error_output),
                        module_name=module_name,
                    )
                except Exception as e:
                    p.stop()
                    console.print(f"[bold red]✗[/bold red] {_t('Diagnóstico falhou', 'Diagnostic failed')}: {e}")
                    raise typer.Exit(1)
                p.stop()

            artifacts_this = result.get("artifacts", [])
            if artifacts_this:
                written = plat_agent.write_artifacts(artifacts_this, output_path)
                all_written.extend(written)
                console.print(f"[bold green]✓[/bold green] {result.get('summary', _t('Corrigido', 'Fixed'))}")
                for fw in written:
                    if not fw.endswith("diagnostic_report.md"):
                        console.print(f"  [green]•[/green] {fw}")

            # ── Re-run verification after fix ─────────────────────────────────
            if attempt < MAX_RETRIES:
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
                    p.add_task(_t("Verificando se o fix funcionou...", "Verifying fix..."), total=None)
                    # Re-scan so updated files are in context
                    project_context = scan_project(str(project_path))
                    all_files = project_context.get("files", [])
                    v_passed, v_out = _run_build(verify_cmd)
                    p.stop()

                # Also verify docker build if relevant
                if v_passed and has_compose:
                    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
                        p.add_task(_t("Verificando docker compose build...", "Verifying docker compose build..."), total=None)
                        v_passed, v_out = _run_docker_build()
                        p.stop()

                if v_passed:
                    console.print(f"\n[bold green]✓[/bold green] {_t('Verificação passou — projeto compila corretamente!', 'Verification passed — project builds successfully!')}")
                    error_output = ""
                    break
                else:
                    console.print(f"[yellow]{_t('Novo erro detectado — aplicando fix adicional...', 'New error detected — applying additional fix...')}[/yellow]")
                    error_output = v_out

        artifacts = result.get("artifacts", [])
    else:
        # Standard generative skill
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            t = p.add_task(_t("Gerando código...", "Generating code..."), total=None)
            try:
                result = client.execute_skill(agent=agent_name, skill=skill_name, params=params)
            except Exception as e:
                p.stop()
                console.print(f"[bold red]✗[/bold red] {_t('Execução falhou', 'Execution failed')}: {e}")
                raise typer.Exit(1)
            p.stop()

        artifacts = _collect_artifacts(result)
        all_written: list[str] = []

    # Write files (generative path — diagnostic path already wrote above)
    written: list[str] = []
    if artifacts and not is_diagnostic:
        written = plat_agent.write_artifacts(artifacts, output_path)
        all_written = written

    if is_diagnostic:
        total = len([w for w in all_written if not w.endswith("diagnostic_report.md")])
        if total:
            console.print(f"\n[dim]{_t(f'{total} arquivo(s) corrigido(s) em', f'{total} file(s) fixed in')} {output_path}[/dim]")
    elif result.get("success", True) and written:
        console.print(f"[bold green]✓[/bold green] {result.get('summary', _t('Concluído', 'Done'))}")
        console.print(f"[dim]{len(written)} {_t('arquivo(s) escritos em', 'file(s) written to')} {output_path}[/dim]\n")
        for f in written:
            console.print(f"  [green]•[/green] {f}")
    elif not written:
        console.print(f"[bold green]✓[/bold green] {result.get('summary', _t('Concluído', 'Done'))}")
    else:
        console.print(f"[bold red]✗[/bold red] {result.get('error', _t('Falha na execução', 'Execution failed'))}")

    # ── Follow-up suggestions ─────────────────────────────────────────────────

    if not suggestions:
        console.print()
        return

    console.print(f"\n[bold]{_t('Próximos passos sugeridos:', 'Suggested next steps:')}[/bold]")
    for i, s in enumerate(suggestions, 1):
        sug_type = s.get("type", "skill")
        if sug_type == "command":
            console.print(f"  [dim]{i}.[/dim] {s['description']}  [dim]→  {s.get('command', '')}[/dim]")
        else:
            console.print(f"  [dim]{i}.[/dim] {s['description']}")

    console.print()

    for suggestion in suggestions:
        sug_type   = suggestion.get("type", "skill")
        sug_desc   = suggestion.get("description", "")

        # ── Command suggestion: just run the shell command locally ───────────
        if sug_type == "command":
            sug_cmd = suggestion.get("command", "")
            if not sug_cmd:
                continue
            run = yes or Confirm.ask(f"{_t('Executar', 'Run')}: [cyan]{sug_cmd}[/cyan]?", default=False)
            if not run:
                continue
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
                t = p.add_task(f"Rodando `{sug_cmd}`...", total=None)
                try:
                    proc = subprocess.run(
                        sug_cmd, shell=True, cwd=str(project_path),
                        capture_output=True, text=True, timeout=120,
                    )
                    output_text = (proc.stdout + proc.stderr).strip()
                    p.stop()
                    if proc.returncode == 0:
                        console.print(f"  [green]✓[/green] {sug_desc}")
                        if output_text:
                            console.print(f"  [dim]{output_text[:200]}[/dim]")
                    else:
                        console.print(f"  [yellow]![/yellow] {sug_desc} — saiu com código {proc.returncode}")
                        if output_text:
                            console.print(f"  [dim]{output_text[:300]}[/dim]")
                except Exception as exc:
                    p.stop()
                    console.print(f"  [red]✗[/red] {sug_cmd}: {exc}")
            continue

        # ── Skill suggestion: call /skills/execute via API ───────────────────
        sug_agent  = suggestion.get("agent", "")
        sug_skill  = suggestion.get("skill", "")
        sug_params = dict(suggestion.get("params", {}))

        # Propagate known params from the primary execution
        for k, v in params.items():
            if k not in sug_params:
                sug_params[k] = v

        apply = yes or Confirm.ask(f"{_t('Aplicar', 'Apply')}: [cyan]{sug_desc}[/cyan]?", default=False)
        if not apply:
            continue

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            t = p.add_task(f"Executando {sug_skill}...", total=None)
            try:
                sug_result = client.execute_skill(agent=sug_agent, skill=sug_skill, params=sug_params)
            except Exception as e:
                p.stop()
                console.print(f"  [red]✗[/red] {sug_skill}: {e}")
                continue
            p.stop()

        sug_artifacts = _collect_artifacts(sug_result)
        if sug_artifacts:
            sug_written = plat_agent.write_artifacts(sug_artifacts, output_path)
            console.print(f"  [green]✓[/green] {sug_desc} — {len(sug_written)} arquivo(s)")
        else:
            console.print(f"  [green]✓[/green] {sug_desc}")

    console.print()


@app.command()
def diagnose(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Path to the project with errors (default: current directory)"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Language: go, nextjs, python (auto-detected if omitted)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Directory to write fixed files (default: project path)"),
    api_url: Optional[str] = typer.Option(None, "--api-url", hidden=True),
):
    """Diagnose and fix build/compile/runtime errors in Go, Next.js, or Python projects."""
    import json
    import subprocess
    from app.cli.project_scanner import scan_project

    client = AgentsClient(base_url=api_url) if api_url else AgentsClient()
    agent = _get_platform_agent()

    project_path = Path(path or os.getcwd()).resolve()
    output_path = Path(output).resolve() if output else project_path

    if not project_path.is_dir():
        console.print(f"[bold red]✗[/bold red] Path not found: {project_path}")
        raise typer.Exit(1)

    # Auto-detect language from project structure
    detected_lang = language
    if not detected_lang:
        if (project_path / "go.mod").exists():
            detected_lang = "go"
        elif (project_path / "package.json").exists() and (project_path / "next.config.js").exists() or (project_path / "next.config.ts").exists():
            detected_lang = "nextjs"
        elif list(project_path.glob("*.py")) or (project_path / "requirements.txt").exists():
            detected_lang = "python"

    if not detected_lang:
        console.print("[bold red]✗[/bold red] Could not detect project language. Use --language go|nextjs|python")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Agents CLI[/bold cyan] — diagnosing [bold]{project_path.name}[/bold] ([dim]{detected_lang}[/dim])")

    try:
        client.health()
    except Exception:
        console.print("[bold red]✗[/bold red] Could not reach the Agents API. Check your connection.")
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        # Step 1: Run build command to capture errors
        task = progress.add_task("Running build to capture errors...", total=None)
        error_output = ""

        build_commands = {
            "go":     ["go", "build", "./..."],
            "nextjs": ["npx", "tsc", "--noEmit"],
            "python": ["python", "-m", "py_compile"],
        }
        cmd = build_commands.get(detected_lang, [])

        if cmd:
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(project_path),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                error_output = (proc.stderr + proc.stdout).strip()
            except FileNotFoundError:
                error_output = f"Build tool not found: {cmd[0]}"
            except subprocess.TimeoutExpired:
                error_output = "Build command timed out after 60s"

        if not error_output:
            progress.stop()
            console.print("[bold green]✓[/bold green] No errors detected — build passed.")
            raise typer.Exit(0)

        progress.update(task, description="Scanning project files...")
        project_context = scan_project(str(project_path))

        # Step 2: Filter to files referenced in error output (or all if small project)
        all_files = project_context.get("files", [])
        error_files = [
            f for f in all_files
            if f.get("path", "") in error_output or error_output.count(f.get("path", "xx")) > 0
        ]
        # Fallback: send all source files (up to 20)
        source_files = error_files if error_files else all_files[:20]

        # Format for API: list of {path, content}
        api_files = [
            {"path": f["path"], "content": f.get("content") or ""}
            for f in source_files
            if f.get("path")
        ]

        module_name = ""
        if detected_lang == "go":
            gomod = project_path / "go.mod"
            if gomod.exists():
                for line in gomod.read_text().splitlines():
                    if line.startswith("module "):
                        module_name = line.split()[1]
                        break

        progress.update(task, description=f"Sending {len(api_files)} file(s) to diagnostic agent...")

        try:
            result = client.diagnose(
                language=detected_lang,
                error_output=error_output,
                source_files=api_files,
                module_name=module_name,
            )
        except Exception as e:
            progress.stop()
            console.print(f"[bold red]✗[/bold red] Diagnostic failed: {e}")
            raise typer.Exit(1)

        progress.update(task, description="Applying fixes...")
        artifacts = result.get("artifacts", [])

        if artifacts:
            written = agent.write_artifacts(artifacts, output_path)
        else:
            written = []

        progress.stop()

    if result.get("success"):
        console.print(f"[bold green]✓[/bold green] {result.get('summary', 'Diagnosis complete')}")
        if written:
            console.print(f"[dim]{len(written)} file(s) fixed and written to {output_path}[/dim]\n")
            for f in written:
                console.print(f"  [green]•[/green] {f}")
        else:
            console.print("[dim]Review the diagnostic_report.md for analysis and suggested fixes.[/dim]")
    else:
        console.print(f"[bold red]✗[/bold red] {result.get('error', 'Diagnostic could not determine fixes')}")

    if result.get("instructions"):
        console.print("\n[bold]Next steps:[/bold]")
        for step in result["instructions"]:
            console.print(f"  [dim]• {step}[/dim]")


@app.command()
def update(
    force: bool = typer.Option(False, "--force", "-f", help="Reinstall even if already on the latest version"),
    api_url: Optional[str] = typer.Option(None, "--api-url", hidden=True),
):
    """Download and install the latest Agents CLI binary, replacing the one currently running."""
    import shutil as _shutil
    import stat
    import subprocess
    import tempfile

    client = AgentsClient(base_url=api_url) if api_url else AgentsClient()

    console.print(f"\n[bold cyan]Agents CLI[/bold cyan] — current version [bold]{CLI_VERSION}[/bold]")

    try:
        latest = client.cli_version().get("version", "")
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Could not check the latest version: {e}")
        raise typer.Exit(1)

    if not latest:
        console.print("[bold red]✗[/bold red] Server did not return a version.")
        raise typer.Exit(1)

    if not force and not _is_newer(latest, CLI_VERSION):
        console.print(f"[bold green]✓[/bold green] Already up to date (v{CLI_VERSION}).")
        return

    is_windows = platform.system() == "Windows"
    target_os = "windows" if is_windows else "linux"

    raw_exe = sys.executable if getattr(sys, "frozen", False) else (_shutil.which("agents") or "")
    current_exe = Path(raw_exe) if raw_exe else None
    if not current_exe or not current_exe.exists() or "python" in current_exe.name.lower():
        console.print(
            "[yellow]![/yellow] `agents update` only works for the installed binary "
            "(not when running from source, e.g. via `python -m`).\n"
            f"[dim]Reinstall manually: curl -fsSL {client._base}/cli/install.sh | bash[/dim]"
        )
        raise typer.Exit(1)

    console.print(f"[dim]New version available: {latest}[/dim]")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task(f"Downloading v{latest}...", total=None)

        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(current_exe.parent), prefix=".agents-update-")
        os.close(tmp_fd)
        tmp_path = Path(tmp_name)

        try:
            client.download_cli_binary(tmp_path, target_os=target_os)
        except Exception as e:
            progress.stop()
            tmp_path.unlink(missing_ok=True)
            console.print(f"[bold red]✗[/bold red] Download failed: {e}")
            raise typer.Exit(1)

        progress.update(task, description="Installing...")

        if not is_windows:
            tmp_path.chmod(tmp_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            try:
                os.replace(tmp_path, current_exe)
            except PermissionError:
                progress.stop()
                console.print(f"[yellow]![/yellow] Permission denied writing to {current_exe} — retrying with sudo...")
                rc = subprocess.run(["sudo", "mv", str(tmp_path), str(current_exe)]).returncode
                if rc != 0:
                    console.print("[bold red]✗[/bold red] Update failed.")
                    raise typer.Exit(1)
        else:
            # Windows refuses to overwrite a running .exe. Stage the new binary
            # next to the current one and finish the swap with a short-lived
            # detached helper once this process exits.
            staged = current_exe.with_name(current_exe.stem + ".new.exe")
            tmp_path.replace(staged)
            subprocess.Popen(
                ["cmd", "/c", "timeout", "/t", "2", "&&", "move", "/Y", str(staged), str(current_exe)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
            )

        progress.stop()

    if is_windows:
        console.print(f"[bold green]✓[/bold green] v{latest} staged — finishing install in a few seconds. Re-open your terminal.")
    else:
        console.print(f"[bold green]✓[/bold green] Updated to v{latest}.")


@app.command()
def version():
    """Show CLI version and API status."""
    client = AgentsClient()
    console.print(f"[bold cyan]Agents CLI[/bold cyan] v{CLI_VERSION}")
    console.print(f"Platform: [dim]{platform.system()} {platform.machine()}[/dim]")

    try:
        health = client.health()
        console.print(f"API: [bold green]online[/bold green] — {health.get('skills_registered', 0)} skills registered")
    except Exception:
        console.print("API: [bold red]unreachable[/bold red]")

    latest = _latest_known_version()
    if latest and _is_newer(latest, CLI_VERSION):
        console.print(f"\n[yellow]![/yellow] Update available: {latest}. Run [bold]agents update[/bold].")


def cli():
    app()


if __name__ == "__main__":
    cli()
