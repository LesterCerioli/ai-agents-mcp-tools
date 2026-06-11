from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoEchoAppSkill(BaseSkill):
    name = "go.echo_app"
    description = "Generate Echo v4 instance setup with binder, validator, and custom error handler."
    category = SkillCategory.GO
    tags = ["go", "echo", "app", "middleware", "validator", "http", "framework"]
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
            "\t\"net/http\"\n\n"
            "\t\"github.com/go-playground/validator/v10\"\n"
            "\t\"github.com/labstack/echo/v4\"\n"
            "\t\"github.com/labstack/echo/v4/middleware\"\n"
            "\t\"go.uber.org/zap\"\n"
            ")\n\n"
            "type CustomValidator struct{ v *validator.Validate }\n\n"
            "func (cv *CustomValidator) Validate(i any) error {\n"
            "\treturn cv.v.Struct(i)\n"
            "}\n\n"
            "type Server struct {\n"
            "\tcfg    *Config\n"
            "\tlogger *zap.Logger\n"
            "}\n\n"
            "func (s *Server) buildEcho() *echo.Echo {\n"
            "\te := echo.New()\n"
            "\te.HideBanner = true\n"
            "\te.Validator = &CustomValidator{v: validator.New()}\n\n"
            "\te.Use(middleware.Recover())\n"
            "\te.Use(middleware.RequestID())\n"
            "\te.Use(middleware.CORS())\n"
            "\te.Use(middleware.Gzip())\n\n"
            "\te.HTTPErrorHandler = func(err error, c echo.Context) {\n"
            "\t\tcode := http.StatusInternalServerError\n"
            "\t\tmsg := err.Error()\n"
            "\t\tif he, ok := err.(*echo.HTTPError); ok {\n"
            "\t\t\tcode = he.Code\n"
            "\t\t\tmsg = fmt.Sprintf(\"%v\", he.Message)\n"
            "\t\t}\n"
            "\t\t_ = c.JSON(code, map[string]string{\"error\": msg})\n"
            "\t}\n\n"
            "\te.GET(\"/health\", func(c echo.Context) error {\n"
            "\t\treturn c.JSON(http.StatusOK, map[string]string{\"status\": \"ok\"})\n"
            "\t})\n\n"
            "\treturn e\n"
            "}\n\n"
            "func (s *Server) Start(ctx context.Context) error {\n"
            "\te := s.buildEcho()\n"
            "\tgo func() {\n"
            "\t\t<-ctx.Done()\n"
            "\t\tshutCtx, cancel := context.WithTimeout(context.Background(), 5*s.cfg.AppPort)\n"
            "\t\tdefer cancel()\n"
            "\t\t_ = e.Shutdown(shutCtx)\n"
            "\t}()\n"
            "\taddr := fmt.Sprintf(\":%s\", s.cfg.AppPort)\n"
            "\ts.logger.Info(\"starting echo server\", zap.String(\"addr\", addr))\n"
            "\treturn e.Start(addr)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Echo v4 server for `{app_name}`",
            artifacts=[
                CodeArtifact("internal/app/server.go", code, "go", "Echo v4 server setup")
            ],
            dependencies=["github.com/labstack/echo/v4", "github.com/go-playground/validator/v10"],
            next_steps=["go.echo_routes", "go.echo_middleware"],
        )


@SkillRegistry.register
class GoEchoHandlerSkill(BaseSkill):
    name = "go.echo_handler"
    description = "Generate CRUD handlers using echo.Context with automatic binding and validation."
    category = SkillCategory.GO
    tags = ["go", "echo", "handler", "crud", "rest", "http"]
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
            "\t\"net/http\"\n"
            "\t\"strconv\"\n\n"
            "\t\"github.com/labstack/echo/v4\"\n"
            f"\t\"{module_name}/internal/domain\"\n"
            f"\t\"{module_name}/internal/service\"\n"
            ")\n\n"
            f"type {R}Handler struct {{\n"
            f"\tsvc *service.{R}Service\n"
            "}\n\n"
            f"func New{R}Handler(svc *service.{R}Service) *{R}Handler {{\n"
            f"\treturn &{R}Handler{{svc: svc}}\n"
            "}\n\n"
            f"func (h *{R}Handler) List(c echo.Context) error {{\n"
            "\tlimit := c.QueryParam(\"limit\")\n"
            "\tl := 20\n"
            "\tif limit != \"\" {\n"
            "\t\tif v, err := strconv.Atoi(limit); err == nil {\n"
            "\t\t\tl = v\n"
            "\t\t}\n"
            "\t}\n"
            "\titems, err := h.svc.List(c.Request().Context(), l, 0)\n"
            "\tif err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusInternalServerError, err.Error())\n"
            "\t}\n"
            "\treturn c.JSON(http.StatusOK, items)\n"
            "}\n\n"
            f"func (h *{R}Handler) Get(c echo.Context) error {{\n"
            "\tid, err := strconv.ParseInt(c.Param(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusBadRequest, \"invalid id\")\n"
            "\t}\n"
            "\titem, err := h.svc.Get(c.Request().Context(), id)\n"
            "\tif err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusNotFound, err.Error())\n"
            "\t}\n"
            f"\treturn c.JSON(http.StatusOK, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Create(c echo.Context) error {{\n"
            f"\tvar req domain.Create{R}Request\n"
            "\tif err := c.Bind(&req); err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusBadRequest, err.Error())\n"
            "\t}\n"
            "\tif err := c.Validate(req); err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusUnprocessableEntity, err.Error())\n"
            "\t}\n"
            "\titem, err := h.svc.Create(c.Request().Context(), req)\n"
            "\tif err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusInternalServerError, err.Error())\n"
            "\t}\n"
            f"\treturn c.JSON(http.StatusCreated, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Update(c echo.Context) error {{\n"
            "\tid, err := strconv.ParseInt(c.Param(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusBadRequest, \"invalid id\")\n"
            "\t}\n"
            f"\tvar req domain.Update{R}Request\n"
            "\tif err := c.Bind(&req); err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusBadRequest, err.Error())\n"
            "\t}\n"
            "\titem, err := h.svc.Update(c.Request().Context(), id, req)\n"
            "\tif err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusInternalServerError, err.Error())\n"
            "\t}\n"
            f"\treturn c.JSON(http.StatusOK, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Delete(c echo.Context) error {{\n"
            "\tid, err := strconv.ParseInt(c.Param(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusBadRequest, \"invalid id\")\n"
            "\t}\n"
            "\tif err := h.svc.Delete(c.Request().Context(), id); err != nil {\n"
            "\t\treturn echo.NewHTTPError(http.StatusNotFound, err.Error())\n"
            "\t}\n"
            "\treturn c.NoContent(http.StatusNoContent)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Echo v4 CRUD handler for `{R}`",
            artifacts=[
                CodeArtifact(f"internal/handler/{r}_handler.go", code, "go", f"Echo v4 handler for {R}")
            ],
            dependencies=["github.com/labstack/echo/v4"],
        )


