import json
from typing import Any

from app.architecture.schemas.quality_assessment import QualityAttribute, QualityAttributeScore
from app.architecture.schemas.solid import NormalizedDesignInput, _INFRA_KEYWORDS
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_BASE_SCORE = 40.0

_AUTH_KEYWORDS: frozenset[str] = frozenset({
    "jwt", "oauth", "oidc", "keycloak", "auth0", "cognito",
    "bearer", "token", "authentication", "authorization",
    "api-key", "apikey", "rbac", "acl",
})

_DATA_CLASSIFICATION_KEYWORDS: frozenset[str] = frozenset({
    "pii", "sensitive", "confidential", "encrypted", "encryption",
    "vault", "secret", "classified", "gdpr", "hipaa", "pci",
    "private", "public", "internal", "restricted",
})


def _detect_auth_boundary(inp: NormalizedDesignInput) -> bool:
    """Detect explicit authentication/authorization boundary from component hints or protocols."""
    for comp in inp.components:
        hints = " ".join(h.lower() for h in comp.get("technology_hints", []))
        resp = comp.get("responsibility", "").lower()
        comp_type = comp.get("type", "").lower()
        combined = hints + " " + resp + " " + comp_type
        if any(kw in combined for kw in _AUTH_KEYWORDS):
            return True
        if comp_type == "gateway" and comp.get("layer", "").lower() == "presentation":
            return True
    return inp.has_gateway


def _detect_data_classification_zones(inp: NormalizedDesignInput) -> bool:
    """Detect data classification zones from bounded contexts or component responsibility descriptions."""
    if len(inp.bounded_contexts) > 1:
        return True
    for comp in inp.components:
        resp = comp.get("responsibility", "").lower()
        hints = " ".join(h.lower() for h in comp.get("technology_hints", []))
        combined = resp + " " + hints
        if any(kw in combined for kw in _DATA_CLASSIFICATION_KEYWORDS):
            return True
    for ds in inp.domain_services:
        resp = " ".join(ds.get("responsibilities", [])).lower()
        if any(kw in resp for kw in _DATA_CLASSIFICATION_KEYWORDS):
            return True
    return False


def _assess_security_boundary_clarity(
    inp: NormalizedDesignInput,
    solid_violations: list[str],
) -> QualityAttributeScore:
    score = _BASE_SCORE
    notes: list[str] = []

    # ── Explicit security layers (gateway / dedicated security component) ─────
    if inp.has_gateway:
        score += 15.0
        notes.append("API gateway defines a clear security enforcement boundary for all entry points.")
    else:
        notes.append("No API gateway detected; security enforcement is scattered across components.")

    # ── Authentication / authorization boundaries ─────────────────────────────
    has_auth_boundary = _detect_auth_boundary(inp)
    if has_auth_boundary:
        score += 15.0
        notes.append(
            "Explicit authentication/authorization boundary detected "
            "(auth gateway, OAuth/JWT component, or RBAC technology hint)."
        )
    else:
        notes.append(
            "No explicit authentication/authorization boundary found; "
            "access control responsibilities are undefined."
        )

    # ── Data classification zones ─────────────────────────────────────────────
    has_data_zones = _detect_data_classification_zones(inp)
    if has_data_zones:
        score += 12.0
        notes.append(
            "Data classification zones identified (bounded contexts, PII/sensitive data labels, "
            "or encryption/vault technology hints) — data ownership is scoped."
        )
    else:
        notes.append(
            "No data classification zones detected; "
            "sensitive data boundaries are not explicitly defined."
        )

    # ── Ports-and-adapters separation ─────────────────────────────────────────
    if inp.has_ports_and_adapters:
        score += 8.0
        notes.append(
            "Ports-and-adapters pattern separates the trusted domain core from external adapters."
        )

    # ── Clean domain layer (no infrastructure leaks) ─────────────────────────
    domain_clean = not any(
        {h.lower() for h in c.get("technology_hints", [])} & _INFRA_KEYWORDS
        for c in inp.components
        if c.get("layer") == "domain"
    )
    if domain_clean and inp.components:
        score += 5.0
        notes.append(
            "Domain layer carries no infrastructure hints — security concerns "
            "remain properly isolated in the infrastructure layer."
        )
    elif not domain_clean:
        score -= 8.0
        notes.append(
            "Domain components expose infrastructure technology hints, "
            "blurring the security boundary between domain and infrastructure."
        )

    # ── Repository pattern (centralised data-access control) ─────────────────
    if inp.has_repositories:
        score += 5.0
        notes.append(
            "Repository pattern centralises data-access logic, making it easier "
            "to enforce access-control policies at a single boundary."
        )

    # ── SRP violations blur security boundaries ───────────────────────────────
    if "srp" in solid_violations:
        score -= 5.0
        notes.append(
            "SRP violations blur component responsibilities, "
            "making it harder to enforce security policies consistently."
        )

    score = max(10.0, min(100.0, score))

    return QualityAttributeScore(
        attribute=QualityAttribute.SECURITY_BOUNDARY_CLARITY,
        score=round(score, 1),
        justification=" | ".join(notes),
    )


@SkillRegistry.register
class SecurityBoundaryAssessSkill(BaseSkill):
    name = "quality_assessment.security_boundary_assess"
    description = (
        "Assesses security boundary clarity (0–100) based on explicit security layers, "
        "authentication/authorization boundaries (JWT/OAuth/gateway), and data classification "
        "zones (bounded contexts, PII labels, encryption hints). "
        "A high score indicates well-defined, enforced security boundaries across all layers."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    tags = ["quality", "security", "authentication", "authorization", "data-classification", "architecture"]
    parameters = [
        SkillParameter("design_input", "Serialized NormalizedDesignInput dict.", type="object"),
        SkillParameter("solid_violations", "List of violated SOLID principle ids.", type="array"),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        solid_violations: list[str] | None = None,
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        result = _assess_security_boundary_clarity(inp, solid_violations or [])
        return SkillResult(
            success=True,
            summary=f"Security boundary clarity score: {result.score}",
            artifacts=[
                CodeArtifact(
                    filename="quality_security.json",
                    content=json.dumps(result.model_dump(), indent=2),
                    language="json",
                    description="Security boundary clarity assessment result",
                )
            ],
        )
