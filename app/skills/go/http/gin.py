from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoGinAppSkill(BaseSkill):
    name = "go.gin_app"
    description = "Generate Gin engine setup with global middleware chain (CORS, recovery, logger)."
    category = SkillCategory.GO
    tags = ["go", "gin", "app", "middleware", "cors", "http", "framework"]
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
            "\t\"net/http\"\n"
            "\t\"time\"\n\n"
            "\t\"github.com/gin-gonic/gin\"\n"
            "\t\"go.uber.org/zap\"\n"
            ")\n\n"
            "type Server struct {\n"
            "\tcfg    *Config\n"
            "\tlogger *zap.Logger\n"
            "}\n\n"
            "func (s *Server) buildRouter() *gin.Engine {\n"
            "\tgin.SetMode(gin.ReleaseMode)\n"
            "\tr := gin.New()\n"
            "\tr.Use(gin.Recovery())\n"
            "\tr.Use(corsMiddleware())\n\n"
            "\tr.GET(\"/health\", func(c *gin.Context) {\n"
            "\t\tc.JSON(http.StatusOK, gin.H{\"status\": \"ok\"})\n"
            "\t})\n\n"
            "\treturn r\n"
            "}\n\n"
            "func corsMiddleware() gin.HandlerFunc {\n"
            "\treturn func(c *gin.Context) {\n"
            "\t\tc.Header(\"Access-Control-Allow-Origin\", \"*\")\n"
            "\t\tc.Header(\"Access-Control-Allow-Methods\", \"GET,POST,PUT,PATCH,DELETE,OPTIONS\")\n"
            "\t\tc.Header(\"Access-Control-Allow-Headers\", \"Origin,Content-Type,Authorization\")\n"
            "\t\tif c.Request.Method == http.MethodOptions {\n"
            "\t\t\tc.AbortWithStatus(http.StatusNoContent)\n"
            "\t\t\treturn\n"
            "\t\t}\n"
            "\t\tc.Next()\n"
            "\t}\n"
            "}\n\n"
            "func (s *Server) Start(ctx context.Context) error {\n"
            "\trouter := s.buildRouter()\n"
            "\tsrv := &http.Server{\n"
            "\t\tAddr:         fmt.Sprintf(\":%s\", s.cfg.AppPort),\n"
            "\t\tHandler:      router,\n"
            "\t\tReadTimeout:  10 * time.Second,\n"
            "\t\tWriteTimeout: 10 * time.Second,\n"
            "\t\tIdleTimeout:  60 * time.Second,\n"
            "\t}\n"
            "\tgo func() {\n"
            "\t\t<-ctx.Done()\n"
            "\t\tshutCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)\n"
            "\t\tdefer cancel()\n"
            "\t\t_ = srv.Shutdown(shutCtx)\n"
            "\t}()\n"
            "\ts.logger.Info(\"starting gin server\", zap.String(\"addr\", srv.Addr))\n"
            "\treturn srv.ListenAndServe()\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Gin server for `{app_name}`",
            artifacts=[
                CodeArtifact("internal/app/server.go", code, "go", "Gin server setup")
            ],
            dependencies=["github.com/gin-gonic/gin"],
            next_steps=["go.gin_routes", "go.gin_middleware"],
        )


