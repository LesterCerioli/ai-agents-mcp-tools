from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoLoggerSkill(BaseSkill):
    name = "go.logger"
    description = (
        "Generate structured logging setup with uber-go/zap and request-scoped log fields."
    )
    category = SkillCategory.GO
    tags = ["go", "logger", "zap", "logging", "observability", "structured"]
    parameters = [
        SkillParameter(
            "log_level",
            "Default log level (debug, info, warn, error)",
            required=False,
            default="info",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        log_level: str = "info",
        **_: Any,
    ) -> SkillResult:
        code = (
            "package app\n\n"
            "import (\n"
            "\t\"go.uber.org/zap\"\n"
            "\t\"go.uber.org/zap/zapcore\"\n"
            ")\n\n"
            "// NewLogger creates a production-ready structured logger.\n"
            "func NewLogger(level string) *zap.Logger {\n"
            "\tvar zapLevel zapcore.Level\n"
            "\tif err := zapLevel.UnmarshalText([]byte(level)); err != nil {\n"
            "\t\tzapLevel = zapcore.InfoLevel\n"
            "\t}\n\n"
            "\tcfg := zap.NewProductionConfig()\n"
            "\tcfg.Level = zap.NewAtomicLevelAt(zapLevel)\n"
            "\tcfg.EncoderConfig.TimeKey = \"ts\"\n"
            "\tcfg.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder\n\n"
            "\tlogger, err := cfg.Build(zap.AddCallerSkip(0))\n"
            "\tif err != nil {\n"
            "\t\tpanic(\"failed to init logger: \" + err.Error())\n"
            "\t}\n"
            "\treturn logger\n"
            "}\n\n"
            "// LoggerFromContext retrieves the logger from a context key.\n"
            "// Use this in HTTP handlers to access request-scoped fields.\n"
            "func SugaredLogger(logger *zap.Logger) *zap.SugaredLogger {\n"
            "\treturn logger.Sugar()\n"
            "}\n"
        )

        middleware_code = (
            "package middleware\n\n"
            "import (\n"
            "\t\"time\"\n\n"
            "\t\"github.com/gofiber/fiber/v2\"\n"
            "\t\"go.uber.org/zap\"\n"
            ")\n\n"
            "// RequestLogger returns a Fiber middleware that logs each request using zap.\n"
            "func RequestLogger(logger *zap.Logger) fiber.Handler {\n"
            "\treturn func(c *fiber.Ctx) error {\n"
            "\t\tstart := time.Now()\n"
            "\t\terr := c.Next()\n"
            "\t\tlogger.Info(\"request\",\n"
            "\t\t\tzap.String(\"method\", c.Method()),\n"
            "\t\t\tzap.String(\"path\", c.Path()),\n"
            "\t\t\tzap.Int(\"status\", c.Response().StatusCode()),\n"
            "\t\t\tzap.Duration(\"latency\", time.Since(start)),\n"
            "\t\t\tzap.String(\"ip\", c.IP()),\n"
            "\t\t)\n"
            "\t\treturn err\n"
            "\t}\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary="Generated zap logger setup with request-scoped logging middleware",
            artifacts=[
                CodeArtifact(
                    filename="internal/app/logger.go",
                    content=code,
                    language="go",
                    description="Zap logger factory",
                ),
                CodeArtifact(
                    filename="internal/middleware/request_logger.go",
                    content=middleware_code,
                    language="go",
                    description="HTTP request logging middleware",
                ),
            ],
            dependencies=["go.uber.org/zap"],
            instructions=[
                "Inject *zap.Logger via constructor in wire.go",
                "Call zap.ReplaceGlobals(logger) in main.go if you want global access",
            ],
        )
