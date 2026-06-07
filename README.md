# Enterprise AI Agents

AI agents with specialized Next.js, Design, and Frontend skills, powered by open-source HuggingFace LLMs and exposed via a FastAPI REST API.

## Overview

Four specialized agents collaborate through an orchestrator to handle complex frontend development tasks:

| Agent | Skills | Focus |
|-------|--------|-------|
| `nextjs` | 25 | App Router, API routes, server actions, layouts, data fetching |
| `design` | 17 | UI components, design systems, dark mode, accessibility |
| `frontend` | 13 | State management, hooks, forms, animations, performance |
| `vercel` | 5 | Deployment, environment config, edge functions |

Skills run with or without an LLM — when no token is provided, they return structured template-based output.

---

## Routing & Intelligence Architecture

### Where the Intelligence Lives

The application runs on Render's free tier (0.5 CPU / 512 MB RAM). No language model runs inside the application. All LLM inference is delegated to the **HuggingFace Inference API** via HTTP:

```
Render (this application)            HuggingFace (their infrastructure)
┌─────────────────────────┐          ┌──────────────────────────────────┐
│  FastAPI                │          │  Qwen2.5-Coder-7B-Instruct       │
│  AgentOrchestrator      │──HTTP───▶│  (7B parameters)                 │
│  Specialized Agents     │◀─────────│  running on their GPU servers    │
│  Skills (58 total)      │          └──────────────────────────────────┘
│  BM25 Index (~50 KB)    │
└─────────────────────────┘
  RAM used: ~150–200 MB
  LLM RAM:  0 (remote)
```

The `AsyncInferenceClient` from `huggingface-hub` acts as a pure HTTP client — it sends prompts and receives generated code. The `HUGGINGFACE_TOKEN` environment variable is the only credential required.

---

### Skill Routing: BM25 (Zero Cost, Zero API Calls)

Skill selection is handled by an **in-memory BM25 index** built at startup from the `name + description + tags` of all 58 registered skills. No LLM call is needed to decide which skill to invoke.

```
Startup
  SkillBM25Index.build()
    → tokenizes name + description + tags for each of the 58 skills
    → builds BM25Okapi corpus in memory (~50 KB)

Request: "create a dashboard with authentication"
  SkillBM25Index.search(query, top_k=5)
    → BM25 keyword scoring (local, microseconds)
    → returns: [nextjs.auth (0.94), nextjs.generate_component (0.88), ...]
    → no API call, no cost, deterministic
```

This design eliminates two problems with LLM-based routing:
- **Hallucination** — the LLM could return a skill name that does not exist.
- **Cost** — every routing decision would consume an API call before the actual code generation.

---

### Full Request Flow

A complete orchestrated request goes through two distinct stages:

```
POST /orchestrate  { "task": "Build a SaaS dashboard with auth and dark mode" }

  Stage 1 — Skill Routing (BM25, local, free)
  ┌──────────────────────────────────────────────┐
  │  BM25Index.search("SaaS dashboard auth ...")  │
  │  → nextjs.auth          score: 0.94           │
  │  → nextjs.generate_component  score: 0.88     │
  │  → design.color_system  score: 0.71           │
  └──────────────────────────────────────────────┘
              ↓

  Stage 2 — Code Generation (HuggingFace API, per skill)
  ┌──────────────────────────────────────────────┐
  │  For each matched skill:                      │
  │    LLM.generate_code(skill_prompt)            │
  │    → HTTP POST to HuggingFace Inference API   │
  │    → returns production-ready TypeScript/TSX  │
  └──────────────────────────────────────────────┘
              ↓

  Response: { artifacts: [...], dependencies: [...] }
```

| Stage | Technology | LLM calls | Cost |
|---|---|---|---|
| Skill routing | BM25 (local) | 0 | free |
| Param extraction | HuggingFace API | 1 (small prompt) | API token |
| Code generation | HuggingFace API | 1 per skill | API token |

---

### No-Token Mode

All 58 skills include a hardcoded fallback template. When `HUGGINGFACE_TOKEN` is not set, the system still functions — routing works identically via BM25, and each skill returns a valid but generic scaffold:

