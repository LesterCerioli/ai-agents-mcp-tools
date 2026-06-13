# Enterprise AI Agents & MCP Tools

An agentic backend platform that transforms natural-language instructions into production-ready code — either scaffolding new projects from scratch or improving existing ones. Specialized agents cover Go, Python/FastAPI, Next.js, design systems, and Vercel deployments, all coordinated through an architecture pipeline and exposed via a FastAPI REST API, a CLI, and MCP (Model Context Protocol) servers.

---

## End-to-End Flow

### `agents improve` — Improving an Existing Project

The primary flow for adding features or improvements to a project already on disk.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER'S MACHINE                                     │
│                                                                                 │
│  $ agents improve "Add a credit card payment gateway and an API gateway"        │
│                    --path /path/to/my-project                                   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  CLI  (app/cli/commands.py)                                              │  │
│  │                                                                          │  │
│  │  1. Project Scanner (app/cli/project_scanner.py)                        │  │
│  │     • Walks directory tree                                               │  │
│  │     • Skips: .git  node_modules  __pycache__  vendor                    │  │
│  │     • Reads files up to 10 KB each / 150 KB total                       │  │
│  │     • Detects project type from go.mod / package.json / requirements    │  │
│  │     → { files: [...], project_type: "go", file_count: 22 }              │  │
│  │                                                                          │  │
│  │  2. AgentsClient.improve()  (app/cli/client.py)                         │  │
│  │     POST /workflow/improve  →  instruction + project_files + type       │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                    │  HTTP                                      │
└────────────────────────────────────┼───────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────────────┐
│                              AGENTS API  (FastAPI)                              │
│                                                                                 │
│  /workflow/improve  (app/main.py)                                               │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  3. Orchestrator.plan()  — BM25 Skill Router                           │   │
│  │                                                                         │   │
│  │     "Add a credit card payment gateway and an API gateway in Go"        │   │
│  │      → BM25 index search (local, microseconds, zero LLM calls)         │   │
│  │      → [ go.service, go.repository, go.fiber_handler,                  │   │
│  │           go.fiber_routes, go.test_suite, go.docker_setup, … ]         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────▼───────────────────────────────────────┐   │
│  │  4. Dual LLM Param Extractor  (app/llm/dual_extractor.py)              │   │
│  │                                                                         │   │
│  │     For each planned skill, both models are called in parallel:         │   │
│  │                                                                         │   │
│  │     asyncio.gather(                                                     │   │
│  │       call(LLM_MODEL_1),   ◀──── meta-llama/Llama-3.1-8B-Instruct     │   │
│  │       call(LLM_MODEL_2),   ◀──── Qwen/Qwen2.5-Coder-7B-Instruct       │   │
│  │     )                             via HuggingFace Inference API         │   │
│  │                                                                         │   │
│  │     Each response is parsed with a resilient JSON extractor:            │   │
│  │       • Direct JSON parse                                               │   │
│  │       • Markdown code-block extraction  (```json ... ```)               │   │
│  │       • Regex fallback for any { } object in the text                  │   │
│  │                                                                         │   │
│  │     _score() compares responses:                                        │   │
│  │       • Counts required params filled with non-empty values             │   │
│  │       • Winner = higher coverage of required parameters                 │   │
│  │       → best_params = { "resource": "pagamento", "module": "..." }     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────▼───────────────────────────────────────┐   │
│  │  5. Fallback Param Extraction  (only if dual extractor returns empty)   │   │
│  │                                                                         │   │
│  │     _parse_go_context()  →  reads go.mod for module_name, framework    │   │
│  │     _fallback_params()   →  infers resource name from instruction text  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────▼───────────────────────────────────────┐   │
│  │  6. Agent.execute_skill(skill_name, **params)                           │   │
│  │                                                                         │   │
│  │     Go skills  →  template-based generation (fast, deterministic)       │   │
│  │     Next.js / Design / Frontend skills                                  │   │
│  │                  →  LLM code generation via HuggingFace                 │   │
│  │                                                                         │   │
│  │     Returns: [ CodeArtifact(filename, content, language), … ]          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  Response → { artifacts: [...], success: true, summary: "..." }                │
└────────────────────────────────────┬───────────────────────────────────────────┘
                                     │  HTTP response
┌────────────────────────────────────▼───────────────────────────────────────────┐
│                              USER'S MACHINE                                     │
│                                                                                 │
│  7. Platform Agent  (app/cli/platforms/linux.py | windows.py)                  │
│     • Receives artifacts from API response                                      │
│     • Resolves absolute paths relative to project root                         │
│     • Creates missing directories                                               │
│     • Writes each file to disk                                                  │
│                                                                                 │
│  8. Files land in the target repository                                         │
│                                                                                 │
│     /path/to/my-project/                                                        │
│     ├── internal/service/payment_gateway_service.go    ← NEW                   │
│     ├── internal/repository/payment_gateway_repo.go    ← NEW                   │
│     ├── internal/handler/payment_gateway_handler.go    ← NEW                   │
│     ├── internal/mocks/mock_payment_gateway_repo.go    ← NEW                   │
│     ├── internal/service/payment_gateway_test.go       ← NEW                   │
│     ├── Dockerfile                                     ← NEW                   │
│     └── docker-compose.yml                             ← NEW                   │
│                                                                                 │
│  ✓ Changes written to /path/to/my-project                                      │
│  13 files written                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### `agents generate` — Scaffolding a New Project from Scratch

