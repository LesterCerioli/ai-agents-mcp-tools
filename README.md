# Enterprise AI Agents & MCP Tools

An agentic backend platform that transforms natural-language business objectives into production-ready code scaffolds. Specialized agents cover Go, Python/FastAPI, Next.js, design systems, and Vercel deployments — all coordinated through an architecture pipeline and exposed via a FastAPI REST API and MCP (Model Context Protocol) servers.

---

## Agent Roster

| Agent | Skills | Focus |
|-------|--------|-------|
| `go` | 27 | Go 1.24 microservices — Fiber, Gin, Gorilla, Echo, Chi |
| `backend` | 6 | Python/FastAPI — endpoints, SQLAlchemy, repository pattern, Docker |
| `nextjs` | 25 | App Router, API routes, server actions, layouts, data fetching |
| `design` | 17 | UI components, design systems, dark mode, accessibility |
| `frontend` | 13 | State management, hooks, forms, animations, performance |
| `vercel` | 5 | Deployment, environment config, edge functions |

**Total: 93 registered skills.** All skills work in rule-based (template) mode without an LLM. When a `HUGGINGFACE_TOKEN` is configured, skills use the Hugging Face Inference API for context-aware output.

---

## Architecture Pipeline

The platform includes a multi-stage architecture pipeline that processes a business objective end-to-end:

```
[Natural Language Objective]
        ↓
[BusinessObjectiveParserAgent]
  — Extracts 7 requirement dimensions (scalability, compliance, availability, …)
  — Multi-turn clarification support
        ↓
[SolutionArchitectureDecisionEngine]
  — Rule-based pattern selection (microservices, hexagonal, monolith, …)
  — Bypassed when architecture_pattern is forced in the request
        ↓
[SolutionFlowDiagramAgent] → [ValidationAgent]
        ↓
[DesignPartnerOrchestrator]
  — Hexagonal | Microservices | Monolith design partner
        ↓
[WorkflowCoordinator]
  — Routes to GoAgent or BackendAgent based on backend_language
  — Generates frontend artifacts via NextJSAgent + DesignAgent
  — Writes every file to disk at output_dir/project_name/
```

### Requirement Dimensions

| Dimension | Examples |
|-----------|---------|
| `scalability` | expected users, peak load, growth rate |
| `availability` | target uptime (SLA), RTO, RPO |
| `compliance` | GDPR, HIPAA, SOC2, PCI-DSS, ISO 27001 |
| `domain_boundaries` | e-commerce, fintech, healthcare, SaaS, IoT |
| `integration` | Stripe, Kafka, REST/gRPC/WebSocket patterns |
| `budget` | startup / mid-market / enterprise tier |
| `team_size` | engineering headcount, organisational maturity |

---

## MCP Servers

Four MCP (Model Context Protocol) SSE servers are mounted on the API and can be consumed by any MCP-compatible client (Claude Desktop, custom agents, etc.):

| Mount path | Purpose |
|---|---|
| `/mcp/architecture` | Pipeline tools: parse, clarify, decide, select design partner |
| `/mcp/backend` | Python/FastAPI skill execution |
| `/mcp/frontend` | Next.js + design skill execution |
| `/mcp/orchestrate` | Cross-agent orchestration |

---

## Intelligence Architecture

No model runs inside this application. All LLM inference is delegated to the **Hugging Face Inference API** over HTTP, making the service deployable on minimal infrastructure (0.5 CPU / 512 MB RAM):

```
This application                     Hugging Face
┌──────────────────────────┐         ┌────────────────────────────────┐
│  FastAPI                 │         │  Qwen2.5-Coder-7B-Instruct     │
│  AgentOrchestrator       │──HTTP──▶│  (or any configured model)     │
│  Architecture Pipeline   │◀────────│  running on their GPU servers  │
│  93 Skills               │         └────────────────────────────────┘
│  BM25 Skill Router       │
└──────────────────────────┘
  RAM: ~150–200 MB   |   LLM RAM: 0 (remote)
```

### Skill Routing — BM25 (zero cost, zero API calls)

Skill selection uses an **in-memory BM25 index** built at startup from the `name + description + tags` of all 93 skills. No LLM call is needed to decide which skill to invoke.

```
"build a Go microservice with JWT auth"
  → BM25 search (local, microseconds)
  → go.fiber_handler (0.94), go.fiber_middleware (0.91), go.service (0.87), …
```

---

## Requirements

- Python 3.12+
- Hugging Face account — free token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) with **Inference** permission enabled

