from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoFiberAppSkill(BaseSkill):
    name = "go.fiber_app"
    description = (
        "Generate Fiber v2 app initialization with global middleware: "
        "CORS, logger, recover, and rate limiter."
    )
    category = SkillCategory.GO
    tags = ["go", "fiber", "app", "middleware", "cors", "http", "framework"]
    parameters = [
        SkillParameter("app_name", "Application name"),
        SkillParameter("port", "Port to listen on", required=False, default="8080"),
        SkillParameter("module_name", "Go module name", required=False, default="github.com/org/app"),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_name: str,
        port: str = "8080",
        module_name: str = "github.com/org/app",
        **_: Any,
    ) -> SkillResult:
        code = (
            "package app\n\n"
            "import (\n"
            "\t\"context\"\n"
            "\t\"fmt\"\n"
            "\t\"time\"\n\n"
            "\t\"github.com/gofiber/fiber/v2\"\n"
            "\t\"github.com/gofiber/fiber/v2/middleware/compress\"\n"
            "\t\"github.com/gofiber/fiber/v2/middleware/cors\"\n"
            "\t\"github.com/gofiber/fiber/v2/middleware/limiter\"\n"
            "\t\"github.com/gofiber/fiber/v2/middleware/logger\"\n"
            "\t\"github.com/gofiber/fiber/v2/middleware/recover\"\n"
            "\t\"github.com/gofiber/fiber/v2/middleware/requestid\"\n"
            "\t\"go.uber.org/zap\"\n"
            ")\n\n"
            "// Server wraps the Fiber application.\n"
            "type Server struct {\n"
            "\tapp    *fiber.App\n"
            "\tcfg    *Config\n"
            "\tlogger *zap.Logger\n"
            "}\n\n"
            "func (s *Server) buildApp() *fiber.App {\n"
            "\tapp := fiber.New(fiber.Config{\n"
            "\t\tAppName:               \"" + app_name + "\",\n"
            "\t\tReadTimeout:           10 * time.Second,\n"
            "\t\tWriteTimeout:          10 * time.Second,\n"
            "\t\tIdleTimeout:           60 * time.Second,\n"
            "\t\tEnableTrustedProxyCheck: true,\n"
            "\t})\n\n"
            "\tapp.Use(requestid.New())\n"
            "\tapp.Use(recover.New())\n"
            "\tapp.Use(logger.New(logger.Config{\n"
            "\t\tFormat: \"${time} ${status} - ${latency} ${method} ${path}\\n\",\n"
            "\t}))\n"
            "\tapp.Use(cors.New(cors.Config{\n"
            "\t\tAllowOrigins: \"*\",\n"
            "\t\tAllowMethods: \"GET,POST,PUT,PATCH,DELETE,OPTIONS\",\n"
            "\t\tAllowHeaders: \"Origin,Content-Type,Authorization\",\n"
            "\t}))\n"
            "\tapp.Use(compress.New())\n"
            "\tapp.Use(limiter.New(limiter.Config{\n"
            "\t\tMax:        100,\n"
            "\t\tExpiration: 1 * time.Minute,\n"
            "\t}))\n\n"
            "\tapp.Get(\"/health\", func(c *fiber.Ctx) error {\n"
            "\t\treturn c.JSON(fiber.Map{\"status\": \"ok\"})\n"
            "\t})\n\n"
            "\treturn app\n"
            "}\n\n"
            "func (s *Server) Start(ctx context.Context) error {\n"
            "\ts.app = s.buildApp()\n"
            "\tgo func() {\n"
            "\t\t<-ctx.Done()\n"
            "\t\t_ = s.app.Shutdown()\n"
            "\t}()\n"
            f"\taddr := fmt.Sprintf(\":%s\", s.cfg.AppPort)\n"
            "\ts.logger.Info(\"starting fiber server\", zap.String(\"addr\", addr))\n"
            "\treturn s.app.Listen(addr)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Fiber v2 app for `{app_name}` on port {port}",
            artifacts=[
                CodeArtifact(
                    filename="internal/app/server.go",
                    content=code,
                    language="go",
                    description="Fiber v2 server with global middleware",
                )
            ],
            dependencies=["github.com/gofiber/fiber/v2"],
            next_steps=["go.fiber_routes", "go.fiber_middleware"],
        )


