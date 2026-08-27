"""
Grok + Skills Analyzer — avalia projetos existentes e orquestra melhorias/correções.

Este módulo é o coração da integração Grok × skills pedida:

  - Avalia projeto já existente (structure, stack, debt)
  - Entende requisitos do usuário (natural language)
  - Usa Grok para mapear requisitos → skills concretas (agent, skill, params)
  - Executa as skills via Orchestrator (template + Grok codegen)
  - Quando skill precisa de geração LLM, Grok já está injetado no agent
  - Também gera patches/correções diretas via Grok quando não há skill exata

Fluxo para workflow/improve:
  scan_project() -> Grok.analyze_project() -> BM25 + Grok skill mapping -> execute skills
  + Grok generate_code para fixes que não cabem em skill

Fluxo para diagnostic:
  error_output + source_files -> Grok propõe fix -> aplica via skill diagnostic

Nunca expõe GROCK_API_TOKEN; usa GrokProvider que o mascara.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Skills consideradas para improve (ordem não importa — BM25 + Grok escolhe)
_IMPROVE_SYSTEM = """\
You are the skill router for an AI code generation platform.

Available agents and some of their skills (use EXACT names, no invention):
- go: go.setup_project, go.go_struct, go.repository, go.service, go.docker_setup, go.test_suite, go.generate_migration, go.config, go.logger, go.fiber_full_project, go.initializers, go.gorm_entity, go.swagger_fiber, go.fiber_app, go.fiber_handler, go.fiber_routes, go.fiber_middleware, go.gin_app, go.gin_handler, etc.
- backend: backend.fastapi_endpoint, backend.sqlalchemy_model, backend.repository_pattern, backend.docker_setup, backend.pytest_suite
- nextjs: nextjs.generate_component, nextjs.generate_page, nextjs.generate_layout, nextjs.generate_api_route, nextjs.generate_server_action, nextjs.generate_middleware, nextjs.setup_nextauth, nextjs.generate_form_component, nextjs.generate_crud_actions, nextjs.optimize_images, etc.
- design: design.generate_tailwind_config, design.generate_design_tokens_css, design.generate_dashboard, design.generate_data_table, design.implement_dark_mode, etc.
- frontend: frontend.implement_zustand_store, frontend.generate_zod_schema, frontend.implement_tanstack_query, etc.
- vercel: vercel.generate_config, vercel.deployment_checklist, vercel.generate_env_validation
- diagnostic: diagnostic.go_diagnose, diagnostic.nextjs_diagnose, diagnostic.python_diagnose
- solid/design_patterns/quality_assessment: analysis skills

You must map the user instruction and the project snapshot to a JSON array of skill calls.

