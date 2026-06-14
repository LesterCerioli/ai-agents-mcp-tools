from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoControllerSkill(BaseSkill):
    """Generates controllers/resourceController.go.

    Follows the Medical-App-Core pattern:
    - Struct holds the ServiceContract interface (never the concrete implementation)
    - Constructor: NewResourceController(service contracts.ResourceServiceContract)
    - Full CRUD handlers with Swagger annotations
    - Uses fiber.Map for all responses
    - References net/http status codes
    """

    name = "go.controller"
    description = (
        "Generate controllers/{resource}Controller.go — Fiber v2 HTTP controller "
        "following the Medical-App-Core pattern. Struct depends on the ServiceContract "
        "interface. Includes Create, GetAll, GetByID, Update, Delete handlers with "
        "full Swagger annotations (@Summary, @Tags, @Accept, @Produce, @Param, "
        "@Success, @Failure, @Router, @Security BearerAuth)."
    )
    category = SkillCategory.GO
    tags = [
        "go", "fiber", "controller", "handler", "http", "swagger",
        "crud", "medical-app-core", "rest",
    ]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. patient, account, user)"),
        SkillParameter("module_name", "Go module name (e.g. github.com/org/my-service)"),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        module_name: str = "github.com/org/app",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()
        Rs = R + "s"
        tag = Rs

        code = self._generate(r, R, Rs, tag, module_name)

        return SkillResult(
            success=True,
            summary=f"Generated Fiber controller for `{R}` with full CRUD and Swagger annotations",
            artifacts=[
                CodeArtifact(
                    f"controllers/{r}Controller.go",
                    code,
                    "go",
                    f"Fiber v2 HTTP controller for {R} (Medical-App-Core pattern)",
                ),
            ],
            dependencies=[
                "github.com/gofiber/fiber/v2",
                "github.com/google/uuid",
            ],
            instructions=[
                f"Register controller in cmd/main.go initializeRoutes: "
                f"{r}Ctrl := controllers.New{R}Controller(services.{R}Service)",
                f"Mount routes: api.Post(\"/{r}s\", {r}Ctrl.Create)",
                f"Run `swag init -g cmd/main.go -o docs` to regenerate Swagger docs",
            ],
            next_steps=[
                f"go.swagger_fiber module_name={module_name}",
                f"go.initializers module_name={module_name} resources={resource}",
            ],
        )

    def _generate(self, r: str, R: str, Rs: str, tag: str, module_name: str) -> str:
        return (
            "package controllers\n\n"
            "import (\n"
            '\t"net/http"\n\n'
            '\t"github.com/gofiber/fiber/v2"\n'
            '\t"github.com/google/uuid"\n\n'
            f'\t"{module_name}/services/contracts"\n'
            ")\n\n"
            f"type {R}Controller struct {{\n"
            f"\t{R}Service contracts.{R}ServiceContract\n"
            "}\n\n"
            f"func New{R}Controller(service contracts.{R}ServiceContract) *{R}Controller {{\n"
            f"\treturn &{R}Controller{{{R}Service: service}}\n"
            "}\n\n"
            + self._create_handler(r, R, Rs, tag)
            + self._get_all_handler(r, R, Rs, tag)
            + self._get_by_id_handler(r, R, Rs, tag)
            + self._get_by_name_handler(r, R, Rs, tag)
            + self._update_handler(r, R, Rs, tag)
            + self._delete_handler(r, R, Rs, tag)
        )

    def _create_handler(self, r: str, R: str, Rs: str, tag: str) -> str:
        return (
            f"// Create{R} godoc\n"
            f"// @Summary      Create a new {r}\n"
            f"// @Description  Add a new {r} to the system\n"
            f"// @Tags         {tag}\n"
            "// @Accept       json\n"
            "// @Produce      json\n"
            f"// @Security     BearerAuth\n"
            f"// @Param        {r} body contracts.{R}InputDTO true \"{R} data\"\n"
            "// @Success      201  {object}  fiber.Map\n"
            "// @Failure      400  {object}  fiber.Map\n"
            "// @Failure      401  {object}  fiber.Map\n"
            "// @Failure      500  {object}  fiber.Map\n"
            f"// @Router       /{r}s [post]\n"
            f"func (ctrl *{R}Controller) Create(c *fiber.Ctx) error {{\n"
            f"\tvar input contracts.{R}InputDTO\n"
            "\tif err := c.BodyParser(&input); err != nil {\n"
            "\t\treturn c.Status(http.StatusBadRequest).JSON(fiber.Map{\n"
            '\t\t\t"error": "Invalid request body",\n'
            "\t\t})\n"
            "\t}\n"
            f"\tid, err := ctrl.{R}Service.Create(input)\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusInternalServerError).JSON(fiber.Map{\n"
            f'\t\t\t"error": "Failed to create {r}",\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.Status(http.StatusCreated).JSON(fiber.Map{\n"
            f'\t\t"message": "{R} created successfully",\n'
            '\t\t"id":      id,\n'
            "\t})\n"
            "}\n\n"
        )

    def _get_all_handler(self, r: str, R: str, Rs: str, tag: str) -> str:
        return (
            f"// GetAll{Rs} godoc\n"
            f"// @Summary      List all {r}s\n"
            f"// @Description  Get a list of all {r}s\n"
            f"// @Tags         {tag}\n"
            "// @Produce      json\n"
            "// @Security     BearerAuth\n"
            f"// @Success      200  {{array}}  contracts.{R}DTO\n"
            "// @Failure      401  {object}  fiber.Map\n"
            "// @Failure      500  {object}  fiber.Map\n"
            f"// @Router       /{r}s [get]\n"
            f"func (ctrl *{R}Controller) GetAll(c *fiber.Ctx) error {{\n"
            f"\titems, err := ctrl.{R}Service.GetAll()\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusInternalServerError).JSON(fiber.Map{\n"
            f'\t\t\t"error": "Failed to fetch {r}s",\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.Status(http.StatusOK).JSON(items)\n"
            "}\n\n"
        )

    def _get_by_id_handler(self, r: str, R: str, Rs: str, tag: str) -> str:
        return (
            f"// Get{R}ByID godoc\n"
            f"// @Summary      Get {r} by ID\n"
            f"// @Description  Retrieve a single {r} by its UUID\n"
            f"// @Tags         {tag}\n"
            "// @Produce      json\n"
            "// @Security     BearerAuth\n"
            f"// @Param        id   path  string  true  \"{R} UUID\"\n"
            f"// @Success      200  {{object}}  contracts.{R}DTO\n"
            "// @Failure      400  {object}  fiber.Map\n"
            "// @Failure      401  {object}  fiber.Map\n"
            "// @Failure      404  {object}  fiber.Map\n"
            f"// @Router       /{r}s/{{id}} [get]\n"
            f"func (ctrl *{R}Controller) GetByID(c *fiber.Ctx) error {{\n"
            "\tid, err := uuid.Parse(c.Params(\"id\"))\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusBadRequest).JSON(fiber.Map{\n"
            '\t\t\t"error": "Invalid UUID format",\n'
            "\t\t})\n"
            "\t}\n"
            f"\titem, err := ctrl.{R}Service.GetByID(id)\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusNotFound).JSON(fiber.Map{\n"
            f'\t\t\t"error": "{R} not found",\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.Status(http.StatusOK).JSON(item)\n"
            "}\n\n"
        )

    def _get_by_name_handler(self, r: str, R: str, Rs: str, tag: str) -> str:
        return (
            f"// Get{Rs}ByName godoc\n"
            f"// @Summary      Get {r}s by name\n"
            f"// @Description  Search {r}s by name (partial match)\n"
            f"// @Tags         {tag}\n"
            "// @Produce      json\n"
            "// @Security     BearerAuth\n"
            f"// @Param        name  path  string  true  \"{R} name\"\n"
            f"// @Success      200   {{array}}   contracts.{R}DTO\n"
            "// @Failure      401  {object}  fiber.Map\n"
            "// @Failure      404  {object}  fiber.Map\n"
            "// @Failure      500  {object}  fiber.Map\n"
            f"// @Router       /{r}s/name/{{name}} [get]\n"
            f"func (ctrl *{R}Controller) GetByName(c *fiber.Ctx) error {{\n"
            "\tname := c.Params(\"name\")\n"
            "\tif name == \"\" {\n"
            "\t\treturn c.Status(http.StatusBadRequest).JSON(fiber.Map{\n"
            '\t\t\t"error": "name parameter is required",\n'
            "\t\t})\n"
            "\t}\n"
            f"\titems, err := ctrl.{R}Service.GetByName(name)\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusInternalServerError).JSON(fiber.Map{\n"
            f'\t\t\t"error": "Failed to fetch {r}s",\n'
            "\t\t})\n"
            "\t}\n"
            "\tif len(items) == 0 {\n"
            "\t\treturn c.Status(http.StatusNotFound).JSON(fiber.Map{\n"
            f'\t\t\t"error": "No {r}s found with that name",\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.Status(http.StatusOK).JSON(items)\n"
            "}\n\n"
        )

    def _update_handler(self, r: str, R: str, Rs: str, tag: str) -> str:
        return (
            f"// Update{R} godoc\n"
            f"// @Summary      Update {r}\n"
            f"// @Description  Update an existing {r} by UUID\n"
            f"// @Tags         {tag}\n"
            "// @Accept       json\n"
            "// @Produce      json\n"
            "// @Security     BearerAuth\n"
            f"// @Param        id    path  string           true  \"{R} UUID\"\n"
            f"// @Param        {r}  body  contracts.{R}InputDTO  true  \"Updated {r} data\"\n"
            "// @Success      200  {object}  fiber.Map\n"
            "// @Failure      400  {object}  fiber.Map\n"
            "// @Failure      401  {object}  fiber.Map\n"
            "// @Failure      500  {object}  fiber.Map\n"
            f"// @Router       /{r}s/{{id}} [put]\n"
            f"func (ctrl *{R}Controller) Update(c *fiber.Ctx) error {{\n"
            "\tid, err := uuid.Parse(c.Params(\"id\"))\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusBadRequest).JSON(fiber.Map{\n"
            '\t\t\t"error": "Invalid UUID format",\n'
            "\t\t})\n"
            "\t}\n"
            f"\tvar input contracts.{R}InputDTO\n"
            "\tif err := c.BodyParser(&input); err != nil {\n"
            "\t\treturn c.Status(http.StatusBadRequest).JSON(fiber.Map{\n"
            '\t\t\t"error": "Invalid request body",\n'
            "\t\t})\n"
            "\t}\n"
            f"\tif err := ctrl.{R}Service.Update(id, input); err != nil {{\n"
            "\t\treturn c.Status(http.StatusInternalServerError).JSON(fiber.Map{\n"
            f'\t\t\t"error": "Failed to update {r}",\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.Status(http.StatusOK).JSON(fiber.Map{\n"
            f'\t\t"message": "{R} updated successfully",\n'
            "\t})\n"
            "}\n\n"
        )

    def _delete_handler(self, r: str, R: str, Rs: str, tag: str) -> str:
        return (
            f"// Delete{R} godoc\n"
            f"// @Summary      Delete {r}\n"
            f"// @Description  Soft-delete a {r} by UUID\n"
            f"// @Tags         {tag}\n"
            "// @Produce      json\n"
            "// @Security     BearerAuth\n"
            f"// @Param        id  path  string  true  \"{R} UUID\"\n"
            "// @Success      200  {object}  fiber.Map\n"
            "// @Failure      400  {object}  fiber.Map\n"
            "// @Failure      401  {object}  fiber.Map\n"
            "// @Failure      500  {object}  fiber.Map\n"
            f"// @Router       /{r}s/{{id}} [delete]\n"
            f"func (ctrl *{R}Controller) Delete(c *fiber.Ctx) error {{\n"
            "\tid, err := uuid.Parse(c.Params(\"id\"))\n"
            "\tif err != nil {\n"
            "\t\treturn c.Status(http.StatusBadRequest).JSON(fiber.Map{\n"
            '\t\t\t"error": "Invalid UUID format",\n'
            "\t\t})\n"
            "\t}\n"
            f"\tif err := ctrl.{R}Service.Delete(id); err != nil {{\n"
            "\t\treturn c.Status(http.StatusInternalServerError).JSON(fiber.Map{\n"
            f'\t\t\t"error": "Failed to delete {r}",\n'
            "\t\t})\n"
            "\t}\n"
            "\treturn c.Status(http.StatusOK).JSON(fiber.Map{\n"
            f'\t\t"message": "{R} deleted successfully",\n'
            "\t})\n"
            "}\n"
        )
