from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoGorillaAppSkill(BaseSkill):
    name = "go.gorilla_app"
    description = "Generate gorilla/mux router setup with middleware chain and graceful shutdown."
    category = SkillCategory.GO
    tags = ["go", "gorilla", "mux", "app", "middleware", "http", "framework"]
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
            "\t\"encoding/json\"\n"
            "\t\"fmt\"\n"
            "\t\"net/http\"\n"
            "\t\"time\"\n\n"
            "\t\"github.com/gorilla/mux\"\n"
            "\t\"go.uber.org/zap\"\n"
            ")\n\n"
            "type Server struct {\n"
            "\tcfg    *Config\n"
            "\tlogger *zap.Logger\n"
            "}\n\n"
            "func (s *Server) buildRouter() *mux.Router {\n"
            "\tr := mux.NewRouter()\n"
            "\tr.Use(s.loggingMiddleware)\n"
            "\tr.Use(s.corsMiddleware)\n\n"
            "\tr.HandleFunc(\"/health\", func(w http.ResponseWriter, r *http.Request) {\n"
            "\t\tw.Header().Set(\"Content-Type\", \"application/json\")\n"
            "\t\t_ = json.NewEncoder(w).Encode(map[string]string{\"status\": \"ok\"})\n"
            "\t}).Methods(http.MethodGet)\n\n"
            "\treturn r\n"
            "}\n\n"
            "func (s *Server) loggingMiddleware(next http.Handler) http.Handler {\n"
            "\treturn http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {\n"
            "\t\tstart := time.Now()\n"
            "\t\tnext.ServeHTTP(w, r)\n"
            "\t\ts.logger.Info(\"request\",\n"
            "\t\t\tzap.String(\"method\", r.Method),\n"
            "\t\t\tzap.String(\"path\", r.URL.Path),\n"
            "\t\t\tzap.Duration(\"latency\", time.Since(start)),\n"
            "\t\t)\n"
            "\t})\n"
            "}\n\n"
            "func (s *Server) corsMiddleware(next http.Handler) http.Handler {\n"
            "\treturn http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {\n"
            "\t\tw.Header().Set(\"Access-Control-Allow-Origin\", \"*\")\n"
            "\t\tw.Header().Set(\"Access-Control-Allow-Methods\", \"GET,POST,PUT,PATCH,DELETE,OPTIONS\")\n"
            "\t\tw.Header().Set(\"Access-Control-Allow-Headers\", \"Origin,Content-Type,Authorization\")\n"
            "\t\tif r.Method == http.MethodOptions {\n"
            "\t\t\tw.WriteHeader(http.StatusNoContent)\n"
            "\t\t\treturn\n"
            "\t\t}\n"
            "\t\tnext.ServeHTTP(w, r)\n"
            "\t})\n"
            "}\n\n"
            "func (s *Server) Start(ctx context.Context) error {\n"
            "\tsrv := &http.Server{\n"
            "\t\tAddr:         fmt.Sprintf(\":%s\", s.cfg.AppPort),\n"
            "\t\tHandler:      s.buildRouter(),\n"
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
            "\ts.logger.Info(\"starting gorilla/mux server\", zap.String(\"addr\", srv.Addr))\n"
            "\treturn srv.ListenAndServe()\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated gorilla/mux server for `{app_name}`",
            artifacts=[
                CodeArtifact("internal/app/server.go", code, "go", "Gorilla/mux server setup")
            ],
            dependencies=["github.com/gorilla/mux"],
            next_steps=["go.gorilla_routes", "go.gorilla_handler"],
        )