---

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd ai-agents-mcp-tools

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install all dependencies
make install
# or: pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# Edit .env — set HUGGINGFACE_TOKEN
```

---

## Running

### Development

```bash
make dev      # hot-reload on port 3443
make run      # without reload, port 3443
make stop     # kill the process on port 3443
make test     # full test suite
make lint     # ruff linter
```

API: `http://localhost:3443`  
Interactive docs: `http://localhost:3443/docs`

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 3030 --reload
```

---

## API Reference

### Health

```
GET /          — service status
GET /health    — agent count, skill count, LLM status, MCP server list
```

### Agents & Skills

```
GET /agents                   — list all agents and their skill counts
GET /skills                   — list all 93 skills
GET /skills?agent=go          — skills for a specific agent
GET /skills?category=backend
GET /skills?tag=fiber
```

### Execute a Skill

```http
POST /skills/execute
{
  "agent": "go",
  "skill": "go.fiber_handler",
  "params": {
    "resource": "order",
    "module_name": "github.com/org/order-service"
  }
}
```

### Orchestrate a Multi-Agent Task

```http
POST /orchestrate
{
  "task": "Create a SaaS dashboard with auth, dark mode, and data tables"
}
```

### Architecture Pipeline

```http
POST /architecture/parse
{
  "objective": "Build a HIPAA-compliant telemedicine platform for 10,000 concurrent patients",
  "session_id": null
}
```

```http
POST /architecture/clarify
{
  "session_id": "<session_id>",
  "answer": "We need 99.9% uptime and plan to grow to 1 million users in 2 years."
}
```

```http
GET /architecture/sessions/{session_id}
```

### Full Project Scaffold

Runs the complete pipeline — architecture decision → skill generation → writes every file to disk.

```http
POST /workflow/scaffold
{
  "objective": "Build a Go 1.24 microservice for order management with Fiber v2, PostgreSQL, JWT auth, and clean architecture",
  "project_name": "order-service",
  "output_dir": "/home/user/projects",
  "scope": "backend",
  "backend_language": "go",
  "backend_framework": "fiber",
  "architecture_pattern": "microservices"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `objective` | ✓ | — | Natural-language description of what to build |
| `project_name` | ✓ | — | Directory name for the output |
| `output_dir` | ✓ | — | Absolute path where the project folder is created |
| `scope` | | `fullstack` | `backend`, `frontend`, or `fullstack` |
| `backend_language` | | `python` | `python` or `go` |
| `backend_framework` | | `fiber` | Go: `fiber`, `gin`, `gorilla`, `echo`, `chi` |
| `architecture_pattern` | | _(auto)_ | Forces a pattern: `microservices`, `hexagonal`, `monolith`, `layered`, `event_driven`, `serverless`, `cqrs` |

When `architecture_pattern` is not set, the decision engine selects the pattern based on the parsed requirements. When set, the decision engine is bypassed and the specified pattern is applied directly.

**Example response:**
```json
{
  "project_name": "order-service",
  "output_path": "/home/user/projects/order-service",
  "architecture_pattern": "MICROSERVICES",
  "files_written": 32,
  "files": ["go.mod", "cmd/server/main.go", "internal/app/server.go", "..."],
  "errors": [],
  "session_id": "..."
}
```

---

## GoAgent — 27 Skills

### Shared Skills (framework-agnostic)

| Skill | Generates |
|---|---|
| `go.setup_project` | `go.mod`, `main.go`, folder structure (`cmd/`, `internal/`, `pkg/`), DI bootstrap |
| `go.go_struct` | Domain structs + request/response DTOs with `json`, `validate`, `db` tags |
| `go.repository` | Repository interface + pgx/v5 PostgreSQL implementation |
| `go.service` | Service layer with business logic injected via repository interface |
| `go.docker_setup` | Multi-stage Dockerfile (builder → distroless) + `docker-compose.yml` |
| `go.test_suite` | testify/suite unit tests + mockery-generated mocks, table-driven patterns |
| `go.generate_migration` | SQL migration files (up/down) for golang-migrate + CLI runner |
| `go.config` | Config struct + viper loader for env/YAML |
| `go.logger` | Structured logging setup with uber-go/zap + request-scoped middleware |

### HTTP Framework Skills

| Framework | Skills |
|---|---|
| **Fiber v2** | `go.fiber_app`, `go.fiber_handler`, `go.fiber_routes`, `go.fiber_middleware` |
| **Gin** | `go.gin_app`, `go.gin_handler`, `go.gin_routes`, `go.gin_middleware` |
| **Gorilla Mux** | `go.gorilla_app`, `go.gorilla_handler`, `go.gorilla_routes` |
| **Echo v4** | `go.echo_app`, `go.echo_handler`, `go.echo_routes`, `go.echo_middleware` |
| **Chi v5** | `go.chi_app`, `go.chi_handler`, `go.chi_routes` |

### Go Stack

| Concern | Library |
|---|---|
| Database | `jackc/pgx/v5` |
| Validation | `go-playground/validator/v10` |
| Auth / JWT | `golang-jwt/jwt/v5` |
| Testing | `testify/suite` + `mockery` |
| Migrations | `golang-migrate/migrate/v4` |
| Config | `spf13/viper` |
| Logging | `uber-go/zap` |

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `HUGGINGFACE_TOKEN` | — | Hugging Face API token (Inference permission required) |
| `LLM_MODEL` | `Qwen/Qwen2.5-Coder-7B-Instruct` | Model used for code generation |
| `LLM_MAX_TOKENS` | `4096` | Maximum output tokens per request |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `API_HOST` | `0.0.0.0` | Server bind address |
| `API_PORT` | `3443` | Server port |

### Recommended Models

```
# Code-specialized
Qwen/Qwen2.5-Coder-7B-Instruct
deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
mistralai/Mistral-7B-Instruct-v0.3

# General purpose
meta-llama/Llama-3.1-8B-Instruct
microsoft/Phi-3.5-mini-instruct
```

---

## Project Structure

```
app/
├── agents/
│   ├── base.py                  # BaseAgent, AgentResult, AgentContext
│   ├── orchestrator.py          # AgentOrchestrator — BM25 routing + coordination
│   ├── go_agent.py              # GoAgent — 27 skills across 5 HTTP frameworks
│   ├── backend_agent.py         # Python/FastAPI specialist
│   ├── nextjs_agent.py          # Next.js App Router specialist
│   ├── design_agent.py          # UI/UX and design systems specialist
│   ├── frontend_agent.py        # React frontend patterns specialist
│   └── vercel_agent.py          # Vercel deployment specialist
├── skills/
│   ├── base.py                  # BaseSkill, SkillResult, CodeArtifact, SkillCategory
│   ├── registry.py              # SkillRegistry — @SkillRegistry.register decorator
│   ├── go/
│   │   ├── shared/              # setup_project, go_struct, repository, service, …
│   │   └── http/                # fiber, gin, gorilla, echo, chi
│   ├── backend/                 # fastapi_endpoint, sqlalchemy_model, …
│   ├── nextjs/                  # components, routing, data_fetching, auth, …
│   ├── design/                  # tailwind, shadcn, color_system, typography, …
│   ├── frontend/                # state_management, forms, i18n, performance, …
│   └── vercel/                  # deployment, environment, edge_config, analytics
├── architecture/
│   ├── agents/
│   │   ├── business_objective_parser.py
│   │   ├── decision_engine.py
│   │   ├── solution_flow_diagram.py
│   │   ├── validation_agent.py
│   │   └── system/              # hexagonal, microservices, monolith design partners
│   ├── context/
│   │   └── pipeline_context.py  # PipelineContext — shared state across pipeline
│   └── schemas/                 # requirements, solution, system_design, workflow
├── architecture/
│   └── workflow_coordinator.py  # End-to-end pipeline + code generation router
├── mcp/
│   ├── architecture_mcp.py      # MCP server: parse, clarify, decide, select_design_partner
│   ├── backend_mcp.py           # MCP server: Python/FastAPI skills
│   ├── frontend_mcp.py          # MCP server: Next.js + design skills
│   └── orchestrator_mcp.py     # MCP server: cross-agent orchestration
├── llm/
│   ├── base.py                  # BaseLLMProvider interface
│   ├── bm25_index.py            # SkillBM25Index — in-memory BM25 skill routing
│   ├── huggingface.py           # AsyncInferenceClient (REST, no local model)
│   └── prompts.py               # System prompts per agent
├── main.py                      # FastAPI app, all routes, CLI entry point
└── api/
```

---

## Adding a Skill

1. Create a file in the appropriate category directory under `app/skills/`.
2. Subclass `BaseSkill`, set class attributes, implement `execute()`.
3. Decorate with `@SkillRegistry.register`.
4. Import the module in the package `__init__.py`.

```python
from app.skills.base import BaseSkill, SkillCategory, SkillResult, SkillParameter, CodeArtifact
from app.skills.registry import SkillRegistry

@SkillRegistry.register
class MySkill(BaseSkill):
    name = "go.my_skill"
    description = "Generate a custom Go component"
    category = SkillCategory.GO
    tags = ["go", "custom"]
    parameters = [
        SkillParameter("resource", "Resource name"),
    ]

    async def execute(self, resource: str, **kwargs) -> SkillResult:
        code = f"package main\n\n// {resource} generated\n"
        return SkillResult(
            success=True,
            summary=f"Generated {resource}",
            artifacts=[CodeArtifact(f"{resource}.go", code, "go")],
        )
```

---

## Development

```bash
make test       # run all 323 tests
make lint       # ruff check
make format     # ruff format
```

---

## License

MIT