@SkillRegistry.register
class GoGinHandlerSkill(BaseSkill):
    name = "go.gin_handler"
    description = "Generate CRUD handlers using *gin.Context with automatic binding and validation."
    category = SkillCategory.GO
    tags = ["go", "gin", "handler", "crud", "rest", "http"]
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
            "\t\"github.com/gin-gonic/gin\"\n"
            f"\t\"{module_name}/internal/domain\"\n"
            f"\t\"{module_name}/internal/service\"\n"
            ")\n\n"
            f"type {R}Handler struct {{\n"
            f"\tsvc *service.{R}Service\n"
            "}\n\n"
            f"func New{R}Handler(svc *service.{R}Service) *{R}Handler {{\n"
            f"\treturn &{R}Handler{{svc: svc}}\n"
            "}\n\n"
            f"func (h *{R}Handler) List(c *gin.Context) {{\n"
            "\tlimitStr := c.DefaultQuery(\"limit\", \"20\")\n"
            "\toffsetStr := c.DefaultQuery(\"offset\", \"0\")\n"
            "\tlimit, _ := strconv.Atoi(limitStr)\n"
            "\toffset, _ := strconv.Atoi(offsetStr)\n"
            "\titems, err := h.svc.List(c.Request.Context(), limit, offset)\n"
            "\tif err != nil {\n"
            "\t\tc.JSON(http.StatusInternalServerError, gin.H{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\tc.JSON(http.StatusOK, items)\n"
            "}\n\n"
            f"func (h *{R}Handler) Get(c *gin.Context) {{\n"
            "\tid, err := strconv.ParseInt(c.Param(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\tc.JSON(http.StatusBadRequest, gin.H{\"error\": \"invalid id\"})\n"
            "\t\treturn\n"
            "\t}\n"
            "\titem, err := h.svc.Get(c.Request.Context(), id)\n"
            "\tif err != nil {\n"
            "\t\tc.JSON(http.StatusNotFound, gin.H{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\tc.JSON(http.StatusOK, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Create(c *gin.Context) {{\n"
            f"\tvar req domain.Create{R}Request\n"
            "\tif err := c.ShouldBindJSON(&req); err != nil {\n"
            "\t\tc.JSON(http.StatusBadRequest, gin.H{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\titem, err := h.svc.Create(c.Request.Context(), req)\n"
            "\tif err != nil {\n"
            "\t\tc.JSON(http.StatusInternalServerError, gin.H{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\tc.JSON(http.StatusCreated, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Update(c *gin.Context) {{\n"
            "\tid, err := strconv.ParseInt(c.Param(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\tc.JSON(http.StatusBadRequest, gin.H{\"error\": \"invalid id\"})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\tvar req domain.Update{R}Request\n"
            "\tif err := c.ShouldBindJSON(&req); err != nil {\n"
            "\t\tc.JSON(http.StatusBadRequest, gin.H{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\titem, err := h.svc.Update(c.Request.Context(), id, req)\n"
            "\tif err != nil {\n"
            "\t\tc.JSON(http.StatusInternalServerError, gin.H{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\tc.JSON(http.StatusOK, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Delete(c *gin.Context) {{\n"
            "\tid, err := strconv.ParseInt(c.Param(\"id\"), 10, 64)\n"
            "\tif err != nil {\n"
            "\t\tc.JSON(http.StatusBadRequest, gin.H{\"error\": \"invalid id\"})\n"
            "\t\treturn\n"
            "\t}\n"
            "\tif err := h.svc.Delete(c.Request.Context(), id); err != nil {\n"
            "\t\tc.JSON(http.StatusNotFound, gin.H{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\tc.Status(http.StatusNoContent)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Gin CRUD handler for `{R}`",
            artifacts=[
                CodeArtifact(f"internal/handler/{r}_handler.go", code, "go", f"Gin handler for {R}")
            ],
            dependencies=["github.com/gin-gonic/gin"],
        )


@SkillRegistry.register
class GoGinRoutesSkill(BaseSkill):
    name = "go.gin_routes"
    description = "Generate Gin route groups with versioning and CRUD registration."
    category = SkillCategory.GO
    tags = ["go", "gin", "routes", "router", "versioning", "http"]
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
            "\t\"github.com/gin-gonic/gin\"\n"
            f"\t\"{module_name}/internal/handler\"\n"
            ")\n\n"
            f"func Register{R}Routes(rg *gin.RouterGroup, h *handler.{R}Handler) {{\n"
            f"\tg := rg.Group(\"/{plural}\")\n"
            "\tg.GET(\"/\", h.List)\n"
            "\tg.GET(\"/:id\", h.Get)\n"
            "\tg.POST(\"/\", h.Create)\n"
            "\tg.PATCH(\"/:id\", h.Update)\n"
            "\tg.DELETE(\"/:id\", h.Delete)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Gin routes for `{R}` under {prefix}/{plural}",
            artifacts=[
                CodeArtifact(f"internal/routes/{r}_routes.go", code, "go", f"Gin route group for {R}")
            ],
            dependencies=["github.com/gin-gonic/gin"],
        )


@SkillRegistry.register
class GoGinMiddlewareSkill(BaseSkill):
    name = "go.gin_middleware"
    description = "Generate Gin middleware: JWT auth, CORS, request logging, and rate limit."
    category = SkillCategory.GO
    tags = ["go", "gin", "middleware", "jwt", "auth", "cors", "security"]
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
            "\t\"github.com/gin-gonic/gin\"\n"
            "\t\"github.com/golang-jwt/jwt/v5\"\n"
            ")\n\n"
            "func JWTAuth(secret string) gin.HandlerFunc {\n"
            "\treturn func(c *gin.Context) {\n"
            "\t\tauth := c.GetHeader(\"Authorization\")\n"
            "\t\tif !strings.HasPrefix(auth, \"Bearer \") {\n"
            "\t\t\tc.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{\"error\": \"missing token\"})\n"
            "\t\t\treturn\n"
            "\t\t}\n"
            "\t\ttokenStr := strings.TrimPrefix(auth, \"Bearer \")\n"
            "\t\ttoken, err := jwt.Parse(tokenStr, func(t *jwt.Token) (any, error) {\n"
            "\t\t\tif _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {\n"
            "\t\t\t\treturn nil, gin.Error{Err: http.ErrAbortHandler}\n"
            "\t\t\t}\n"
            "\t\t\treturn []byte(secret), nil\n"
            "\t\t})\n"
            "\t\tif err != nil || !token.Valid {\n"
            "\t\t\tc.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{\"error\": \"invalid token\"})\n"
            "\t\t\treturn\n"
            "\t\t}\n"
            "\t\tc.Set(\"claims\", token.Claims)\n"
            "\t\tc.Next()\n"
            "\t}\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary="Generated Gin JWT auth middleware",
            artifacts=[
                CodeArtifact("internal/middleware/jwt.go", jwt_mw, "go", "Gin JWT middleware")
            ],
            dependencies=["github.com/gin-gonic/gin", "github.com/golang-jwt/jwt/v5"],
        )