Return ONLY a JSON object: {"skills": [{"agent":"go","skill":"go.gorm_entity","params":{"resource":"product","module_name":"github.com/org/app"},"reason":"criar entidade Product"}, ...], "analysis":"brief pt/en analysis"}
No markdown, no extra text.
"""

def _try_parse_json(text: str) -> dict | None:
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None

def _extract_go_context(project_files: list[dict[str, Any]]) -> dict[str, str]:
    by_path = {f.get("path", ""): f.get("content") or "" for f in project_files}
    module_name = ""
    app_name = ""
    framework = "fiber"
    for line in by_path.get("go.mod", "").splitlines():
        s = line.strip()
        if s.startswith("module "):
            module_name = s.split()[1]
            app_name = module_name.split("/")[-1]
        if "gofiber/fiber" in s:
            framework = "fiber"
        elif "gin-gonic/gin" in s:
            framework = "gin"
        elif "labstack/echo" in s:
            framework = "echo"
        elif "gorilla/mux" in s:
            framework = "gorilla"
        elif "go-chi/chi" in s:
            framework = "chi"
    return {"module_name": module_name, "app_name": app_name, "framework": framework}

async def grok_analyze_and_plan(
    instruction: str,
    project_files: list[dict[str, Any]],
    project_type: str,
    llm: BaseLLMProvider | None,
    orchestrator: Any | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Usa Grok (se disponível) para avaliar o projeto e propor skills.
    Fallback: BM25 puro se Grok não estiver disponível ou falhar.

    Returns dict com keys: analysis, skills (list de task specs), raw (optional)
    Cada skill entry: {"agent": str, "skill": str, "params": dict, "reason": str}
    """
    # Fallback rápido se sem LLM
    if llm is None:
        if orchestrator:
            enriched = f"[{project_type} project] {instruction}"
            plan = await orchestrator.plan(enriched)
            return {
                "analysis": plan.analysis,
                "skills": plan.tasks,
                "source": "bm25-fallback-no-llm",
            }
        return {"analysis": "No LLM, waiting for BM25", "skills": [], "source": "no-llm"}

    # Tenta usar GrokProvider.analyze_project se existir
    grok_plan = None
    if hasattr(llm, "analyze_project"):
        try:
            raw = await llm.analyze_project(  # type: ignore
                instruction=instruction,
                project_files=project_files,
                project_type=project_type,
            )
            parsed = _try_parse_json(raw)
            if parsed and isinstance(parsed.get("suggested_skills"), list):
                grok_plan = {
                    "analysis": parsed.get("analysis", "")[:2000],
                    "skills": parsed.get("suggested_skills", []),
                    "raw": parsed,
                    "source": "grok-analyze",
                    "detected_stack": parsed.get("detected_stack"),
                    "requirements": parsed.get("requirements"),
                }
            elif parsed and isinstance(parsed.get("skills"), list):
                grok_plan = {
                    "analysis": parsed.get("analysis", "")[:2000],
                    "skills": parsed.get("skills", []),
                    "raw": parsed,
                    "source": "grok-analyze",
                }
        except Exception as exc:
            logger.debug("grok analyze_project failed: %s", exc)

    # Se Grok analyze não deu retorno útil, tenta chamada direta de routing
    if grok_plan is None or not grok_plan.get("skills"):
        # Monta sumário do projeto para o prompt
        file_list = [f.get("path", "") for f in project_files[:30]]
        summary = (
            f"Project type: {project_type}\n"
            f"Files ({len(project_files)}): {', '.join(file_list[:20])}\n"
            f"Instruction: {instruction}\n"
        )
        # Adiciona go.mod/go context se existir
        go_ctx = _extract_go_context(project_files)
        if go_ctx["module_name"]:
            summary += f"Go module: {go_ctx['module_name']} framework={go_ctx['framework']}\n"
            # Dá dicas de conteúdo do go.mod / package.json para o modelo
            for f in project_files:
                if f.get("path") in ("go.mod", "package.json", "pyproject.toml", "requirements.txt"):
                    summary += f"\n--- {f['path']} ---\n{(f.get('content') or '')[:2500]}\n"

        try:
            from app.llm.base import LLMMessage
            messages = [
                LLMMessage(role="system", content=_IMPROVE_SYSTEM),
                LLMMessage(role="user", content=summary),
            ]
            raw = (await llm.complete(messages, max_tokens=2500, temperature=0.15)).content  # type: ignore
            parsed = _try_parse_json(raw)
            if parsed and isinstance(parsed.get("skills"), list):
                return {
                    "analysis": parsed.get("analysis", "")[:2000],
                    "skills": parsed.get("skills", [])[:10],
                    "raw": parsed,
                    "source": "grok-direct",
                }
        except Exception as exc:
            logger.debug("grok direct routing failed: %s", exc)

    if grok_plan and grok_plan.get("skills"):
        # Normaliza: garante params é dict, agent/skill existem
        normalized: list[dict] = []
        for item in grok_plan["skills"][:10]:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent", "")).strip()
            skill = str(item.get("skill", "")).strip()
            params = item.get("params", {}) if isinstance(item.get("params"), dict) else {}
            reason = str(item.get("reason", item.get("description", "")))[:300]
            if agent and skill:
                normalized.append({"agent": agent, "skill": skill, "params": params, "reason": reason})
        grok_plan["skills"] = normalized
        return grok_plan

    # Último fallback: BM25
    if orchestrator:
        enriched = f"[{project_type} project] {instruction}"
        plan = await orchestrator.plan(enriched)
        return {
            "analysis": plan.analysis,
            "skills": plan.tasks,
            "source": "bm25-fallback-grok-failed",
        }
    return {"analysis": "No plan", "skills": [], "source": "no-orchestrator"}


