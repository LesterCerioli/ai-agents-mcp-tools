"""Server-side natural-language intent router.

Classifies a free-form user query into a concrete skill call, then proposes
a list of follow-up suggestions the user can approve one at a time.
"""
from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.orchestrator import AgentOrchestrator
    from app.llm.base import BaseLLMProvider

# ── User language detection ──────────────────────────────────────────────────

_PT_RE = re.compile(
    r"\b(não|está|estou|tenho|minha|meu|tive|falhou|preciso|quero|pode|"
    r"como|para|com|voce|você|aplicação|projeto|serviço|erro|obrigado|"
    r"arquivo|executar|rodando|funciona|problema|ajuda|gostaria)\b",
    re.IGNORECASE,
)


def detect_user_language(text: str) -> str:
    """Return 'pt' if text is Portuguese, 'en' otherwise."""
    return "pt" if _PT_RE.search(text) else "en"


# ── Diagnostic keyword sets (Portuguese + English) ───────────────────────────

_DIAGNOSTIC_RE = re.compile(
    r"\b("
    r"erro|erros|error|errors|bug|bugs"
    r"|falha|falhas|falhou|falhando|fail(?:ing|ed|ure)?"
    r"|n[aã]o (?:est[aá]|inicia|compila|roda|funciona|sobe|abre)"
    r"|n[aã]o (?:est[aá] )?(?:inicializando|compilando|rodando|funcionando|subindo)"
    r"|not (?:starting|working|compiling|running|building|booting)"
    r"|crash(?:ing|ed)?|broken|problema|issue|panic|exception"
    r"|import.*not used|undefined|cannot use|undeclared"
    r"|type.*mismatch|syntax.*error|module not found"
    r"|aplicação.*n[aã]o|app.*n[aã]o|servi[cç]o.*n[aã]o"
    r")",
    re.IGNORECASE,
)

# ── Improvement / generation keywords ────────────────────────────────────────

_IMPROVE_RE = re.compile(
    r"\b(melhor(?:ar|ia)|melhoria|improve|refactor|otimiz|optim|refatora|clean(?:up)?)\b",
    re.IGNORECASE,
)

# ── Skill → follow-up suggestions (resource-aware) ──────────────────────────

