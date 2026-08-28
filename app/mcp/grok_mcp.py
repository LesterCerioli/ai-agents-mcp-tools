"""
Grok MCP Server — integração forçada Grok + Skills.

Expõe via MCP (SSE em /mcp/grok) as capacidades Grok:
  - evaluate_project: avalia projeto existente e sugere melhorias com skills
  - improve_project: aplica melhorias num projeto (via orchestrator + Grok)
  - generate_with_grok: geração direta de código Grok-aware (com skill context)
  - diagnose_with_grok: diagnóstico Grok-enhanced
  - grok_chat: chat geral com Grok (mantém skills no contexto)

Tudo usa GROCK_API_TOKEN internamente sem nunca expor valor.

Mount: app.mount("/mcp/grok", GrokMCPServer(...).sse_app())
"""
from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

try:
    from mcp.server import FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        try:
            from fastmcp import FastMCP
        except ImportError:
            import logging as _log
            _log.getLogger(__name__).warning('FastMCP nao disponivel — MCP stub')
            class _StubMCP:
                def __init__(self, name: str):
                    self.name = name
                def resource(self, uri: str):
                    def decorator(fn):
                        return fn
                    return decorator
                def tool(self):
                    def decorator(fn):
                        return fn
                    return decorator
                def sse_app(self):
                    from starlette.responses import JSONResponse
                    from starlette.routing import Route
                    from starlette.applications import Starlette
                    async def stub(request):
                        return JSONResponse({'error': 'MCP stub — FastMCP nao instalado'})
                    return Starlette(routes=[Route('/{path:path}', endpoint=stub)])
            FastMCP = _StubMCP  # type: ignore