async def grok_fix_project_files(
    instruction: str,
    project_files: list[dict[str, Any]],
    project_type: str,
    llm: BaseLLMProvider | None,
    on_artifact: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Quando o mapeamento de skills não cobre total a instrução, usa Grok para gerar
    arquivos de correção/criação diretamente (patches). Retorna lista de artifacts
    compatível com CodeArtifact: {filename, content, language, description}.

    Só deve ser chamado após executar skills; serve como complemento.
    """
    if llm is None:
        return []

    # Só GrokProvider sabe fazer generate_code de forma confiável aqui; tentamos igual
    try:
        from app.llm.base import LLMMessage
        # Resume arquivos importantes
        important = []
        for f in project_files:
            p = f.get("path", "")
            # Prioriza configs e arquivos pequenos
            if p in ("go.mod", "package.json", "Dockerfile", "docker-compose.yml", "requirements.txt", "pyproject.toml") or p.endswith((".go", ".tsx", ".ts", ".py")):
                important.append(f)
            if len(important) >= 15:
                break
        files_block = "\n\n".join(
            f"--- {fi['path']} ---\n{(fi.get('content') or '')[:2000]}" for fi in important
        )
        prompt = (
            f"Instrução de melhoria/correção: {instruction}\n"
            f"Tipo de projeto: {project_type}\n"
            f"Arquivos relevantes (parcial):\n{files_block}\n\n"
            f"Gere APENAS um arquivo que implementa a melhoria pedida. "
            f"Se a melhoria requer vários arquivos, escolha o MAIS CRÍTICO. "
            f"Responda com o código completo do arquivo e indique o path no formato:\n"
            f"FILENAME: <path/relativo>\n"
            f"```<linguagem>\n<code>\n```\n"
            f"Se não for possível, explique por que mas ainda retorne um artifact mínimo.\n"
        )
        messages = [
            LLMMessage(
                role="system",
                content=(
                    "You are a senior engineer that fixes and improves existing projects. "
                    "Generate the single most important file needed to satisfy the instruction. "
                    "Return the filename and code. Keep code production-ready, no placeholders."
                ),
            ),
            LLMMessage(role="user", content=prompt),
        ]
        raw = (await llm.complete(messages, max_tokens=3500, temperature=0.1)).content  # type: ignore
        # Extrai filename
        m = re.search(r"FILENAME:\s*([^\n\r`]+)", raw)
        filename = m.group(1).strip().strip("`").strip() if m else ""
        # Extrai code block
        code_match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", raw, re.DOTALL)
        code = code_match.group(1).strip() if code_match else raw.strip()
        if not filename:
            # tenta inferir filename a partir do tipo de projeto
            if project_type == "go":
                filename = "internal/service/generated_by_grok.go"
            elif project_type in ("nextjs", "node"):
                filename = "src/components/GeneratedByGrok.tsx"
            elif project_type == "python":
                filename = "app/generated_by_grok.py"
            else:
                filename = "GROK_GENERATED.md"
        lang = "go" if filename.endswith(".go") else "tsx" if filename.endswith(".tsx") else "python" if filename.endswith(".py") else "markdown"
        # Heurística de linguagem
        if filename.endswith(".tsx") or filename.endswith(".ts"):
            lang = "typescript"
        elif filename.endswith(".py"):
            lang = "python"
        elif filename.endswith(".go"):
            lang = "go"
        artifacts = [{"filename": filename, "content": code, "language": lang, "description": f"Gerado por Grok para: {instruction[:80]}"}]
        # Detecta se gerou múltiplos artifacts no raw (FILENAME repetidos)
        extra = re.findall(r"FILENAME:\s*([^\n\r`]+)\s*\n```(?:\w+)?\s*(.*?)\s*```", raw, re.DOTALL)
        if len(extra) > 1:
            artifacts = []
            for fname, fcode in extra[:5]:
                fname = fname.strip().strip("`")
                fcode = fcode.strip()
                flang = "go" if fname.endswith(".go") else "typescript" if fname.endswith((".ts", ".tsx")) else "python" if fname.endswith(".py") else "text"
                artifacts.append({"filename": fname, "content": fcode, "language": flang, "description": f"Gerado por Grok para: {instruction[:60]}"})
        return artifacts
    except Exception as exc:
        logger.debug("grok_fix_project_files failed: %s", exc)
        return []