@SkillRegistry.register
class GoEchoRoutesSkill(BaseSkill):
    name = "go.echo_routes"
    description = "Generate Echo v4 route group registration with versioning."
    category = SkillCategory.GO
    tags = ["go", "echo", "routes", "group", "versioning", "http"]
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
            "\t\"github.com/labstack/echo/v4\"\n"
            f"\t\"{module_name}/internal/handler\"\n"
            ")\n\n"
            f"func Register{R}Routes(e *echo.Echo, h *handler.{R}Handler) {{\n"
            f"\tg := e.Group(\"{prefix}/{plural}\")\n"
            "\tg.GET(\"/\", h.List)\n"
            "\tg.GET(\"/:id\", h.Get)\n"
            "\tg.POST(\"/\", h.Create)\n"
            "\tg.PATCH(\"/:id\", h.Update)\n"
            "\tg.DELETE(\"/:id\", h.Delete)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Echo v4 routes for `{R}` under {prefix}/{plural}",
            artifacts=[
                CodeArtifact(f"internal/routes/{r}_routes.go", code, "go", f"Echo routes for {R}")
            ],
            dependencies=["github.com/labstack/echo/v4"],
        )


@SkillRegistry.register
class GoEchoMiddlewareSkill(BaseSkill):
    name = "go.echo_middleware"
    description = "Generate Echo v4 middleware: JWT auth, request logger, and timeout."
    category = SkillCategory.GO
    tags = ["go", "echo", "middleware", "jwt", "auth", "timeout", "security"]
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
            "\t\"net/http\"\n"
            "\t\"strings\"\n\n"
            "\t\"github.com/golang-jwt/jwt/v5\"\n"
            "\t\"github.com/labstack/echo/v4\"\n"
            ")\n\n"
            "func JWTAuth(secret string) echo.MiddlewareFunc {\n"
            "\treturn func(next echo.HandlerFunc) echo.HandlerFunc {\n"
            "\t\treturn func(c echo.Context) error {\n"
            "\t\t\tauth := c.Request().Header.Get(\"Authorization\")\n"
            "\t\t\tif !strings.HasPrefix(auth, \"Bearer \") {\n"
            "\t\t\t\treturn echo.NewHTTPError(http.StatusUnauthorized, \"missing token\")\n"
            "\t\t\t}\n"
            "\t\t\ttokenStr := strings.TrimPrefix(auth, \"Bearer \")\n"
            "\t\t\ttoken, err := jwt.Parse(tokenStr, func(t *jwt.Token) (any, error) {\n"
            "\t\t\t\tif _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {\n"
            "\t\t\t\t\treturn nil, echo.ErrUnauthorized\n"
            "\t\t\t\t}\n"
            "\t\t\t\treturn []byte(secret), nil\n"
            "\t\t\t})\n"
            "\t\t\tif err != nil || !token.Valid {\n"
            "\t\t\t\treturn echo.NewHTTPError(http.StatusUnauthorized, \"invalid token\")\n"
            "\t\t\t}\n"
            "\t\t\tc.Set(\"claims\", token.Claims)\n"
            "\t\t\treturn next(c)\n"
            "\t\t}\n"
            "\t}\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary="Generated Echo v4 JWT middleware",
            artifacts=[
                CodeArtifact("internal/middleware/jwt.go", jwt_mw, "go", "Echo v4 JWT middleware")
            ],
            dependencies=["github.com/labstack/echo/v4", "github.com/golang-jwt/jwt/v5"],
        )