@SkillRegistry.register
class GoFiberHandlerSkill(BaseSkill):
    name = "go.fiber_handler"
    description = "Generate full CRUD Fiber v2 handler using fiber.Ctx with request parsing and validation."
    category = SkillCategory.GO
    tags = ["go", "fiber", "handler", "crud", "rest", "http"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form"),
        SkillParameter("module_name", "Go module name", required=False, default="github.com/org/app"),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        module_name: str = "github.com/org/app",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()

        code = (
            "package handler\n\n"
            "import (\n"
            "\t\"strconv\"\n\n"
            "\t\"github.com/gofiber/fiber/v2\"\n"
            "\t\"github.com/go-playground/validator/v10\"\n"
            f"\t\"{module_name}/internal/domain\"\n"
            f"\t\"{module_name}/internal/service\"\n"
            ")\n\n"
            f"type {R}Handler struct {{\n"
            f"\tsvc      *service.{R}Service\n"
            "\tvalidate *validator.Validate\n"
            "}\n\n"
            f"func New{R}Handler(svc *service.{R}Service) *{R}Handler {{\n"
            f"\treturn &{R}Handler{{svc: svc, validate: validator.New()}}\n"
            "}\n\n"
            f"func (h *{R}Handler) List(c *fiber.Ctx) error {{\n"
            "\tlimit := c.QueryInt(\"limit\", 20)\n"
            "\toffset := c.QueryInt(\"offset\", 0)\n"
            f"\titems, err := h.svc.List(c.Context(), limit, offset)\n"
            "\tif err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusInternalServerError, err.Error())\n"
            "\t}\n"
            "\treturn c.JSON(items)\n"
            "}\n\n"
            f"func (h *{R}Handler) Get(c *fiber.Ctx) error {{\n"
            "\tid, err := strconv.ParseInt(c.Params(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusBadRequest, \"invalid id\")\n"
            "\t}\n"
            f"\titem, err := h.svc.Get(c.Context(), id)\n"
            "\tif err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusNotFound, err.Error())\n"
            "\t}\n"
            f"\treturn c.JSON(domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Create(c *fiber.Ctx) error {{\n"
            f"\tvar req domain.Create{R}Request\n"
            "\tif err := c.BodyParser(&req); err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusBadRequest, err.Error())\n"
            "\t}\n"
            "\tif err := h.validate.Struct(req); err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusUnprocessableEntity, err.Error())\n"
            "\t}\n"
            f"\titem, err := h.svc.Create(c.Context(), req)\n"
            "\tif err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusInternalServerError, err.Error())\n"
            "\t}\n"
            f"\treturn c.Status(fiber.StatusCreated).JSON(domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Update(c *fiber.Ctx) error {{\n"
            "\tid, err := strconv.ParseInt(c.Params(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusBadRequest, \"invalid id\")\n"
            "\t}\n"
            f"\tvar req domain.Update{R}Request\n"
            "\tif err := c.BodyParser(&req); err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusBadRequest, err.Error())\n"
            "\t}\n"
            f"\titem, err := h.svc.Update(c.Context(), id, req)\n"
            "\tif err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusInternalServerError, err.Error())\n"
            "\t}\n"
            f"\treturn c.JSON(domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Delete(c *fiber.Ctx) error {{\n"
            "\tid, err := strconv.ParseInt(c.Params(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\treturn fiber.NewError(fiber.StatusBadRequest, \"invalid id\")\n"
            "\t}\n"
            f"\tif err := h.svc.Delete(c.Context(), id); err != nil {{\n"
            "\t\treturn fiber.NewError(fiber.StatusNotFound, err.Error())\n"
            "\t}\n"
            "\treturn c.SendStatus(fiber.StatusNoContent)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Fiber v2 CRUD handler for `{R}`",
            artifacts=[
                CodeArtifact(
                    filename=f"internal/handler/{r}_handler.go",
                    content=code,
                    language="go",
                    description=f"Fiber v2 handler for {R}",
                )
            ],
            dependencies=["github.com/gofiber/fiber/v2", "github.com/go-playground/validator/v10"],
            next_steps=[f"go.fiber_routes resource={resource}"],
        )


@SkillRegistry.register
class GoFiberRoutesSkill(BaseSkill):
    name = "go.fiber_routes"
    description = "Generate Fiber v2 route registration with groups and API versioning (/api/v1/)."
    category = SkillCategory.GO
    tags = ["go", "fiber", "routes", "router", "versioning", "http"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form"),
        SkillParameter("module_name", "Go module name", required=False, default="github.com/org/app"),
        SkillParameter("prefix", "API prefix", required=False, default="/api/v1"),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        module_name: str = "github.com/org/app",
        prefix: str = "/api/v1",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()
        plural = f"{r}s"

        code = (
            "package routes\n\n"
            "import (\n"
            "\t\"github.com/gofiber/fiber/v2\"\n"
            f"\t\"{module_name}/internal/handler\"\n"
            ")\n\n"
            f"// Register{R}Routes mounts {R} CRUD routes on the Fiber app.\n"
            f"func Register{R}Routes(app *fiber.App, h *handler.{R}Handler) {{\n"
            f"\tv1 := app.Group(\"{prefix}\")\n"
            f"\tg := v1.Group(\"/{plural}\")\n\n"
            "\tg.Get(\"/\", h.List)\n"
            "\tg.Get(\"/:id\", h.Get)\n"
            "\tg.Post(\"/\", h.Create)\n"
            "\tg.Patch(\"/:id\", h.Update)\n"
            "\tg.Delete(\"/:id\", h.Delete)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Fiber v2 routes for `{R}` under {prefix}/{plural}",
            artifacts=[
                CodeArtifact(
                    filename=f"internal/routes/{r}_routes.go",
                    content=code,
                    language="go",
                    description=f"Fiber v2 route registration for {R}",
                )
            ],
            dependencies=["github.com/gofiber/fiber/v2"],
            instructions=[f"Call routes.Register{R}Routes(app, handler) in server.go"],
        )


@SkillRegistry.register
class GoFiberMiddlewareSkill(BaseSkill):
    name = "go.fiber_middleware"
    description = "Generate Fiber v2 custom middleware: JWT auth, API key, request ID, and timeout."
    category = SkillCategory.GO
    tags = ["go", "fiber", "middleware", "jwt", "auth", "security", "http"]
    parameters = [
        SkillParameter("module_name", "Go module name", required=False, default="github.com/org/app"),
    ]

    async def execute(  # type: ignore[override]
        self,
        module_name: str = "github.com/org/app",
        **_: Any,
    ) -> SkillResult:
        jwt_mw = (
            "package middleware\n\n"
            "import (\n"
            "\t\"strings\"\n\n"
            "\t\"github.com/gofiber/fiber/v2\"\n"
            "\t\"github.com/golang-jwt/jwt/v5\"\n"
            ")\n\n"
            "// JWTAuth validates the Bearer token and stores claims in locals.\n"
            "func JWTAuth(secret string) fiber.Handler {\n"
            "\treturn func(c *fiber.Ctx) error {\n"
            "\t\tauth := c.Get(\"Authorization\")\n"
            "\t\tif !strings.HasPrefix(auth, \"Bearer \") {\n"
            "\t\t\treturn fiber.ErrUnauthorized\n"
            "\t\t}\n"
            "\t\ttokenStr := strings.TrimPrefix(auth, \"Bearer \")\n"
            "\t\ttoken, err := jwt.Parse(tokenStr, func(t *jwt.Token) (any, error) {\n"
            "\t\t\tif _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {\n"
            "\t\t\t\treturn nil, fiber.ErrUnauthorized\n"
            "\t\t\t}\n"
            "\t\t\treturn []byte(secret), nil\n"
            "\t\t})\n"
            "\t\tif err != nil || !token.Valid {\n"
            "\t\t\treturn fiber.ErrUnauthorized\n"
            "\t\t}\n"
            "\t\tc.Locals(\"claims\", token.Claims)\n"
            "\t\treturn c.Next()\n"
            "\t}\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary="Generated Fiber v2 JWT auth middleware",
            artifacts=[
                CodeArtifact(
                    filename="internal/middleware/jwt.go",
                    content=jwt_mw,
                    language="go",
                    description="Fiber v2 JWT authentication middleware",
                )
            ],
            dependencies=["github.com/gofiber/fiber/v2", "github.com/golang-jwt/jwt/v5"],
        )
