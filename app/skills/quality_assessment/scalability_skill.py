import json
from typing import Any

from app.architecture.schemas.quality_assessment import QualityAttribute, QualityAttributeScore
from app.architecture.schemas.solid import NormalizedDesignInput
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_BASE_SCORE_BY_STYLE: dict[str, float] = {
    "microservices": 70.0,
    "hexagonal": 60.0,
    "monolith": 45.0,
}

# Patterns that indicate async / event-driven capabilities
_ASYNC_PATTERNS: frozenset[str] = frozenset({
    "event_sourcing", "observer", "saga", "outbox",
})

# Patterns that indicate CQRS / horizontal read-write partitioning
_PARTITIONING_PATTERNS: frozenset[str] = frozenset({
    "cqrs",
})

# Patterns that support stateless request handling
_STATELESS_PATTERNS: frozenset[str] = frozenset({
    "cqrs", "event_sourcing", "proxy", "facade",
})

_STATELESS_KEYWORDS: frozenset[str] = frozenset({
    "stateless", "jwt", "token", "oauth", "session-free",
})


def _infer_statelessness(inp: NormalizedDesignInput) -> bool:
    """Infer statelessness from component technology hints and protocols."""
    for comp in inp.components:
        hints = " ".join(h.lower() for h in comp.get("technology_hints", []))
        protocols = " ".join(p.lower() for p in comp.get("protocols", []))
        combined = hints + " " + protocols
        if any(kw in combined for kw in _STATELESS_KEYWORDS):
            return True
    # Microservices/hexagonal with gateway strongly implies stateless REST
    if inp.has_gateway and inp.pattern.lower() in ("microservices", "hexagonal"):
        return True
    return False


def _infer_partitioning(inp: NormalizedDesignInput, pattern_names: list[str]) -> bool:
    """Infer workload partitioning: multiple services or CQRS."""
    if inp.service_count > 2:
        return True
    if len(inp.bounded_contexts) > 1:
        return True
    if any(p.lower() in _PARTITIONING_PATTERNS for p in pattern_names):
        return True
    return False


def _assess_scalability(
    inp: NormalizedDesignInput,
    architecture_style: str,
    pattern_names: list[str],
) -> QualityAttributeScore:
    style = architecture_style.lower()
    score = _BASE_SCORE_BY_STYLE.get(style, 50.0)
    notes: list[str] = [f"Base scalability for '{style or 'unknown'}' architecture: {score}."]

    # ── Statelessness ──────────────────────────────────────────────────────────
    stateless = _infer_statelessness(inp)
    if stateless:
        score += 10.0
        notes.append(
            "Stateless design detected (JWT/token auth or stateless REST gateway): "
            "enables horizontal scaling without session affinity."
        )
    else:
        notes.append(
            "No statelessness indicators found; session-based state limits horizontal scaling."
        )

    # ── Partitioning ──────────────────────────────────────────────────────────
    partitioned = _infer_partitioning(inp, pattern_names)
    if partitioned:
        score += 8.0
        notes.append(
            f"Workload partitioning detected ({inp.service_count} service(s) / "
            f"{len(inp.bounded_contexts)} bounded context(s)): independent scaling per domain."
        )
    else:
        notes.append(
            "Single service or monolithic partition; individual components cannot scale independently."
        )

    # ── Async / event-driven patterns ─────────────────────────────────────────
    patterns_lower = {p.lower() for p in pattern_names}
    async_matched = patterns_lower & _ASYNC_PATTERNS
    if async_matched:
        bonus = min(len(async_matched) * 5.0, 12.0)
        score += bonus
        notes.append(
            f"Async/event-driven patterns ({', '.join(sorted(async_matched))}): "
            "decouple producers from consumers, improving throughput under load."
        )
    else:
        notes.append(
            "No async or event-driven patterns identified; tight coupling may create bottlenecks."
        )

    # ── API gateway ───────────────────────────────────────────────────────────
    if inp.has_gateway:
        score += 8.0
        notes.append("API gateway enables load balancing and traffic partitioning.")

    # ── Shared database bottleneck ────────────────────────────────────────────
    if inp.has_shared_database:
        score -= 18.0
        notes.append(
            "Shared database is a scaling bottleneck and prevents independent deployment; "
            "migrate to database-per-service."
        )

    score = max(10.0, min(100.0, score))

    return QualityAttributeScore(
        attribute=QualityAttribute.SCALABILITY,
        score=round(score, 1),
        justification=" | ".join(notes),
    )


@SkillRegistry.register
class ScalabilityAssessSkill(BaseSkill):
    name = "quality_assessment.scalability_assess"
    description = (
        "Assesses scalability quality attribute (0–100) based on statelessness indicators, "
        "workload partitioning decisions, and async/event-driven patterns. "
        "Microservices with CQRS/event-sourcing and a stateless API gateway score highest."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    tags = ["quality", "scalability", "statelessness", "partitioning", "async", "architecture"]
    parameters = [
        SkillParameter("design_input", "Serialized NormalizedDesignInput dict.", type="object"),
        SkillParameter(
            "architecture_style",
            "Architecture style (microservices, hexagonal, monolith).",
            type="string",
            required=False,
        ),
        SkillParameter(
            "pattern_names",
            "List of recommended design pattern names.",
            type="array",
            required=False,
        ),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        architecture_style: str = "",
        pattern_names: list[str] | None = None,
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        result = _assess_scalability(inp, architecture_style, pattern_names or [])
        return SkillResult(
            success=True,
            summary=f"Scalability score: {result.score}",
            artifacts=[
                CodeArtifact(
                    filename="quality_scalability.json",
                    content=json.dumps(result.model_dump(), indent=2),
                    language="json",
                    description="Scalability quality assessment result",
                )
            ],
        )
