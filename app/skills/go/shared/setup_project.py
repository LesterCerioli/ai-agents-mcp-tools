from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoSetupProjectSkill(BaseSkill):
    name = "go.setup_project"
    description = (
        "Generate Go 1.24 project scaffold: go.mod, main.go, folder structure "
        "(cmd/, internal/, pkg/), and dependency injection bootstrap."
    )
    category = SkillCategory.GO
    tags = ["go", "setup", "scaffold", "project", "module", "bootstrap"]
    parameters = [
        SkillParameter("module_name", "Go module name (e.g. github.com/org/my-service)"),
        SkillParameter("app_name", "Application name used for the binary and package names"),
        SkillParameter(
            "framework",
            "HTTP framework to use",
            required=False,
            default="fiber",
            enum=["fiber", "gin", "gorilla", "echo", "chi"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        module_name: str,
        app_name: str,
        framework: str = "fiber",
        **_: Any,
    ) -> SkillResult:
        app = app_name.lower().replace("-", "_").replace(" ", "_")

        go_mod = (
            f"module {module_name}\n\n"
            "go 1.24\n\n"
            "require (\n"
            + self._framework_require(framework)
            + "\tgithub.com/jackc/pgx/v5 v5.7.2\n"
            "\tgithub.com/spf13/viper v1.19.0\n"
            "\tgithub.com/go-playground/validator/v10 v10.22.1\n"
            "\tgithub.com/golang-jwt/jwt/v5 v5.2.1\n"
            "\tgo.uber.org/zap v1.27.0\n"
            "\tgithub.com/golang-migrate/migrate/v4 v4.18.1\n"
            "\tgithub.com/stretchr/testify v1.9.0\n"
            ")\n"
        )

        main_go = (
            "package main\n\n"
            "import (\n"
            f'\t"{module_name}/internal/app"\n'
            '\t"log"\n'
            ")\n\n"
            "func main() {\n"
            "\tif err := app.Run(); err != nil {\n"
            '\t\tlog.Fatalf("application error: %v", err)\n'
            "\t}\n"
            "}\n"
        )

        app_bootstrap = (
            "package app\n\n"
            "import (\n"
            '\t"context"\n'
            '\t"fmt"\n'
            '\t"os/signal"\n'
            '\t"syscall"\n'
            ")\n\n"
            "func Run() error {\n"
            "\tctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)\n"
            "\tdefer stop()\n\n"
            "\tserver, err := NewServer()\n"
            "\tif err != nil {\n"
            '\t\treturn fmt.Errorf("init server: %w", err)\n'
            "\t}\n\n"
            "\treturn server.Start(ctx)\n"
            "}\n"
        )

        wire_go = (
            "package app\n\n"
            "// NewServer wires all dependencies together.\n"
            "// Replace with wire/fx if the project grows.\n"
            "func NewServer() (*Server, error) {\n"
            "\tcfg, err := LoadConfig()\n"
            "\tif err != nil {\n"
            '\t\treturn nil, err\n'
            "\t}\n"
            "\tlogger := NewLogger(cfg.LogLevel)\n"
            "\treturn &Server{cfg: cfg, logger: logger}, nil\n"
            "}\n"
        )

        makefile = (
            ".PHONY: run build test migrate\n\n"
            f"BINARY := {app}\n\n"
            "run:\n"
            "\tgo run ./cmd/...\n\n"
            "build:\n"
            f"\tgo build -o bin/$(BINARY) ./cmd/...\n\n"
            "test:\n"
            "\tgo test ./... -race -cover\n\n"
            "lint:\n"
            "\tgolangci-lint run ./...\n\n"
            "migrate-up:\n"
            "\tgo run ./cmd/migrate up\n\n"
            "migrate-down:\n"
            "\tgo run ./cmd/migrate down\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Go 1.24 project scaffold for `{module_name}` using {framework}",
            artifacts=[
                CodeArtifact("go.mod", go_mod, "go", "Go module file"),
                CodeArtifact("cmd/server/main.go", main_go, "go", "Entry point"),
                CodeArtifact("internal/app/app.go", app_bootstrap, "go", "Application bootstrap"),
                CodeArtifact("internal/app/wire.go", wire_go, "go", "Dependency injection wiring"),
                CodeArtifact("Makefile", makefile, "makefile", "Build commands"),
            ],
            dependencies=[
                f"github.com/jackc/pgx/v5",
                "github.com/spf13/viper",
                "github.com/go-playground/validator/v10",
                "github.com/golang-jwt/jwt/v5",
                "go.uber.org/zap",
            ],
            instructions=[
                "Run `go mod tidy` after adding framework dependencies",
                "Set DATABASE_URL and APP_PORT in .env",
                "Use `make run` to start the server",
            ],
            next_steps=[
                f"go.{framework}_app app_name={app_name}",
                "go.config app_name=" + app_name,
                "go.logger",
            ],
        )

    def _framework_require(self, framework: str) -> str:
        mapping = {
            "fiber": "\tgithub.com/gofiber/fiber/v2 v2.52.5\n",
            "gin": "\tgithub.com/gin-gonic/gin v1.10.0\n",
            "gorilla": "\tgithub.com/gorilla/mux v1.8.1\n",
            "echo": "\tgithub.com/labstack/echo/v4 v4.12.0\n",
            "chi": "\tgithub.com/go-chi/chi/v5 v5.1.0\n",
        }
        return mapping.get(framework, "\tgithub.com/gofiber/fiber/v2 v2.52.5\n")
