from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoServiceSkill(BaseSkill):
    name = "go.service"
    description = (
        "Generate a Go service layer with business logic injected via the repository interface."
    )
    category = SkillCategory.GO
    tags = ["go", "service", "business-logic", "use-case", "domain", "ddd"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
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
            "package service\n\n"
            "import (\n"
            "\t\"context\"\n"
            "\t\"fmt\"\n\n"
            f"\t\"{module_name}/internal/domain\"\n"
            f"\t\"{module_name}/internal/repository\"\n"
            ")\n\n"
            f"// {R}Service encapsulates business rules for the {R} domain.\n"
            f"type {R}Service struct {{\n"
            f"\trepo repository.{R}Repository\n"
            f"}}\n\n"
            f"func New{R}Service(repo repository.{R}Repository) *{R}Service {{\n"
            f"\treturn &{R}Service{{repo: repo}}\n"
            f"}}\n\n"
            f"func (s *{R}Service) Get(ctx context.Context, id int64) (*domain.{R}, error) {{\n"
            f"\te, err := s.repo.FindByID(ctx, id)\n"
            f"\tif err != nil {{\n"
            f'\t\treturn nil, fmt.Errorf("get {r}: %w", err)\n'
            f"\t}}\n"
            f"\treturn e, nil\n"
            f"}}\n\n"
            f"func (s *{R}Service) List(ctx context.Context, limit, offset int) ([]*domain.{R}, error) {{\n"
            f"\tif limit <= 0 || limit > 100 {{\n"
            f"\t\tlimit = 20\n"
            f"\t}}\n"
            f"\treturn s.repo.FindAll(ctx, limit, offset)\n"
            f"}}\n\n"
            f"func (s *{R}Service) Create(ctx context.Context, req domain.Create{R}Request) (*domain.{R}, error) {{\n"
            f"\tif req.Name == \"\" {{\n"
            f'\t\treturn nil, fmt.Errorf("name is required")\n'
            f"\t}}\n"
            f"\treturn s.repo.Create(ctx, req)\n"
            f"}}\n\n"
            f"func (s *{R}Service) Update(ctx context.Context, id int64, req domain.Update{R}Request) (*domain.{R}, error) {{\n"
            f"\t_, err := s.repo.FindByID(ctx, id)\n"
            f"\tif err != nil {{\n"
            f'\t\treturn nil, fmt.Errorf("{r} %d not found: %w", id, err)\n'
            f"\t}}\n"
            f"\treturn s.repo.Update(ctx, id, req)\n"
            f"}}\n\n"
            f"func (s *{R}Service) Delete(ctx context.Context, id int64) error {{\n"
            f"\t_, err := s.repo.FindByID(ctx, id)\n"
            f"\tif err != nil {{\n"
            f'\t\treturn fmt.Errorf("{r} %d not found: %w", id, err)\n'
            f"\t}}\n"
            f"\treturn s.repo.Delete(ctx, id)\n"
            f"}}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated service layer for `{R}`",
            artifacts=[
                CodeArtifact(
                    filename=f"internal/service/{r}_service.go",
                    content=code,
                    language="go",
                    description=f"Service layer for {R}",
                )
            ],
            instructions=[
                f"Wire in wire.go: New{R}Service(repo)",
                "Inject into HTTP handler via constructor",
            ],
            next_steps=[f"go.fiber_handler resource={resource}"],
        )