@SkillRegistry.register
class GoGorillaHandlerSkill(BaseSkill):
    name = "go.gorilla_handler"
    description = "Generate CRUD handlers using http.HandlerFunc and gorilla/mux path variables."
    category = SkillCategory.GO
    tags = ["go", "gorilla", "handler", "crud", "rest", "http", "handlerfunc"]
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
            "\t\"encoding/json\"\n"
            "\t\"net/http\"\n"
            "\t\"strconv\"\n\n"
            "\t\"github.com/gorilla/mux\"\n"
            f"\t\"{module_name}/internal/domain\"\n"
            f"\t\"{module_name}/internal/service\"\n"
            ")\n\n"
            "func writeJSON(w http.ResponseWriter, status int, v any) {\n"
            "\tw.Header().Set(\"Content-Type\", \"application/json\")\n"
            "\tw.WriteHeader(status)\n"
            "\t_ = json.NewEncoder(w).Encode(v)\n"
            "}\n\n"
            f"type {R}Handler struct {{\n"
            f"\tsvc *service.{R}Service\n"
            "}\n\n"
            f"func New{R}Handler(svc *service.{R}Service) *{R}Handler {{\n"
            f"\treturn &{R}Handler{{svc: svc}}\n"
            "}\n\n"
            f"func (h *{R}Handler) List(w http.ResponseWriter, r *http.Request) {{\n"
            "\titems, err := h.svc.List(r.Context(), 20, 0)\n"
            "\tif err != nil {\n"
            "\t\twriteJSON(w, http.StatusInternalServerError, map[string]string{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\twriteJSON(w, http.StatusOK, items)\n"
            "}\n\n"
            f"func (h *{R}Handler) Get(w http.ResponseWriter, r *http.Request) {{\n"
            "\tvars := mux.Vars(r)\n"
            "\tid, err := strconv.ParseInt(vars[\"id\"], 10, 64)\n"
            "\tif err != nil {\n"
            "\t\twriteJSON(w, http.StatusBadRequest, map[string]string{\"error\": \"invalid id\"})\n"
            "\t\treturn\n"
            "\t}\n"
            "\titem, err := h.svc.Get(r.Context(), id)\n"
            "\tif err != nil {\n"
            "\t\twriteJSON(w, http.StatusNotFound, map[string]string{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\twriteJSON(w, http.StatusOK, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Create(w http.ResponseWriter, r *http.Request) {{\n"
            f"\tvar req domain.Create{R}Request\n"
            "\tif err := json.NewDecoder(r.Body).Decode(&req); err != nil {\n"
            "\t\twriteJSON(w, http.StatusBadRequest, map[string]string{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\titem, err := h.svc.Create(r.Context(), req)\n"
            "\tif err != nil {\n"
            "\t\twriteJSON(w, http.StatusInternalServerError, map[string]string{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\twriteJSON(w, http.StatusCreated, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Update(w http.ResponseWriter, r *http.Request) {{\n"
            "\tvars := mux.Vars(r)\n"
            "\tid, err := strconv.ParseInt(vars[\"id\"], 10, 64)\n"
            "\tif err != nil {\n"
            "\t\twriteJSON(w, http.StatusBadRequest, map[string]string{\"error\": \"invalid id\"})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\tvar req domain.Update{R}Request\n"
            "\tif err := json.NewDecoder(r.Body).Decode(&req); err != nil {\n"
            "\t\twriteJSON(w, http.StatusBadRequest, map[string]string{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\titem, err := h.svc.Update(r.Context(), id, req)\n"
            "\tif err != nil {\n"
            "\t\twriteJSON(w, http.StatusInternalServerError, map[string]string{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            f"\twriteJSON(w, http.StatusOK, domain.From{R}(item))\n"
            "}\n\n"
            f"func (h *{R}Handler) Delete(w http.ResponseWriter, r *http.Request) {{\n"
            "\tvars := mux.Vars(r)\n"
            "\tid, err := strconv.ParseInt(vars[\"id\"], 10, 64)\n"
            "\tif err != nil {\n"
            "\t\twriteJSON(w, http.StatusBadRequest, map[string]string{\"error\": \"invalid id\"})\n"
            "\t\treturn\n"
            "\t}\n"
            "\tif err := h.svc.Delete(r.Context(), id); err != nil {\n"
            "\t\twriteJSON(w, http.StatusNotFound, map[string]string{\"error\": err.Error()})\n"
            "\t\treturn\n"
            "\t}\n"
            "\tw.WriteHeader(http.StatusNoContent)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated gorilla/mux CRUD handler for `{R}`",
            artifacts=[
                CodeArtifact(f"internal/handler/{r}_handler.go", code, "go", f"Gorilla handler for {R}")
            ],
            dependencies=["github.com/gorilla/mux"],
        )


@SkillRegistry.register
class GoGorillaRoutesSkill(BaseSkill):
    name = "go.gorilla_routes"
    description = "Generate gorilla/mux subrouter registration with path prefix and method constraints."
    category = SkillCategory.GO
    tags = ["go", "gorilla", "routes", "subrouter", "mux", "http"]
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
            "\t\"net/http\"\n\n"
            "\t\"github.com/gorilla/mux\"\n"
            f"\t\"{module_name}/internal/handler\"\n"
            ")\n\n"
            f"func Register{R}Routes(r *mux.Router, h *handler.{R}Handler) {{\n"
            f"\tsub := r.PathPrefix(\"{prefix}/{plural}\").Subrouter()\n"
            "\tsub.HandleFunc(\"/\", h.List).Methods(http.MethodGet)\n"
            "\tsub.HandleFunc(\"/{id:[0-9]+}\", h.Get).Methods(http.MethodGet)\n"
            "\tsub.HandleFunc(\"/\", h.Create).Methods(http.MethodPost)\n"
            "\tsub.HandleFunc(\"/{id:[0-9]+}\", h.Update).Methods(http.MethodPatch)\n"
            "\tsub.HandleFunc(\"/{id:[0-9]+}\", h.Delete).Methods(http.MethodDelete)\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated gorilla/mux routes for `{R}` under {prefix}/{plural}",
            artifacts=[
                CodeArtifact(f"internal/routes/{r}_routes.go", code, "go", f"Gorilla routes for {R}")
            ],
            dependencies=["github.com/gorilla/mux"],
        )