```
With token     → contextual, production-ready code tailored to the task
Without token  → generic template scaffold (compilable, not contextual)
```

---

## Requirements

- Python 3.12+
- HuggingFace account (free token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens))

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd agents

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# Edit .env and set HUGGINGFACE_TOKEN
```

## Running the API

```bash
# Using the installed CLI entry point
agents

# Or directly with uvicorn
uvicorn src.api.main:app --reload --port 4250
```

The API starts at `http://localhost:4250`. Interactive docs at `http://localhost:4250/docs`.

## API Endpoints

### Health

```
GET /          — service status
GET /health    — health check with skill count and LLM status
```

### Agents & Skills

```
GET  /agents              — list all agents
GET  /skills              — list all skills
GET  /skills?agent=nextjs — skills for a specific agent
GET  /skills?category=design
GET  /skills?tag=auth
```

### Execution

**Execute a specific skill directly:**

```
POST /skills/execute
{
  "agent": "nextjs",
  "skill": "create_page",
  "params": {
    "name": "Dashboard",
    "route": "/dashboard"
  }
}
```

**Orchestrate a complex multi-agent task:**

```
POST /orchestrate
{
  "task": "Create a SaaS dashboard with auth, dark mode, and data tables"
}
```

**Generate a plan without executing:**

```
POST /plan
{
  "task": "Build a user profile page with avatar upload"
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HUGGINGFACE_TOKEN` | — | HuggingFace API token |
| `LLM_MODEL` | `Qwen/Qwen2.5-Coder-7B-Instruct` | Model to use |
| `LLM_MAX_TOKENS` | `4096` | Max output tokens |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `API_HOST` | `0.0.0.0` | Server bind address |
| `API_PORT` | `4250` | Server port |
| `API_DEBUG` | `true` | Enable auto-reload |

### Recommended models

```
# Code-specialized (best for dev agents)
Qwen/Qwen2.5-Coder-7B-Instruct
deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct
codellama/CodeLlama-13b-Instruct-hf

# General purpose
meta-llama/Llama-3.1-8B-Instruct
microsoft/Phi-3.5-mini-instruct
mistralai/Mistral-7B-Instruct-v0.3
```

## Project Structure

```
src/
├── agents/
│   ├── base.py           # BaseAgent ABC, AgentResult, AgentContext
│   ├── orchestrator.py   # AgentOrchestrator — routes and coordinates agents
│   ├── nextjs_agent.py   # Next.js App Router specialist
│   ├── design_agent.py   # UI/UX and design systems specialist
│   ├── frontend_agent.py # React frontend patterns specialist
│   └── vercel_agent.py   # Vercel deployment specialist
├── skills/
│   ├── base.py           # BaseSkill ABC, SkillResult, CodeArtifact
│   └── registry.py       # SkillRegistry — @SkillRegistry.register decorator
├── llm/
│   ├── base.py           # BaseLLMProvider interface
│   ├── bm25_index.py     # SkillBM25Index — in-memory BM25 skill routing
│   ├── huggingface.py    # HuggingFace InferenceClient implementation
│   └── prompts.py        # System prompts for each agent type
└── api/
    └── main.py           # FastAPI app, routes, CLI entry point
```

## Adding a Skill

1. Create a skill file in the appropriate category directory.
2. Subclass `BaseSkill`, set class attributes, implement `execute`.
3. Decorate with `@SkillRegistry.register`.
4. Import the module in the package `__init__.py`.

```python
from src.skills.base import BaseSkill, SkillCategory, SkillResult, SkillParameter
from src.skills.registry import SkillRegistry

@SkillRegistry.register
class CreateLayoutSkill(BaseSkill):
    name = "create_layout"
    description = "Generate a Next.js layout component"
    category = SkillCategory.NEXTJS
    tags = ["layout", "app-router"]
    parameters = [
        SkillParameter(name="name", description="Layout name", type="string"),
    ]

    async def execute(self, name: str, **kwargs) -> SkillResult:
        # generate code, optionally calling self.llm.chat(...)
        ...
```

