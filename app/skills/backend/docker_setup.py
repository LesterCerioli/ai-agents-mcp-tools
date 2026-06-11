from typing import Any

from ..base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from ..registry import SkillRegistry


@SkillRegistry.register
class GenerateDockerSetupSkill(BaseSkill):
    name = "backend.docker_setup"
    description = (
        "Generate a production-ready multi-stage Dockerfile and docker-compose.yml "
        "for a FastAPI application with optional database, Redis, and monitoring services."
    )
    category = SkillCategory.BACKEND
    tags = ["docker", "dockerfile", "docker-compose", "deployment", "devops", "container"]
    parameters = [
        SkillParameter("app_name", "Application name used in image tags and service names"),
        SkillParameter(
            "python_version",
            "Python version for the base image",
            required=False,
            default="3.12",
        ),
        SkillParameter(
            "services",
            "Comma-separated additional services (postgres, redis, celery, prometheus, grafana)",
            required=False,
            default="postgres",
        ),
        SkillParameter(
            "port",
            "Port the FastAPI app listens on",
            required=False,
            default="8000",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_name: str,
        python_version: str = "3.12",
        services: str = "postgres",
        port: str = "8000",
        **_: Any,
    ) -> SkillResult:
        svc_list = {s.strip().lower() for s in services.split(",") if s.strip()}
        app = app_name.lower().replace(" ", "-")

        dockerfile = (
            f"# ── Build stage ───────────────────────────────────────────────────────────\n"
            f"FROM python:{python_version}-slim AS builder\n\n"
            f"WORKDIR /app\n\n"
            f"RUN pip install --upgrade pip && pip install hatchling\n\n"
            f"COPY pyproject.toml ./\n"
            f"RUN pip install --no-cache-dir .\n\n"
            f"# ── Runtime stage ─────────────────────────────────────────────────────────\n"
            f"FROM python:{python_version}-slim AS runtime\n\n"
            f"WORKDIR /app\n\n"
            f"RUN addgroup --system app && adduser --system --group app\n\n"
            f"COPY --from=builder /usr/local/lib/python{python_version}/site-packages /usr/local/lib/python{python_version}/site-packages\n"
            f"COPY --from=builder /usr/local/bin /usr/local/bin\n"
            f"COPY . .\n\n"
            f"RUN chown -R app:app /app\n"
            f"USER app\n\n"
            f"EXPOSE {port}\n\n"
            f'CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "{port}"]\n'
        )

        compose_services: list[str] = []

        compose_services.append(
            f"  {app}:\n"
            f"    build: .\n"
            f"    image: {app}:latest\n"
            f"    ports:\n"
            f'      - "{port}:{port}"\n'
            f"    environment:\n"
            f"      - DATABASE_URL=${{DATABASE_URL}}\n"
            f"      - REDIS_URL=${{REDIS_URL:-}}\n"
            f"    env_file:\n"
            f"      - .env\n"
            f"    restart: unless-stopped\n"
            f"    depends_on:\n"
            + ("      - postgres\n" if "postgres" in svc_list else "")
            + ("      - redis\n" if "redis" in svc_list else "")
        )

        if "postgres" in svc_list:
            compose_services.append(
                "  postgres:\n"
                "    image: postgres:16-alpine\n"
                "    environment:\n"
                "      POSTGRES_USER: ${POSTGRES_USER:-app}\n"
                "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-secret}\n"
                "      POSTGRES_DB: ${POSTGRES_DB:-appdb}\n"
                "    ports:\n"
                '      - "5432:5432"\n'
                "    volumes:\n"
                "      - postgres_data:/var/lib/postgresql/data\n"
                "    restart: unless-stopped\n"
            )

        if "redis" in svc_list:
            compose_services.append(
                "  redis:\n"
                "    image: redis:7-alpine\n"
                "    ports:\n"
                '      - "6379:6379"\n'
                "    restart: unless-stopped\n"
            )

        if "celery" in svc_list:
            compose_services.append(
                f"  celery_worker:\n"
                f"    build: .\n"
                f"    command: celery -A src.worker worker --loglevel=info\n"
                f"    environment:\n"
                f"      - DATABASE_URL=${{DATABASE_URL}}\n"
                f"      - REDIS_URL=${{REDIS_URL}}\n"
                f"    depends_on:\n"
                f"      - redis\n"
                f"    restart: unless-stopped\n"
            )

        if "prometheus" in svc_list:
            compose_services.append(
                "  prometheus:\n"
                "    image: prom/prometheus:latest\n"
                "    ports:\n"
                '      - "9090:9090"\n'
                "    volumes:\n"
                "      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml\n"
                "    restart: unless-stopped\n"
            )

        volumes: list[str] = []
        if "postgres" in svc_list:
            volumes.append("  postgres_data:")

        services_block = "\n".join(compose_services)
        volumes_block = ("\nvolumes:\n" + "\n".join(volumes)) if volumes else ""

        compose = (
            f"version: '3.9'\n\n"
            f"services:\n"
            f"{services_block}"
            f"{volumes_block}\n"
        )

        env_example = (
            f"# Application\n"
            f"APP_ENV=development\n"
            f"SECRET_KEY=change-me-in-production\n\n"
            + (
                f"# Database\n"
                f"DATABASE_URL=postgresql+asyncpg://app:secret@postgres:5432/appdb\n"
                f"POSTGRES_USER=app\n"
                f"POSTGRES_PASSWORD=secret\n"
                f"POSTGRES_DB=appdb\n\n"
                if "postgres" in svc_list
                else ""
            )
            + (
                f"# Redis\n"
                f"REDIS_URL=redis://redis:6379/0\n\n"
                if "redis" in svc_list
                else ""
            )
        )

        artifacts = [
            CodeArtifact(filename="Dockerfile", content=dockerfile, language="dockerfile"),
            CodeArtifact(filename="docker-compose.yml", content=compose, language="yaml"),
            CodeArtifact(filename=".env.example", content=env_example, language="dotenv"),
        ]

        return SkillResult(
            success=True,
            summary=f"Generated Docker setup for `{app_name}` with services: {', '.join(sorted(svc_list)) or 'app only'}",
            artifacts=artifacts,
            instructions=[
                "cp .env.example .env && edit .env with your secrets",
                "docker compose up --build -d",
                f"API available at http://localhost:{port}",
                f"Docs at http://localhost:{port}/docs",
            ],
            next_steps=[
                "Configure CI/CD to build and push Docker image",
                "Add health check endpoint at /health for container orchestration",
            ],
        )