if TYPE_CHECKING:
    from app.agents.orchestrator import AgentOrchestrator
    from app.architecture.workflow_coordinator import WorkflowCoordinator
    from app.architecture.context.pipeline_context import PipelineContext
    from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def create_grok_mcp(
    orchestrator: "AgentOrchestrator",
    workflow_coordinator: "WorkflowCoordinator | None" = None,
    sessions: "dict[str, PipelineContext] | None" = None,
    llm: "BaseLLMProvider | None" = None,
) -> FastMCP:
    mcp = FastMCP("grok-mcp")
    sessions = sessions or {}

    @mcp.resource("grok://status")
    async def grok_status() -> str:
        import os
        grok_configured = bool(os.getenv("GROCK_API_TOKEN") or os.getenv("GROK_API_TOKEN") or os.getenv("XAI_API_KEY"))
        is_grok = False
        model = "none"
        try:
            from app.llm.grok import GrokProvider
            is_grok = isinstance(llm, GrokProvider)
            model = getattr(llm, "model", "unknown") if llm else "none"
        except Exception:
            pass
        return json.dumps({
            "grok_configured": grok_configured,
            "grok_forced": grok_configured,
            "provider_is_grok": is_grok,
            "model": model,
            "llm_available": llm is not None,
            "skills_registered": len(orchestrator.agents["nextjs"].available_skills) if orchestrator else 0,
        }, indent=2)

    @mcp.resource("grok://skills")
    async def grok_skills() -> str:
        return json.dumps(orchestrator.list_all_skills(), indent=2)

    @mcp.tool()
    async def evaluate_project(
        instruction: str,
        project_type: str = "unknown",
        files: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Avalia um projeto existente usando Grok + skills.

        Analisa estrutura, detecta stack, dívidas técnicas e mapeia a instrução
        para skills concretas com params.

        Args:
            instruction: O que você quer melhorar/corrigir/implementar (PT ou EN)
            project_type: go | nextjs | python | node | unknown (auto se vazio)
            files: lista de {path, content} do projeto (opcional — se vazio usa BM25 puro)

        Returns JSON com: analysis, detected_stack, suggested_skills [{agent, skill, params, reason}], corrections
        """
        from app.llm.grok_analyzer import grok_analyze_and_plan
        files = files or []
        # Auto-detect type se não vier
        if project_type == "unknown" and files:
            paths = {f.get("path", "") for f in files}
            if "go.mod" in paths:
                project_type = "go"
            elif "package.json" in paths:
                project_type = "nextjs" if any("next" in (f.get("content") or "") for f in files if f.get("path") == "package.json") else "node"
            elif "requirements.txt" in paths or "pyproject.toml" in paths:
                project_type = "python"

        grok_llm = llm or orchestrator.agents["nextjs"].llm or orchestrator.agents["go"].llm
        result = await grok_analyze_and_plan(
            instruction=instruction,
            project_files=files,
            project_type=project_type,
            llm=grok_llm,
            orchestrator=orchestrator,
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def improve_project(
        instruction: str,
        project_type: str = "unknown",
        files: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Aplica melhorias num projeto existente: avalia com Grok, executa skills e
        gera artifacts prontos para escrita.

        Fluxo: Grok avalia -> seleciona skills -> executa cada skill -> complementa com Grok fix se necessário.

        Args:
            instruction: Requisitos de melhoria/correção
            project_type: Tipo do projeto
            files: Arquivos atuais (path, content)

        Returns JSON com: success, analysis, files_to_write [{filename, content, language}], summary, errors
        """
        from app.llm.grok_analyzer import grok_analyze_and_plan, grok_fix_project_files
        files = files or []
        if project_type == "unknown" and files:
            paths = {f.get("path", "") for f in files}
            if "go.mod" in paths:
                project_type = "go"
            elif "package.json" in paths:
                project_type = "nextjs"
            elif "requirements.txt" in paths or "pyproject.toml" in paths:
                project_type = "python"

        grok_llm = llm or orchestrator.agents["nextjs"].llm or orchestrator.agents["go"].llm
        plan = await grok_analyze_and_plan(
            instruction=instruction,
            project_files=files,
            project_type=project_type,
            llm=grok_llm,
            orchestrator=orchestrator,
        )
        skills = plan.get("skills", [])
        all_artifacts: list[dict] = []
        errors: list[str] = []

        for spec in skills[:8]:
            agent_name = spec.get("agent", "")
            skill_name = spec.get("skill", "")
            params = spec.get("params", {}) if isinstance(spec.get("params"), dict) else {}
            if agent_name not in orchestrator.agents:
                errors.append(f"Agent desconhecido: {agent_name}")
                continue
            try:
                agent = orchestrator.agents[agent_name]
                # Tenta preencher params ausentes via fallback se Grok não forneceu tudo
                if not params:
                    # deixa skill falhar e reportar qual param falta
                    pass
                result = await agent.execute_skill(skill_name, **params)
                if result.success:
                    for art in result.artifacts:
                        all_artifacts.append({
                            "filename": art.filename,
                            "content": art.content,
                            "language": art.language,
                            "description": art.description,
                        })
                else:
                    errors.append(f"{agent_name}.{skill_name}: {result.error or result.summary}")
            except Exception as exc:
                errors.append(f"{agent_name}.{skill_name}: {exc}")

        # Se poucas skills ou Grok indicou que precisa complemento, gera fix direto
        if len(all_artifacts) < 2 and grok_llm is not None:
            try:
                extras = await grok_fix_project_files(
                    instruction=instruction,
                    project_files=files,
                    project_type=project_type,
                    llm=grok_llm,
                )
                for art in extras:
                    if art["filename"] not in {a["filename"] for a in all_artifacts}:
                        all_artifacts.append(art)
            except Exception as exc:
                logger.debug("grok_fix complement failed: %s", exc)

        return json.dumps({
            "success": len(errors) == 0,
            "analysis": plan.get("analysis", ""),
            "project_type": project_type,
            "skills_executed": len(skills),
            "files_to_write": all_artifacts,
            "files_count": len(all_artifacts),
            "errors": errors,
            "plan_source": plan.get("source", "unknown"),
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def generate_with_grok(
        prompt: str,
        language: str = "typescript",
        context: str | None = None,
    ) -> str:
        """
        Geração direta de código via Grok (ciente das skills).

        Args:
            prompt: O que gerar (ex: "crie um componente ProductCard")
            language: Linguagem (typescript, go, python, etc.)
            context: Contexto extra (ex: arquivos relevantes, stack)

        Returns JSON com: content (código), language, model
        """
        grok_llm = llm or orchestrator.agents["nextjs"].llm
        if grok_llm is None:
            return json.dumps({"error": "Nenhum LLM configurado. Defina GROCK_API_TOKEN."})
        try:
            code = await grok_llm.generate_code(prompt, language=language, context=context)
            return json.dumps({
                "success": True,
                "language": language,
                "content": code,
                "model": getattr(grok_llm, "model", "unknown"),
            }, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.exception("generate_with_grok failed")
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool()
    async def diagnose_with_grok(
        language: str,
        error_output: str,
        files: list[dict[str, Any]] | None = None,
        module_name: str = "",
    ) -> str:
        """
        Diagnóstico Grok-enhanced: envia erro + arquivos para Grok e retorna fix via skills diagnostic.

        Args:
            language: go | nextjs | python
            error_output: Output completo do build/erro
            files: Arquivos fonte relevantes [{path, content}]
            module_name: Go module (para go)

        Returns JSON com artifacts (arquivos corrigidos) e summary.
        """
        files = files or []
        # Primeiro tenta via skill diagnostic tradicional (que já usa Grok se LLM=Grok)
        lang = language.lower().strip()
        skill_map = {
            "go": ("diagnostic", "diagnostic.go_diagnose"),
            "nextjs": ("diagnostic", "diagnostic.nextjs_diagnose"),
            "next": ("diagnostic", "diagnostic.nextjs_diagnose"),
            "python": ("diagnostic", "diagnostic.python_diagnose"),
            "py": ("diagnostic", "diagnostic.python_diagnose"),
        }
        if lang not in skill_map:
            return json.dumps({"error": f"Unsupported language '{language}'"})
        agent_name, skill_name = skill_map[lang]
        import json as _json
        params: dict[str, Any] = {
            "error_output": error_output,
            "source_files": _json.dumps([{"path": f.get("path", ""), "content": f.get("content", "")} for f in files]),
        }
        if lang == "go" and module_name:
            params["module_name"] = module_name
        try:
            result = await orchestrator.run_skill(agent_name, skill_name, **params)
            skill_result = result.skill_results[0] if result.skill_results else None
            if skill_result:
                return json.dumps({
                    "success": skill_result.success,
                    "language": lang,
                    "summary": skill_result.summary,
                    "artifacts": [
                        {"filename": a.filename, "content": a.content, "language": a.language}
                        for a in skill_result.artifacts
                    ],
                    "instructions": skill_result.instructions,
                    "error": skill_result.error,
                }, indent=2, ensure_ascii=False)
            return json.dumps({"error": "No result from diagnostic skill"})
        except Exception as exc:
            logger.exception("diagnose_with_grok failed")
            return json.dumps({"error": str(exc)})

    @mcp.tool()
    async def grok_chat(
        message: str,
        system: str | None = None,
    ) -> str:
        """
        Chat direto com Grok (útil para orquestração e perguntas sobre skills).

        Args:
            message: Mensagem do usuário
            system: System prompt opcional (default: arquiteto que conhece as skills)

        Returns resposta do Grok como string JSON.
        """
        grok_llm = llm or orchestrator.agents["nextjs"].llm
        if grok_llm is None:
            return json.dumps({"error": "Nenhum LLM configurado. Defina GROCK_API_TOKEN."})
        try:
            from app.llm.base import LLMMessage
            sys_prompt = system or (
                "Você é o Grok integrado a um sistema de skills (go, nextjs, design, frontend, vercel, backend, diagnostic, solid). "
                "Ajude a entender requisitos, mapear para skills e gerar código. Responda de forma objetiva e técnica."
            )
            resp = await grok_llm.complete(
                [LLMMessage(role="system", content=sys_prompt), LLMMessage(role="user", content=message)]
            )
            return json.dumps({"success": True, "content": resp.content, "model": resp.model}, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.exception("grok_chat failed")
            return json.dumps({"success": False, "error": str(exc)})

    return mcp


class GrokMCPServer:
    """Wrapper que expõe o FastMCP Grok como ASGI app para mount."""

    def __init__(
        self,
        orchestrator: "AgentOrchestrator",
        workflow_coordinator: "WorkflowCoordinator | None" = None,
        sessions: "dict[str, PipelineContext] | None" = None,
        llm: "BaseLLMProvider | None" = None,
    ) -> None:
        resolved_llm = llm or orchestrator.agents["nextjs"].llm or orchestrator.agents["go"].llm
        self._mcp = create_grok_mcp(orchestrator, workflow_coordinator, sessions or {}, llm=resolved_llm)

    def sse_app(self):
        return self._mcp.sse_app()