```
$ agents generate "Go microservice for order management with Fiber, PostgreSQL, JWT"
                  --name order-service --language go --framework fiber

CLI → POST /workflow/scaffold
         │
         ▼
  Architecture Pipeline
  ┌─────────────────────────────────┐
  │ BusinessObjectiveParserAgent    │  — extracts 7 requirement dimensions
  │          ↓                      │
  │ SolutionArchitectureDecision    │  — selects pattern (microservices / hexagonal / …)
  │          ↓                      │
  │ SolutionFlowDiagramAgent        │
  │          ↓                      │
  │ ValidationAgent                 │
  │          ↓                      │
  │ DesignPartnerOrchestrator       │  — hexagonal / microservices / monolith partner
  └─────────────────────────────────┘
         │
         ▼
  Skill Generation (parallel)
  ┌──────────────────┬──────────────────────┐
  │  GoAgent         │  NextJSAgent          │
  │  BackendAgent    │  DesignAgent          │
  │  (27 Go skills)  │  FrontendAgent        │
  │                  │  VercelAgent          │
  └──────────────────┴──────────────────────┘
         │
         ▼
  Platform Agent writes every artifact to disk
  → /path/to/output/order-service/  (32+ files)
```

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

**Total: 93 registered skills.** All skills work in rule-based (template) mode without an LLM. When `HUGGINGFACE_TOKEN`, `LLM_MODEL_1`, and `LLM_MODEL_2` are configured, the dual extractor calls both models in parallel and picks the best parameter set for each skill.

---

## Intelligence Architecture

No model runs inside this application. All LLM inference is delegated to the **Hugging Face Inference API** over HTTP, making the service deployable on minimal infrastructure (0.5 CPU / 512 MB RAM):

```
This application                          Hugging Face Inference API
┌───────────────────────────────┐         ┌──────────────────────────────────────┐
│  FastAPI                      │         │  LLM_MODEL_1                         │
│  AgentOrchestrator            │──HTTP──▶│  meta-llama/Llama-3.1-8B-Instruct   │
│  Architecture Pipeline        │         │  (general purpose)                   │
│  93 Skills                    │         ├──────────────────────────────────────┤
│  BM25 Skill Router            │──HTTP──▶│  LLM_MODEL_2                         │
│  Dual LLM Extractor           │◀────────│  Qwen/Qwen2.5-Coder-7B-Instruct     │
└───────────────────────────────┘         │  (code specialized)                  │
  RAM: ~150–200 MB  |  LLM RAM: 0 (remote)└──────────────────────────────────────┘
```

### Skill Routing — BM25 (zero cost, zero API calls)

Skill selection uses an **in-memory BM25 index** built at startup from the `name + description + tags` of all 93 skills. No LLM call is needed to decide which skill to invoke.

```
"build a Go microservice with JWT auth"
  → BM25 search (local, microseconds)
  → go.fiber_handler (0.94), go.fiber_middleware (0.91), go.service (0.87), …
```

### Dual LLM Parameter Extraction

When the BM25 router selects a skill, both models are queried **in parallel** to extract the required parameters. The response with better coverage of required fields wins:

```
Instruction: "Add a payment gateway with credit card support"
Skill selected: go.service  →  requires: resource, module_name

asyncio.gather(
  LLM_MODEL_1  →  {"resource": "payment_gateway", "module_name": "github.com/org/api"}   score: 2
  LLM_MODEL_2  →  {"resource": "payment", "module_name": ""}                              score: 1
)

Winner: LLM_MODEL_1  →  params passed to skill execution
```

If both models fail (network error, invalid JSON, missing fields), the fallback extractor infers params from `go.mod` and the instruction text — ensuring the pipeline always produces output.

---

## CLI Reference

Install the CLI binary:

```bash
curl -fsSL https://ai-agents-mcp-tools.onrender.com/cli/install.sh | bash
```

### Generate a new project

```bash
agents generate "Go e-commerce API with Fiber, PostgreSQL, JWT auth, and clean architecture" \
  --name store-api \
  --language go \
  --framework fiber \
  --scope backend
```