## File Naming Conventions

Skills enforce Next.js App Router conventions:

| File type | Pattern | Language |
|-----------|---------|----------|
| API routes | `src/app/api/{name}/route.js` | JavaScript |
| Components | `{Name}.tsx` | TypeScript |
| Pages | `page.tsx`, `layout.tsx` | TypeScript |
| Styles | `{name}.styles.ts` | TypeScript |
| Services | `src/services/{name}.ts` | TypeScript |
| Server actions | `src/actions/{name}.ts` | TypeScript |
| Hooks / utils / types | `*.ts` | TypeScript |

## Development

```bash
# Lint
ruff check src/

# Type check
mypy src/

# Tests
pytest
```

---

## Solution Architecture Pipeline

The system includes a second layer of agents focused on **architecture design automation**. This pipeline receives natural language business objectives and transforms them into structured architecture requirement sets that drive downstream design partner agents.

### Pipeline Overview

```text
[User: Natural Language Business Objective]
        ↓
[BusinessObjectiveParserAgent]  ← Feature #7 (implemented)
  - Extracts 7 requirement dimensions
  - Assigns confidence scores (0.0–1.0)
  - Generates clarification questions for gaps
  - Supports multi-turn clarification sessions
        ↓
[PipelineContext]  — shared context object
  - Stores ArchitectureRequirements
  - Tracks conversation history
  - Signals readiness for next pipeline stage
        ↓
[Next stages — Tasks 2–5 from EPIC #1]
  - Solution Architecture Decision Engine
  - System Architecture Design Partners
  - SOLID/Pattern Enforcement
  - MCP Orchestration & REST output
```

### Requirement Dimensions Extracted

| Dimension | Examples |
|-----------|---------|
| `scalability` | expected users, peak load, growth rate |
| `availability` | target uptime (SLA), RTO, RPO |
| `compliance` | GDPR, HIPAA, SOC2, PCI-DSS, ISO 27001, FERPA… |
| `domain_boundaries` | e-commerce, fintech, healthcare, SaaS, IoT, logistics… |
| `integration` | external systems (Stripe, Kafka…), REST/gRPC/WebSocket patterns |
| `budget` | tier (startup/mid-market/enterprise), cloud preference, cost sensitivity |
| `team_size` | engineering headcount range, organizational maturity |

Each dimension carries a `confidence` score (0.0–1.0). Dimensions with low confidence generate targeted clarification questions.

### Solution Architecture Endpoints

```json
POST /architecture/parse
{
  "objective": "Build a HIPAA-compliant telemedicine platform for 10,000 concurrent patients",
  "session_id": null
}
→ {
  "session_id": "...",
  "requirements": { "scalability": {...}, "compliance": {...}, ... },
  "overall_confidence": 0.72,
  "is_complete": true,
  "clarification_questions": []
}
```

```json
POST /architecture/clarify
{
  "session_id": "...",
  "answer": "We need 99.9% uptime and plan to grow to 1 million users in 2 years."
}
→ { "session_id": "...", "requirements": {...}, "overall_confidence": 0.84, ... }
```

```json
GET /architecture/sessions/{session_id}
→ { "session_id": "...", "turn_count": 3, "is_ready_for_next_stage": true, "requirements": {...} }
```

### Architecture Module Structure

```text
src/architecture/
├── schemas/
│   └── requirements.py       # ArchitectureRequirements + 7 dimension Pydantic models
├── context/
│   └── pipeline_context.py   # PipelineContext — shared state across pipeline agents
└── agents/
    ├── base.py                # BaseArchitectureAgent ABC
    ├── business_objective_parser.py  # BusinessObjectiveParserAgent (parse + clarify)
    └── extraction/
        ├── keyword_extractor.py  # Rule-based extraction (LLM fallback)
        └── clarification.py      # ClarificationEngine — generates targeted questions

tests/architecture/
└── test_business_objective_parser.py  # 71 tests across 12 scenarios
```

### Running the Tests

```bash
pytest tests/architecture/ -v
```

## License

MIT
