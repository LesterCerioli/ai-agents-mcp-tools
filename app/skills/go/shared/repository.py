from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoRepositorySkill(BaseSkill):
    name = "go.repository"
    description = (
        "Generate a Go repository interface and PostgreSQL implementation using pgx/v5. "
        "Framework-agnostic — pure domain layer."
    )
    category = SkillCategory.GO
    tags = ["go", "repository", "postgres", "pgx", "database", "ddd", "pattern"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
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

        interface_code = (
            "package repository\n\n"
            "import (\n"
            "\t\"context\"\n"
            f"\t\"{module_name}/internal/domain\"\n"
            ")\n\n"
            f"// {R}Repository defines persistence operations for {R}.\n"
            f"type {R}Repository interface {{\n"
            f"\tFindByID(ctx context.Context, id int64) (*domain.{R}, error)\n"
            f"\tFindAll(ctx context.Context, limit, offset int) ([]*domain.{R}, error)\n"
            f"\tCreate(ctx context.Context, req domain.Create{R}Request) (*domain.{R}, error)\n"
            f"\tUpdate(ctx context.Context, id int64, req domain.Update{R}Request) (*domain.{R}, error)\n"
            f"\tDelete(ctx context.Context, id int64) error\n"
            f"}}\n"
        )

        impl_code = (
            "package postgres\n\n"
            "import (\n"
            "\t\"context\"\n"
            "\t\"fmt\"\n"
            "\t\"time\"\n\n"
            "\t\"github.com/jackc/pgx/v5/pgxpool\"\n"
            f"\t\"{module_name}/internal/domain\"\n"
            ")\n\n"
            f"type pgx{R}Repo struct {{\n"
            "\tdb *pgxpool.Pool\n"
            "}\n\n"
            f"func New{R}Repository(db *pgxpool.Pool) *pgx{R}Repo {{\n"
            f"\treturn &pgx{R}Repo{{db: db}}\n"
            "}\n\n"
            f"func (r *pgx{R}Repo) FindByID(ctx context.Context, id int64) (*domain.{R}, error) {{\n"
            f"\tquery := `SELECT id, name, description, created_at, updated_at FROM {r}s WHERE id = $1`\n"
            f"\trow := r.db.QueryRow(ctx, query, id)\n"
            f"\tvar e domain.{R}\n"
            f"\tif err := row.Scan(&e.ID, &e.Name, &e.Description, &e.CreatedAt, &e.UpdatedAt); err != nil {{\n"
            f'\t\treturn nil, fmt.Errorf("find {r} by id %d: %w", id, err)\n'
            f"\t}}\n"
            f"\treturn &e, nil\n"
            f"}}\n\n"
            f"func (r *pgx{R}Repo) FindAll(ctx context.Context, limit, offset int) ([]*domain.{R}, error) {{\n"
            f"\tquery := `SELECT id, name, description, created_at, updated_at FROM {r}s ORDER BY id LIMIT $1 OFFSET $2`\n"
            f"\trows, err := r.db.Query(ctx, query, limit, offset)\n"
            f"\tif err != nil {{\n"
            f'\t\treturn nil, fmt.Errorf("find all {r}s: %w", err)\n'
            f"\t}}\n"
            f"\tdefer rows.Close()\n"
            f"\tvar items []*domain.{R}\n"
            f"\tfor rows.Next() {{\n"
            f"\t\tvar e domain.{R}\n"
            f"\t\tif err := rows.Scan(&e.ID, &e.Name, &e.Description, &e.CreatedAt, &e.UpdatedAt); err != nil {{\n"
            f'\t\t\treturn nil, fmt.Errorf("scan {r}: %w", err)\n'
            f"\t\t}}\n"
            f"\t\titems = append(items, &e)\n"
            f"\t}}\n"
            f"\treturn items, rows.Err()\n"
            f"}}\n\n"
            f"func (r *pgx{R}Repo) Create(ctx context.Context, req domain.Create{R}Request) (*domain.{R}, error) {{\n"
            f"\tquery := `INSERT INTO {r}s (name, description, created_at, updated_at) VALUES ($1, $2, $3, $3) RETURNING id, name, description, created_at, updated_at`\n"
            f"\tnow := time.Now().UTC()\n"
            f"\trow := r.db.QueryRow(ctx, query, req.Name, req.Description, now)\n"
            f"\tvar e domain.{R}\n"
            f"\tif err := row.Scan(&e.ID, &e.Name, &e.Description, &e.CreatedAt, &e.UpdatedAt); err != nil {{\n"
            f'\t\treturn nil, fmt.Errorf("create {r}: %w", err)\n'
            f"\t}}\n"
            f"\treturn &e, nil\n"
            f"}}\n\n"
            f"func (r *pgx{R}Repo) Update(ctx context.Context, id int64, req domain.Update{R}Request) (*domain.{R}, error) {{\n"
            f"\tquery := `UPDATE {r}s SET name = COALESCE($1, name), description = COALESCE($2, description), updated_at = $3 WHERE id = $4 RETURNING id, name, description, created_at, updated_at`\n"
            f"\tnow := time.Now().UTC()\n"
            f"\trow := r.db.QueryRow(ctx, query, req.Name, req.Description, now, id)\n"
            f"\tvar e domain.{R}\n"
            f"\tif err := row.Scan(&e.ID, &e.Name, &e.Description, &e.CreatedAt, &e.UpdatedAt); err != nil {{\n"
            f'\t\treturn nil, fmt.Errorf("update {r} %d: %w", id, err)\n'
            f"\t}}\n"
            f"\treturn &e, nil\n"
            f"}}\n\n"
            f"func (r *pgx{R}Repo) Delete(ctx context.Context, id int64) error {{\n"
            f"\t_, err := r.db.Exec(ctx, `DELETE FROM {r}s WHERE id = $1`, id)\n"
            f"\tif err != nil {{\n"
            f'\t\treturn fmt.Errorf("delete {r} %d: %w", id, err)\n'
            f"\t}}\n"
            f"\treturn nil\n"
            f"}}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated repository interface and pgx/v5 implementation for `{R}`",
            artifacts=[
                CodeArtifact(
                    filename=f"internal/repository/{r}_repository.go",
                    content=interface_code,
                    language="go",
                    description=f"{R} repository interface",
                ),
                CodeArtifact(
                    filename=f"internal/repository/postgres/{r}_repository.go",
                    content=impl_code,
                    language="go",
                    description=f"pgx/v5 implementation of {R} repository",
                ),
            ],
            dependencies=["github.com/jackc/pgx/v5"],
            instructions=[
                "Wire the repository in app/wire.go",
                "Inject *pgxpool.Pool from the database connection pool",
            ],
            next_steps=[f"go.service resource={resource}", "go.generate_migration resource=" + resource],
        )
