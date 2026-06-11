from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoConfigSkill(BaseSkill):
    name = "go.config"
    description = (
        "Generate a Go config struct with viper loader for environment variables "
        "and YAML files, with validation."
    )
    category = SkillCategory.GO
    tags = ["go", "config", "viper", "env", "yaml", "settings"]
    parameters = [
        SkillParameter("app_name", "Application name used for env var prefix"),
        SkillParameter("module_name", "Go module name", required=False, default="github.com/org/app"),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_name: str,
        module_name: str = "github.com/org/app",
        **_: Any,
    ) -> SkillResult:
        app = app_name.upper().replace("-", "_").replace(" ", "_")

        code = (
            "package app\n\n"
            "import (\n"
            "\t\"fmt\"\n"
            "\t\"strings\"\n\n"
            "\t\"github.com/spf13/viper\"\n"
            ")\n\n"
            "// Config holds all application configuration.\n"
            "type Config struct {\n"
            "\tAppPort     string `mapstructure:\"APP_PORT\"`\n"
            "\tDatabaseURL string `mapstructure:\"DATABASE_URL\"`\n"
            "\tLogLevel    string `mapstructure:\"LOG_LEVEL\"`\n"
            "\tJWTSecret   string `mapstructure:\"JWT_SECRET\"`\n"
            "\tEnvironment string `mapstructure:\"ENVIRONMENT\"`\n"
            "}\n\n"
            "// LoadConfig reads configuration from .env file and environment variables.\n"
            "func LoadConfig() (*Config, error) {\n"
            "\tv := viper.New()\n\n"
            "\tv.SetDefault(\"APP_PORT\", \"8080\")\n"
            "\tv.SetDefault(\"LOG_LEVEL\", \"info\")\n"
            "\tv.SetDefault(\"ENVIRONMENT\", \"development\")\n\n"
            "\tv.SetConfigFile(\".env\")\n"
            "\tv.SetConfigType(\"env\")\n"
            f"\tv.SetEnvKeyReplacer(strings.NewReplacer(\".\", \"_\"))\n"
            "\tv.AutomaticEnv()\n\n"
            "\t_ = v.ReadInConfig()\n\n"
            "\tvar cfg Config\n"
            "\tif err := v.Unmarshal(&cfg); err != nil {\n"
            '\t\treturn nil, fmt.Errorf("unmarshal config: %w", err)\n'
            "\t}\n\n"
            "\tif cfg.DatabaseURL == \"\" {\n"
            '\t\treturn nil, fmt.Errorf("DATABASE_URL is required")\n'
            "\t}\n\n"
            "\treturn &cfg, nil\n"
            "}\n"
        )

        env_example = (
            f"# {app_name} environment configuration\n"
            "APP_PORT=8080\n"
            "DATABASE_URL=postgres://postgres:postgres@localhost:5432/app?sslmode=disable\n"
            "LOG_LEVEL=info\n"
            "JWT_SECRET=change-me-in-production\n"
            "ENVIRONMENT=development\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated viper config loader for `{app_name}`",
            artifacts=[
                CodeArtifact(
                    filename="internal/app/config.go",
                    content=code,
                    language="go",
                    description="Application config with viper",
                ),
                CodeArtifact(
                    filename=".env.example",
                    content=env_example,
                    language="env",
                    description="Environment variable template",
                ),
            ],
            dependencies=["github.com/spf13/viper"],
            instructions=[
                "Copy .env.example to .env and fill in values",
                "Never commit .env to version control",
            ],
        )
