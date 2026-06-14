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
            "go 1.26\n\n"
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


@SkillRegistry.register
class GoFiberFullProjectSkill(BaseSkill):
    """Complete Medical-App-Core style Go project scaffold.

    Generates the full project skeleton with the GORM + Fiber + Swagger + godotenv
    stack used in production — including the centralised initializers init sequence
    in cmd/main.go and a ready-to-use .env.example.
    """

    name = "go.fiber_full_project"
    description = (
        "Generate a complete Fiber v2 + GORM + PostgreSQL + Swagger project scaffold "
        "following the Medical-App-Core pattern: go.mod with production dependencies, "
        "cmd/main.go with centralised initializer sequence "
        "(godotenv → InitialDB → RunMigrations → InitServices → Fiber → Swagger → routes → Listen), "
        ".env.example, and Makefile. "
        "Use go.initializers to generate the initializers/ package afterwards."
    )
    category = SkillCategory.GO
    tags = [
        "go", "fiber", "gorm", "postgres", "swagger", "scaffold",
        "template", "full-stack", "bootstrap", "godotenv", "jwt",
    ]
    parameters = [
        SkillParameter("module_name", "Go module name (e.g. github.com/org/medical-api)"),
        SkillParameter("app_name", "Application name (used in Fiber config and Swagger title)"),
        SkillParameter(
            "resource",
            "Primary resource name to wire in initializeRoutes (e.g. bank, patient, user). "
            "Used to generate the controller instantiation and route group.",
            required=False,
            default="",
        ),
        SkillParameter("port", "Default HTTP port", required=False, default="3040"),
        SkillParameter(
            "go_version",
            "Go toolchain version",
            required=False,
            default="1.26",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        module_name: str,
        app_name: str,
        resource: str = "",
        port: str = "3040",
        go_version: str = "1.26",
        **_: Any,
    ) -> SkillResult:
        app = app_name.lower().replace(" ", "-").replace("_", "-")

        go_mod = self._go_mod(module_name, go_version)
        main_go = self._main_go(module_name, app_name, port, resource)
        env_example = self._env_example(port)
        makefile = self._makefile(app)

        return SkillResult(
            success=True,
            summary=(
                f"Generated Medical-App-Core style scaffold for `{module_name}` "
                f"({app_name}) — Fiber v2 + GORM + PostgreSQL + Swagger"
            ),
            artifacts=[
                CodeArtifact("go.mod", go_mod, "go", "Go module with full Medical-App-Core dependency stack"),
                CodeArtifact("cmd/main.go", main_go, "go", "Entry point with centralised init sequence"),
                CodeArtifact(".env.example", env_example, "text", "Environment variable template"),
                CodeArtifact("Makefile", makefile, "makefile", "Build, run, test, and swagger commands"),
            ],
            dependencies=[
                "github.com/gofiber/fiber/v2",
                "github.com/gofiber/swagger",
                "gorm.io/gorm",
                "gorm.io/driver/postgres",
                "github.com/golang-jwt/jwt/v4",
                "github.com/swaggo/swag",
                "github.com/google/uuid",
                "github.com/joho/godotenv",
                "github.com/go-playground/validator/v10",
            ],
            instructions=[
                "Run `go mod tidy` to download all dependencies",
                "Copy .env.example to .env and fill in your values",
                "Run `go.initializers` skill to generate the initializers/ package",
                "Run `swag init -g cmd/main.go -o docs` to generate Swagger docs",
                "Use `make run` to start the server",
            ],
            next_steps=[
                f"go.initializers module_name={module_name}",
                f"go.gorm_entity resource=<resource> module_name={module_name}",
                f"go.swagger_fiber module_name={module_name} app_name={app_name}",
                f"go.docker_setup app_name={app}",
            ],
        )

    # ------------------------------------------------------------------

    def _go_mod(self, module_name: str, go_version: str) -> str:
        return (
            f"module {module_name}\n\n"
            f"go {go_version}\n\n"
            "require (\n"
            "\tgithub.com/gofiber/fiber/v2 v2.52.6\n"
            "\tgithub.com/gofiber/swagger v1.1.1\n"
            "\tgorm.io/gorm v1.25.12\n"
            "\tgorm.io/driver/postgres v1.5.11\n"
            "\tgithub.com/golang-jwt/jwt/v4 v4.5.2\n"
            "\tgithub.com/swaggo/swag v1.16.4\n"
            "\tgithub.com/google/uuid v1.6.0\n"
            "\tgithub.com/joho/godotenv v1.5.1\n"
            "\tgithub.com/go-playground/validator/v10 v10.22.1\n"
            "\tgithub.com/streadway/amqp v1.1.0\n"
            ")\n"
        )

    def _main_go(self, module_name: str, app_name: str, port: str, resource: str = "") -> str:
        r = resource.lower().replace("-", "_").replace(" ", "_") if resource else ""
        R = r.capitalize() if r else ""

        if r and R:
            routes_block = (
                f"\t{r}Controller := controllers.New{R}Controller(services.{R}Service)\n\n"
                f'\tapi := app.Group("/")\n\n'
                f"\t// Public auth routes\n"
                f'\t// auth := api.Group("/auth")\n'
                f"\t// auth.Post(\"/token\", authController.GenerateTokenHandler)\n\n"
                f"\t// Protected routes (require authentication)\n"
                f"\tprotected := api.Group(\"/\", AuthMiddleware(services))\n\n"
                f"\t{r}s := protected.Group(\"/{r}s\")\n"
                f"\t{r}s.Post(\"/\", {r}Controller.Create)\n"
                f"\t{r}s.Get(\"/\", {r}Controller.GetAll)\n"
                f"\t{r}s.Get(\"/name/:name\", {r}Controller.GetByName)\n"
                f"\t{r}s.Get(\"/:id\", {r}Controller.GetByID)\n"
                f"\t{r}s.Put(\"/:id\", {r}Controller.Update)\n"
                f"\t{r}s.Delete(\"/:id\", {r}Controller.Delete)\n"
            )
            controllers_import = f'\t"{module_name}/controllers"\n'
        else:
            routes_block = (
                '\tapi := app.Group("/")\n'
                "\t_ = api\n\n"
                "\t// Register controllers here, e.g.:\n"
                "\t// resourceController := controllers.NewResourceController(services.ResourceService)\n"
                "\t// protected := api.Group(\"/\", AuthMiddleware(services))\n"
                "\t// protected.Post(\"/resources\", resourceController.Create)\n"
            )
            controllers_import = f'\t// "{module_name}/controllers"\n'

        return (
            "package main\n\n"
            "import (\n"
            '\t"log"\n'
            '\t"os"\n\n'
            + controllers_import
            + f'\t"{module_name}/initializers"\n\n'
            f'\t_ "{module_name}/cmd/docs"\n\n'
            '\t"github.com/gofiber/fiber/v2"\n'
            '\t"github.com/gofiber/fiber/v2/middleware/basicauth"\n'
            '\t"github.com/gofiber/fiber/v2/middleware/cors"\n'
            '\t"github.com/gofiber/fiber/v2/middleware/logger"\n'
            '\t"github.com/gofiber/swagger"\n'
            '\t"github.com/joho/godotenv"\n'
            ")\n\n"
            "func AuthMiddleware(services *initializers.Services) fiber.Handler {\n"
            "\treturn func(c *fiber.Ctx) error {\n"
            '\t\tauthHeader := c.Get("Authorization")\n'
            '\t\tif authHeader == "" {\n'
            "\t\t\treturn c.Status(401).JSON(fiber.Map{\n"
            '\t\t\t\t"error": "Missing authorization header",\n'
            "\t\t\t})\n"
            "\t\t}\n\n"
            '\t\tif len(authHeader) <= 7 || authHeader[:7] != "Bearer " {\n'
            "\t\t\treturn c.Status(401).JSON(fiber.Map{\n"
            '\t\t\t\t"error": "Invalid authorization header format. Use \'Bearer <token>\'",\n'
            "\t\t\t})\n"
            "\t\t}\n\n"
            "\t\treturn c.Next()\n"
            "\t}\n"
            "}\n\n"
            "func initializeRoutes(app *fiber.App, services *initializers.Services) {\n"
            + routes_block
            + "}\n\n"
            "func configureMiddleware(app *fiber.App) {\n"
            "\tapp.Use(cors.New(cors.Config{\n"
            '\t\tAllowOrigins: "",\n'
            '\t\tAllowMethods: "GET,POST,PUT,DELETE,OPTIONS",\n'
            '\t\tAllowHeaders: "Origin, Content-Type, Accept, Authorization",\n'
            "\t}))\n\n"
            "\tapp.Use(logger.New(logger.Config{\n"
            '\t\tFormat: "[${time}] ${status} - ${method} ${path}\\n",\n'
            "\t}))\n"
            "}\n\n"
            "func main() {\n"
            '\tif err := godotenv.Load(); err != nil {\n'
            '\t\tlog.Println("Warning: .env file not found")\n'
            "\t}\n\n"
            "\tdb := initializers.InitialDB()\n"
            "\tinitializers.RunMigrations(db)\n\n"
            "\tservices := initializers.InitServices(db)\n\n"
            "\tapp := fiber.New(fiber.Config{\n"
            f'\t\tAppName: "{app_name}",\n'
            "\t})\n\n"
            "\tconfigureMiddleware(app)\n\n"
            '\tswaggerUser := os.Getenv("SWAGGER_USER")\n'
            '\tswaggerPass := os.Getenv("SWAGGER_PASSWORD")\n\n'
            '\tif swaggerUser == "" || swaggerPass == "" {\n'
            '\t\tlog.Fatal("SWAGGER_USER and SWAGGER_PASSWORD must be set in .env file")\n'
            "\t}\n\n"
            "\tswaggerAuth := basicauth.New(basicauth.Config{\n"
            "\t\tUsers: map[string]string{\n"
            "\t\t\tswaggerUser: swaggerPass,\n"
            "\t\t},\n"
            '\t\tRealm: "Swagger Restricted",\n'
            "\t})\n\n"
            '\tapp.Get("/swagger/*", swaggerAuth, swagger.HandlerDefault)\n'
            '\tapp.Get("/docs", swaggerAuth, func(c *fiber.Ctx) error {\n'
            '\t\treturn c.Redirect("/swagger/index.html")\n'
            "\t})\n\n"
            "\tinitializeRoutes(app, services)\n\n"
            '\tport := os.Getenv("PORT")\n'
            '\tif port == "" {\n'
            f'\t\tport = "{port}"\n'
            "\t}\n\n"
            '\tlog.Printf("🚀 Server is running on http://0.0.0.0:%s", port)\n'
            '\tif err := app.Listen(":" + port); err != nil {\n'
            '\t\tlog.Fatalf("❌ Failed to start server: %v", err)\n'
            "\t}\n"
            "}\n"
        )

    def _env_example(self, port: str) -> str:
        return (
            "# Database\n"
            "DB_HOST=localhost\n"
            "DB_USER=postgres\n"
            "DB_PASSWORD=secret\n"
            "DB_NAME=mydb\n"
            "DB_PORT=5432\n"
            "DB_SSL_MODE=disable\n"
            "DB_TIMEZONE=UTC\n\n"
            "# Application\n"
            f"PORT={port}\n\n"
            "# JWT Authentication\n"
            "JWT_SECRET=replace-with-32-or-more-character-secret\n"
            "CLIENT_ID_1=your-client-id\n"
            "SECRET_1=your-client-secret\n\n"
            "# Swagger UI basic auth\n"
            "SWAGGER_USER=admin\n"
            "SWAGGER_PASSWORD=changeme\n\n"
            "# RabbitMQ (optional)\n"
            "RABBITMQ_BASE_URL=amqp://guest:guest@localhost:5672/\n"
            "RABBITMQ_API_USERNAME=guest\n"
            "RABBITMQ_API_PASSWORD=guest\n"
            "RABBITMQ_VHOST=/\n"
        )

    def _makefile(self, app: str) -> str:
        return (
            ".PHONY: run build test swagger lint docker-up docker-down\n\n"
            f"BINARY := {app}\n\n"
            "run:\n"
            "\tgo run ./cmd/...\n\n"
            "build:\n"
            f"\tgo build -o bin/$(BINARY) ./cmd/...\n\n"
            "test:\n"
            "\tgo test ./... -race -cover\n\n"
            "swagger:\n"
            "\tswag init -g cmd/main.go -o cmd/docs\n\n"
            "lint:\n"
            "\tgolangci-lint run ./...\n\n"
            "docker-up:\n"
            "\tdocker compose up -d\n\n"
            "docker-down:\n"
            "\tdocker compose down\n\n"
            "tidy:\n"
            "\tgo mod tidy\n"
        )
