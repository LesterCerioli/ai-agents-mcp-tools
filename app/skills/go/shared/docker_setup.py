from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoDockerSetupSkill(BaseSkill):
    name = "go.docker_setup"
    description = (
        "Generate a multi-stage Dockerfile (builder → distroless) and "
        "docker-compose.yml for the Go service with PostgreSQL and Redis."
    )
    category = SkillCategory.GO
    tags = ["go", "docker", "dockerfile", "docker-compose", "postgres", "redis", "devops"]
    parameters = [
        SkillParameter("app_name", "Application binary name"),
        SkillParameter(
            "services",
            "Comma-separated extra services to include (postgres,redis)",
            required=False,
            default="postgres",
        ),
        SkillParameter("port", "Port the application listens on", required=False, default="8080"),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_name: str,
        services: str = "postgres",
        port: str = "8080",
        **_: Any,
    ) -> SkillResult:
        app = app_name.lower().replace("-", "_").replace(" ", "_")
        svc_list = [s.strip() for s in services.split(",")]

        dockerfile = (
            "# ── Build stage ──────────────────────────────────────────────────────────────\n"
            "FROM golang:1.24-alpine AS builder\n\n"
            "WORKDIR /app\n"
            "COPY go.mod go.sum ./\n"
            "RUN go mod download\n"
            "COPY . .\n"
            f"RUN CGO_ENABLED=0 GOOS=linux go build -ldflags='-s -w' -o /bin/{app} ./cmd/server\n\n"
            "# ── Final stage ──────────────────────────────────────────────────────────────\n"
            "FROM gcr.io/distroless/static-debian12\n\n"
            f"COPY --from=builder /bin/{app} /{app}\n"
            f'EXPOSE {port}\n'
            f'ENTRYPOINT ["/{app}"]\n'
        )

        compose_services = {
            "app": (
                "  app:\n"
                "    build: .\n"
                f"    ports:\n"
                f"      - \"{port}:{port}\"\n"
                "    environment:\n"
                "      - DATABASE_URL=postgres://postgres:postgres@postgres:5432/app?sslmode=disable\n"
                "      - APP_PORT=" + port + "\n"
                "    depends_on:\n"
                "      postgres:\n"
                "        condition: service_healthy\n"
            )
        }

        if "postgres" in svc_list:
            compose_services["postgres"] = (
                "  postgres:\n"
                "    image: postgres:16-alpine\n"
                "    environment:\n"
                "      POSTGRES_USER: postgres\n"
                "      POSTGRES_PASSWORD: postgres\n"
                "      POSTGRES_DB: app\n"
                "    ports:\n"
                "      - \"5432:5432\"\n"
                "    volumes:\n"
                "      - postgres_data:/var/lib/postgresql/data\n"
                "    healthcheck:\n"
                "      test: [\"CMD-SHELL\", \"pg_isready -U postgres\"]\n"
                "      interval: 5s\n"
                "      timeout: 5s\n"
                "      retries: 5\n"
            )

        if "redis" in svc_list:
            compose_services["redis"] = (
                "  redis:\n"
                "    image: redis:7-alpine\n"
                "    ports:\n"
                "      - \"6379:6379\"\n"
                "    healthcheck:\n"
                "      test: [\"CMD\", \"redis-cli\", \"ping\"]\n"
                "      interval: 5s\n"
                "      timeout: 5s\n"
                "      retries: 5\n"
            )

        volumes_section = ""
        if "postgres" in svc_list:
            volumes_section = "\nvolumes:\n  postgres_data:\n"

        compose_body = "\n".join(compose_services.values())

        docker_compose = (
            "version: '3.9'\n\n"
            "services:\n"
            f"{compose_body}"
            f"{volumes_section}"
        )

        dockerignore = (
            ".git\n"
            ".gitignore\n"
            "*.md\n"
            "bin/\n"
            "tmp/\n"
            ".env\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated multi-stage Dockerfile and docker-compose.yml for `{app_name}`",
            artifacts=[
                CodeArtifact("Dockerfile", dockerfile, "dockerfile", "Multi-stage Docker build"),
                CodeArtifact("docker-compose.yml", docker_compose, "yaml", "Development compose stack"),
                CodeArtifact(".dockerignore", dockerignore, "text", "Docker build context exclusions"),
            ],
            instructions=[
                f"Run with: docker-compose up --build",
                f"The app binary is built as /{app} in the distroless image",
                "Configure .env for local development; docker-compose reads the environment section",
            ],
            next_steps=["go.generate_migration"],
        )