| Flag | Default | Description |
|------|---------|-------------|
| `--name` / `-n` | required | Project name (becomes the directory) |
| `--language` / `-l` | `go` | `go` or `python` |
| `--framework` / `-f` | `fiber` | Go: `fiber` `gin` `gorilla` `echo` `chi` |
| `--scope` / `-s` | `backend` | `backend`, `frontend`, or `fullstack` |
| `--output` / `-o` | current dir | Output directory |

### Improve an existing project

```bash
agents improve "Add a credit card payment gateway and an API gateway for centralizing routes" \
  --path /path/to/existing-project
```

| Flag | Default | Description |
|------|---------|-------------|
| `--path` / `-p` | current dir | Path to the project to improve |
| `--output` / `-o` | project path | Where to write the generated files |

The CLI scans the project structure locally (detecting Go, Next.js, Python, or Rust projects), sends the file tree to the API, and writes the generated files back to disk — no manual file copying required.

### Other commands

```bash
agents list-skills             # list all 93 skills
agents list-skills --agent go  # filter by agent
agents version                 # CLI version + API status
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
# Edit .env — set HUGGINGFACE_TOKEN, LLM_MODEL_1, LLM_MODEL_2
```

---

## Running

### Development

```bash
make dev      # hot-reload on port 3030
make run      # without reload
make stop     # kill the process
make test     # full test suite
make lint     # ruff linter
```

API: `http://localhost:3030`  
Interactive docs: `http://localhost:3030/docs`

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 3030
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

### Execute a Skill Directly

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

### Improve an Existing Project

```http
POST /workflow/improve
{
  "instruction": "Add a credit card payment gateway and an API gateway",
  "project_type": "go",
  "project_files": [
    { "path": "go.mod", "content": "module github.com/org/pizza-api\n..." },
    { "path": "internal/domain/pagamento.go", "content": "..." }
  ]
}
```

### Full Project Scaffold

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

### Architecture Pipeline

```http
POST /architecture/parse
{ "objective": "Build a HIPAA-compliant telemedicine platform for 10,000 concurrent patients" }
```

```http
POST /architecture/clarify
{ "session_id": "<id>", "answer": "We need 99.9% uptime and plan to grow to 1M users in 2 years." }
```

---

## MCP Servers

Four MCP (Model Context Protocol) SSE servers are mounted and can be consumed by any MCP-compatible client (Claude Desktop, custom agents):

| Mount path | Purpose |
|---|---|
| `/mcp/architecture` | Pipeline tools: parse, clarify, decide, select design partner |
| `/mcp/backend` | Python/FastAPI skill execution |
| `/mcp/frontend` | Next.js + design skill execution |
| `/mcp/orchestrate` | Cross-agent orchestration |

---

## Architecture Pipeline (detailed)

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
| `LLM_MODEL_1` | `meta-llama/Llama-3.1-8B-Instruct` | General-purpose model — used in dual extraction |
| `LLM_MODEL_2` | `Qwen/Qwen2.5-Coder-7B-Instruct` | Code-specialized model — used in dual extraction |
| `LLM_MAX_TOKENS` | `4096` | Maximum output tokens per request |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `API_HOST` | `0.0.0.0` | Server bind address |
| `API_PORT` | `3030` | Server port |
| `API_BASE_URL` | — | Public URL of this service (injected into the CLI install script) |
| `AGENTS_API_URL` | — | URL the CLI binary uses to reach the API |

### Recommended Models

```
# Code-specialized (LLM_MODEL_2)
Qwen/Qwen2.5-Coder-7B-Instruct
deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
codellama/CodeLlama-13b-Instruct-hf

# General purpose (LLM_MODEL_1)
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
│   ├── schemas/                 # requirements, solution, system_design, workflow
│   └── workflow_coordinator.py  # End-to-end pipeline + code generation router
├── cli/
│   ├── commands.py              # Typer CLI — generate, improve, list-skills, version
│   ├── client.py                # AgentsClient — HTTP client for the API
│   ├── project_scanner.py       # Scans existing projects, detects type, reads files
│   └── platforms/
│       ├── linux.py             # LinuxPlatformAgent — file writing, path resolution
│       └── windows.py           # WindowsPlatformAgent
├── llm/
│   ├── base.py                  # BaseLLMProvider interface
│   ├── bm25_index.py            # SkillBM25Index — in-memory BM25 skill routing
│   ├── huggingface.py           # AsyncInferenceClient (REST, no local model)
│   ├── dual_extractor.py        # Dual LLM param extraction — parallel + scoring
│   └── prompts.py               # System prompts per agent
├── mcp/
│   ├── architecture_mcp.py      # MCP server: parse, clarify, decide, select_design_partner
│   ├── backend_mcp.py           # MCP server: Python/FastAPI skills
│   ├── frontend_mcp.py          # MCP server: Next.js + design skills
│   └── orchestrator_mcp.py      # MCP server: cross-agent orchestration
└── main.py                      # FastAPI app, all routes, lifespan
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
make test       # run all tests
make lint       # ruff check
make format     # ruff format
```

---

## License

MIT