_SUGGESTIONS: dict[str, list[dict[str, Any]]] = {
    # Go generative
    "go.gorm_entity": [
        {"description": "Adicionar contrato de repositório",   "agent": "go", "skill": "go.repository_contract"},
        {"description": "Adicionar implementação de repositório","agent": "go", "skill": "go.repository_impl"},
        {"description": "Adicionar implementação de serviço",  "agent": "go", "skill": "go.service_impl"},
        {"description": "Adicionar controller CRUD",           "agent": "go", "skill": "go.controller"},
        {"description": "Gerar migration SQL",                 "agent": "go", "skill": "go.generate_migration"},
    ],
    "go.repository_contract": [
        {"description": "Adicionar implementação de repositório","agent": "go", "skill": "go.repository_impl"},
        {"description": "Adicionar implementação de serviço",  "agent": "go", "skill": "go.service_impl"},
    ],
    "go.repository_impl": [
        {"description": "Adicionar implementação de serviço",  "agent": "go", "skill": "go.service_impl"},
        {"description": "Adicionar controller CRUD",           "agent": "go", "skill": "go.controller"},
    ],
    "go.service_impl": [
        {"description": "Adicionar controller CRUD",           "agent": "go", "skill": "go.controller"},
        {"description": "Adicionar Swagger",                   "agent": "go", "skill": "go.swagger_fiber"},
    ],
    "go.controller": [
        {"description": "Adicionar Swagger/OpenAPI",           "agent": "go", "skill": "go.swagger_fiber"},
        {"description": "Gerar suíte de testes",               "agent": "go", "skill": "go.test_suite"},
        {"description": "Adicionar Docker",                    "agent": "go", "skill": "go.docker_setup"},
    ],
    "go.fiber_full_project": [
        {"description": "Adicionar Swagger/OpenAPI",           "agent": "go", "skill": "go.swagger_fiber"},
        {"description": "Adicionar Docker + docker-compose",   "agent": "go", "skill": "go.docker_setup"},
        {"description": "Gerar suíte de testes",               "agent": "go", "skill": "go.test_suite"},
        {"description": "Gerar migration inicial",             "agent": "go", "skill": "go.generate_migration"},
    ],
    "go.swagger_fiber": [
        {"description": "Adicionar suíte de testes",           "agent": "go", "skill": "go.test_suite"},
        {"description": "Adicionar Docker",                    "agent": "go", "skill": "go.docker_setup"},
    ],
    "go.generate_migration": [
        {"description": "Adicionar implementação de repositório","agent": "go", "skill": "go.repository_impl"},
    ],
    "go.docker_setup": [
        {"description": "Gerar suíte de testes",               "agent": "go", "skill": "go.test_suite"},
    ],
    # Diagnostic — use "command" type so the CLI just prints the command
    # instead of trying to call /skills/execute (which would fail without project-specific params)
    "diagnostic.go_diagnose": [
        {"type": "command", "description": "Verificar build após o fix",           "command": "go build ./..."},
        {"type": "command", "description": "Executar docker compose build",        "command": "docker compose build"},
        {"type": "command", "description": "Limpar e re-baixar dependências",      "command": "go mod tidy && go mod download"},
    ],
    "diagnostic.nextjs_diagnose": [
        {"type": "command", "description": "Verificar TypeScript após o fix",      "command": "npx tsc --noEmit"},
        {"type": "command", "description": "Validar build de produção",            "command": "next build"},
        {"type": "command", "description": "Reinstalar dependências Node",         "command": "npm ci"},
    ],
    "diagnostic.python_diagnose": [
        {"type": "command", "description": "Verificar sintaxe após o fix",         "command": "python -m py_compile **/*.py"},
        {"type": "command", "description": "Rodar testes com pytest",              "command": "pytest -v"},
        {"type": "command", "description": "Verificar dependências instaladas",    "command": "pip install -r requirements.txt"},
    ],
    # Next.js
    "nextjs.generate_page": [
        {"description": "Adicionar loading state",             "agent": "nextjs",     "skill": "nextjs.generate_loading"},
        {"description": "Adicionar tratamento de erros",       "agent": "nextjs",     "skill": "nextjs.generate_error_page"},
        {"description": "Adicionar componente de navegação",   "agent": "nextjs",     "skill": "nextjs.generate_component"},
    ],
    "nextjs.generate_component": [
        {"description": "Adicionar store Zustand",             "agent": "frontend",   "skill": "frontend.implement_zustand_store"},
        {"description": "Adicionar validação Zod",             "agent": "frontend",   "skill": "frontend.generate_zod_schema"},
    ],
    "nextjs.setup_nextauth": [
        {"description": "Gerar validação de variáveis de env", "agent": "vercel",     "skill": "vercel.generate_env_validation"},
        {"description": "Adicionar middleware de proteção",    "agent": "nextjs",     "skill": "nextjs.generate_middleware"},
    ],
    # Backend Python
    "backend.fastapi_endpoint": [
        {"description": "Adicionar model SQLAlchemy",          "agent": "backend",    "skill": "backend.sqlalchemy_model"},
        {"description": "Adicionar repository pattern",        "agent": "backend",    "skill": "backend.repository_pattern"},
        {"description": "Adicionar suíte de testes",           "agent": "backend",    "skill": "backend.pytest_suite"},
    ],
    "backend.sqlalchemy_model": [
        {"description": "Adicionar endpoint FastAPI",          "agent": "backend",    "skill": "backend.fastapi_endpoint"},
        {"description": "Adicionar repository pattern",        "agent": "backend",    "skill": "backend.repository_pattern"},
    ],
}

# ── Language detection from project files ────────────────────────────────────

def _detect_lang_from_context(project_context: dict[str, Any]) -> str | None:
    file_paths = [f.get("path", "") for f in project_context.get("files", [])]
    paths_str = " ".join(file_paths)
    if "go.mod" in paths_str or any(p.endswith(".go") for p in file_paths):
        return "go"
    if "package.json" in paths_str and any(
        p.endswith((".tsx", ".ts")) for p in file_paths
    ):
        return "nextjs"
    if any(p.endswith(".py") for p in file_paths) or "requirements.txt" in paths_str:
        return "python"
    return None


def _is_diagnostic(query: str) -> bool:
    return bool(_DIAGNOSTIC_RE.search(query))


# ── Main router ───────────────────────────────────────────────────────────────

_ROUTE_SYSTEM = """\
You are an AI agent router. Given a user query and available skills, output ONLY a JSON object:
{"agent": "<agent_name>", "skill": "<skill_name>", "params": {<param_name>: <value>}, "description": "<one sentence in the same language as the query>"}

Rules:
- Use the exact agent and skill names from the list provided
- Extract all required params from the query context
- description must be in the SAME LANGUAGE as the user query (Portuguese if query is in PT)
- Return ONLY the JSON object, no markdown, no explanation
"""


