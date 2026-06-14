from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoSwaggerFiberSkill(BaseSkill):
    """Generates Swagger/OpenAPI integration for a Fiber v2 project.

    Uses swaggo/swag for annotation-driven doc generation and
    gofiber/swagger for serving the Swagger UI behind HTTP basic auth,
    following the Medical-App-Core security pattern.
    """

    name = "go.swagger_fiber"
    description = (
        "Generate Swagger/OpenAPI integration for Fiber v2: "
        "annotated controller template showing @Summary/@Param/@Success/@Security, "
        "Swagger UI route secured with HTTP basic auth (SWAGGER_USER / SWAGGER_PASSWORD env vars), "
        "and docs/docs.go bootstrap. Requires `swag init` to regenerate after annotation changes."
    )
    category = SkillCategory.GO
    tags = [
        "go", "fiber", "swagger", "openapi", "docs", "basicauth",
        "swaggo", "api-docs", "security",
    ]
    parameters = [
        SkillParameter("module_name", "Go module name (e.g. github.com/org/my-service)"),
        SkillParameter("app_name", "API title shown in Swagger UI", required=False, default="My API"),
        SkillParameter("host", "API host (e.g. localhost:3040)", required=False, default="localhost:3040"),
        SkillParameter(
            "resource",
            "Example resource name to generate an annotated controller (e.g. patient, user)",
            required=False,
            default="resource",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        module_name: str,
        app_name: str = "My API",
        host: str = "localhost:3040",
        resource: str = "resource",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()

        swagger_setup = self._swagger_setup_go(module_name, app_name, host)
        docs_stub = self._docs_stub_go(module_name, app_name, host)

        return SkillResult(
            success=True,
            summary=f"Generated Swagger docs stub for `{app_name}` — run `swag init -g cmd/main.go -o cmd/docs` to populate",
            artifacts=[
                CodeArtifact(
                    "cmd/docs/docs.go",
                    docs_stub,
                    "go",
                    "Swagger docs bootstrap (regenerate with `swag init -g cmd/main.go -o cmd/docs`)",
                ),
            ],
            dependencies=[
                "github.com/gofiber/swagger v1.1.1",
                "github.com/swaggo/swag v1.16.4",
            ],
            instructions=[
                "Add @title, @version, @host, @BasePath, @securityDefinitions.apikey BearerAuth "
                "annotations to cmd/main.go above func main()",
                "Run `swag init -g cmd/main.go -o cmd/docs` to generate cmd/docs/swagger.json and cmd/docs/swagger.yaml",
                "Import _ \"<module>/cmd/docs\" in cmd/main.go to register the generated docs",
                "Set SWAGGER_USER and SWAGGER_PASSWORD in .env",
                "Visit http://HOST/swagger/index.html to access the Swagger UI",
            ],
            next_steps=[
                "go.fiber_full_project module_name=" + module_name,
                "go.initializers module_name=" + module_name,
            ],
        )

    # ------------------------------------------------------------------
    # internal/app/swagger.go
    # ------------------------------------------------------------------

    def _swagger_setup_go(self, module_name: str, app_name: str, host: str) -> str:
        return (
            "package main\n\n"
            "import (\n"
            '\t"os"\n\n'
            '\t"github.com/gofiber/fiber/v2"\n'
            '\t"github.com/gofiber/fiber/v2/middleware/basicauth"\n'
            '\t"github.com/gofiber/swagger"\n'
            f'\t_ "{module_name}/docs"\n'
            ")\n\n"
            "// RegisterSwagger mounts the Swagger UI at /swagger/* behind HTTP basic auth.\n"
            "// Credentials are read from SWAGGER_USER / SWAGGER_PASSWORD env vars.\n"
            "// Call this from Server.Start() or your route initialiser.\n"
            "func RegisterSwagger(app *fiber.App) {\n"
            '\tuser := getSwaggerEnv("SWAGGER_USER", "admin")\n'
            '\tpass := getSwaggerEnv("SWAGGER_PASSWORD", "admin")\n\n'
            "\tauth := basicauth.New(basicauth.Config{\n"
            "\t\tUsers: map[string]string{user: pass},\n"
            '\t\tRealm: "Swagger Restricted",\n'
            "\t})\n\n"
            '\tapp.Get("/swagger/*", auth, swagger.HandlerDefault)\n'
            '\tapp.Get("/docs", auth, func(c *fiber.Ctx) error {\n'
            '\t\treturn c.Redirect("/swagger/index.html")\n'
            "\t})\n"
            "}\n\n"
            "func getSwaggerEnv(key, fallback string) string {\n"
            "\tif v := os.Getenv(key); v != \"\" {\n"
            "\t\treturn v\n"
            "\t}\n"
            "\treturn fallback\n"
            "}\n"
        )

    # ------------------------------------------------------------------
    # controllers/{resource}Controller.go (annotated template)
    # ------------------------------------------------------------------

    def _annotated_controller_go(self, r: str, R: str, module_name: str) -> str:
        plural = f"{r}s"
        return (
            "package controllers\n\n"
            "import (\n"
            '\t"net/http"\n\n'
            '\t"github.com/gofiber/fiber/v2"\n'
            f'\t"{module_name}/initializers"\n'
            f'\t"{module_name}/services/contracts"\n'
            ")\n\n"
            f"// {R}Controller handles HTTP requests for the {R} resource.\n"
            f"type {R}Controller struct {{\n"
            f"\tservice contracts.{R}ServiceContract\n"
            "}\n\n"
            f"// New{R}Controller constructs a {R}Controller injected with its service.\n"
            f"func New{R}Controller(svc contracts.{R}ServiceContract) *{R}Controller {{\n"
            f"\treturn &{R}Controller{{service: svc}}\n"
            "}\n\n"
            "// Create godoc\n"
            f"// @Summary     Create {R}\n"
            f"// @Description Create a new {r} in the system\n"
            f"// @Tags        {R}s\n"
            "// @Accept      json\n"
            "// @Produce     json\n"
            "// @Security    BearerAuth\n"
            f"// @Param       {r} body contracts.Create{R}Request true \"{R} payload\"\n"
            "// @Success     201 {object} fiber.Map\n"
            "// @Failure     400 {object} fiber.Map\n"
            "// @Failure     422 {object} fiber.Map\n"
            f"// @Router      /{plural} [post]\n"
            f"func (ctrl *{R}Controller) Create(c *fiber.Ctx) error {{\n"
            f"\tvar input contracts.Create{R}Request\n"
            "\tif err := c.BodyParser(&input); err != nil {\n"
            "\t\treturn c.Status(http.StatusBadRequest).JSON(fiber.Map{\n"
            '\t\t\t"error": "invalid request body: " + err.Error(),\n'
            "\t\t})\n"
            "\t}\n"
            f"\tid, err := ctrl.service.Create(input)\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusUnprocessableEntity).JSON(fiber.Map{\n"
            '\t\t\t"error": err.Error(),\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.Status(http.StatusCreated).JSON(fiber.Map{\n"
            f'\t\t"message": "{r} created successfully",\n'
            '\t\t"id":      id,\n'
            "\t})\n"
            "}\n\n"
            "// GetAll godoc\n"
            f"// @Summary     List {R}s\n"
            f"// @Description Return all {r}s\n"
            f"// @Tags        {R}s\n"
            "// @Produce     json\n"
            "// @Security    BearerAuth\n"
            "// @Success     200 {array}  fiber.Map\n"
            "// @Failure     500 {object} fiber.Map\n"
            f"// @Router      /{plural} [get]\n"
            f"func (ctrl *{R}Controller) GetAll(c *fiber.Ctx) error {{\n"
            f"\titems, err := ctrl.service.GetAll()\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusInternalServerError).JSON(fiber.Map{\n"
            '\t\t\t"error": err.Error(),\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.JSON(items)\n"
            "}\n\n"
            "// RegisterRoutes registers the controller's routes on the given router group.\n"
            f"func (ctrl *{R}Controller) RegisterRoutes(router fiber.Router) {{\n"
            f'\tg := router.Group("/{plural}")\n'
            "\tg.Post(\"/\", ctrl.Create)\n"
            "\tg.Get(\"/\", ctrl.GetAll)\n"
            "}\n\n"
            "// NewAuthControllerFromServices is a convenience constructor used in main.go.\n"
            f"func New{R}ControllerFromServices(s *initializers.Services) *{R}Controller {{\n"
            f"\treturn New{R}Controller(s.{R}Service)\n"
            "}\n"
        )

    # ------------------------------------------------------------------
    # docs/docs.go  (minimal stub — replaced by `swag init`)
    # ------------------------------------------------------------------

    def _docs_stub_go(self, module_name: str, app_name: str, host: str) -> str:
        return (
            "// Package docs — this file is auto-generated by swaggo/swag.\n"
            "// Run `swag init -g cmd/main.go -o cmd/docs` to regenerate.\n"
            "// DO NOT EDIT MANUALLY.\n"
            "package docs\n\n"
            "import \"github.com/swaggo/swag\"\n\n"
            'const docTemplate = `{\n'
            '    "swagger": "2.0",\n'
            '    "info": {\n'
            f'        "title": "{app_name}",\n'
            '        "version": "1.0"\n'
            '    },\n'
            f'    "host": "{host}",\n'
            '    "basePath": "/"\n'
            '}`\n\n'
            "// SwaggerInfo holds exported Swagger info.\n"
            "var SwaggerInfo = &swag.Spec{\n"
            f'\tTitle:   "{app_name}",\n'
            '\tVersion: "1.0",\n'
            f'\tHost:    "{host}",\n'
            '\tBasePath: "/",\n'
            "\tSchemes: []string{},\n"
            "\tDescription: \"\",\n"
            "\tInfoInstanceName: \"swagger\",\n"
            "\tSwaggerTemplate: docTemplate,\n"
            "}\n\n"
            "func init() {\n"
            "\tswag.Register(SwaggerInfo.InstanceName(), SwaggerInfo)\n"
            "}\n"
        )
