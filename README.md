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

## License

MIT