async def route_intent(
    query: str,
    project_context: dict[str, Any],
    orchestrator: "AgentOrchestrator",
    llm: "BaseLLMProvider | None" = None,
) -> dict[str, Any]:
    """Classify a natural-language query into a concrete skill call + suggestions."""

    user_lang = detect_user_language(query)

    # 1. Diagnostic shortcut
    if _is_diagnostic(query):
        lang = _detect_lang_from_context(project_context) or "go"
        skill_map = {
            "go": ("diagnostic", "diagnostic.go_diagnose"),
            "nextjs": ("diagnostic", "diagnostic.nextjs_diagnose"),
            "python": ("diagnostic", "diagnostic.python_diagnose"),
        }
        agent_name, skill_name = skill_map.get(lang, ("diagnostic", "diagnostic.go_diagnose"))
        return {
            "intent": "diagnostic",
            "is_diagnostic": True,
            "agent": agent_name,
            "skill": skill_name,
            "params": {},
            "detected_language": lang,
            "user_language": user_lang,
            "description": f"Diagnose and fix {lang} errors in your project",
            "suggestions": _get_suggestions(skill_name, {}),
            "confidence": 0.9,
        }

    # 2. BM25 matching
    project_summary = _build_project_summary(project_context)
    enriched = f"{project_summary} {query}" if project_summary else query
    plan = await orchestrator.plan(enriched)

    if not plan.tasks:
        return {
            "intent": "unknown",
            "is_diagnostic": False,
            "description": "Could not match your request to any available skill.",
            "suggestions": [],
            "confidence": 0.0,
        }

    best = plan.tasks[0]
    agent_name: str = best["agent"]
    skill_name: str = best["skill"]
    params: dict[str, Any] = {}

    # 3. LLM param extraction
    if llm:
        try:
            agent = orchestrator.agents[agent_name]
            skill = agent.get_skill(skill_name)
            required = [p for p in skill.schema()["parameters"] if p.get("required", True)]
            if required:
                param_lines = "\n".join(f"- {p['name']}: {p['description']}" for p in required)
                skills_hint = f"\nSkill: {skill_name}\nRequired params:\n{param_lines}"
                full_query = f"User query: {query}\nProject: {project_summary}{skills_hint}"
                raw = await llm.chat(full_query, system_prompt=_ROUTE_SYSTEM)
                parsed = _parse_json(raw)
                if isinstance(parsed, dict):
                    params = parsed.get("params", {})
                    description = parsed.get("description", "")
                else:
                    description = skill.description[:120]
            else:
                description = skill.description[:120]
        except Exception:
            description = skill_name
    else:
        try:
            skill = orchestrator.agents[agent_name].get_skill(skill_name)
            description = skill.description[:120]
        except Exception:
            description = skill_name

    # 4. Fallback params from project context
    if not params:
        params = _infer_params(skill_name, query, project_context)

    return {
        "intent": "generate",
        "is_diagnostic": False,
        "agent": agent_name,
        "skill": skill_name,
        "params": params,
        "description": description,
        "user_language": user_lang,
        "suggestions": _get_suggestions(skill_name, params),
        "confidence": 0.75,
    }


def _get_suggestions(skill_name: str, base_params: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _SUGGESTIONS.get(skill_name, [])
    result = []
    for s in raw:
        sug_type = s.get("type", "skill")
        if sug_type == "command":
            result.append({
                "type": "command",
                "description": s["description"],
                "command": s.get("command", ""),
            })
        else:
            merged_params = dict(base_params)
            merged_params.update(s.get("params", {}))
            result.append({
                "type": "skill",
                "description": s["description"],
                "agent": s["agent"],
                "skill": s["skill"],
                "params": merged_params,
            })
    return result


def _build_project_summary(project_context: dict[str, Any]) -> str:
    if not project_context:
        return ""
    ptype = project_context.get("project_type", "")
    count = project_context.get("file_count", 0)
    files = [f.get("path", "") for f in project_context.get("files", [])[:10]]
    return f"[{ptype} project, {count} files: {', '.join(files)}]"


def _infer_params(skill_name: str, query: str, project_context: dict[str, Any]) -> dict[str, Any]:
    """Best-effort param extraction without LLM."""
    params: dict[str, Any] = {}

    # Try to extract module name from go.mod
    for f in project_context.get("files", []):
        if f.get("path") == "go.mod":
            for line in (f.get("content") or "").splitlines():
                if line.startswith("module "):
                    params["module_name"] = line.split()[1]
                    break

    # Try to extract resource from the query
    resource_match = re.search(
        r"\b(?:entidade|entity|recurso|resource|modelo|model|tabela|table|para\s+(?:o\s+)?|for\s+(?:the\s+)?)\s*[\"']?(\w+)[\"']?",
        query,
        re.IGNORECASE,
    )
    if resource_match:
        params["resource"] = resource_match.group(1).lower().rstrip("s")

    # App name from module_name
    if "module_name" in params and "app_name" not in params:
        params["app_name"] = params["module_name"].split("/")[-1]

    return params


def _parse_json(raw: str) -> Any:
    import json
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass
    return None
