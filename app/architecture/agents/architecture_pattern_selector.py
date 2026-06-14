
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.architecture.schemas.design_partner_plan import (
    DesignPartnerPlan,
    PartnerActivation,
    PartnerConfiguration,
    PartnerDimensionScore,
    PartnerScore,
    SelectionRationale,
)
from app.architecture.schemas.requirements import ArchitectureRequirements
from app.architecture.schemas.solution import ArchitecturePattern, SolutionArchitectureDecision

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Aptitude matrix — how well each design partner performs when a given
# requirement signal is at its maximum (1.0).
# Row = partner, Column = signal dimension.
# ---------------------------------------------------------------------------
_PARTNER_APTITUDE: dict[str, dict[str, float]] = {
    "microservices_design_partner": {
        "scalability_demand":      0.95,
        "large_team":              0.88,
        "domain_complexity":       0.62,
        "operational_maturity":    0.90,
        "time_to_market_pressure": 0.12,
    },
    "hexagonal_design_partner": {
        "scalability_demand":      0.48,
        "large_team":              0.60,
        "domain_complexity":       0.95,
        "operational_maturity":    0.65,
        "time_to_market_pressure": 0.38,
    },
    "monolith_design_partner": {
        "scalability_demand":      0.18,
        "large_team":              0.12,
        "domain_complexity":       0.28,
        "operational_maturity":    0.22,
        "time_to_market_pressure": 0.92,
    },
}

_DIMENSION_WEIGHTS: dict[str, float] = {
    "scalability_demand":      0.30,
    "large_team":              0.20,
    "domain_complexity":       0.25,
    "operational_maturity":    0.15,
    "time_to_market_pressure": 0.10,
}

# Precomputed theoretical maximum score for each partner (all signals = 1.0)
_PARTNER_MAX_SCORE: dict[str, float] = {
    partner: sum(
        _PARTNER_APTITUDE[partner][dim] * _DIMENSION_WEIGHTS[dim]
        for dim in _DIMENSION_WEIGHTS
    )
    for partner in _PARTNER_APTITUDE
}

_PATTERN_TO_PARTNER: dict[ArchitecturePattern, str] = {
    ArchitecturePattern.MICROSERVICES: "microservices_design_partner",
    ArchitecturePattern.EVENT_DRIVEN:  "microservices_design_partner",
    ArchitecturePattern.CQRS:          "microservices_design_partner",
    ArchitecturePattern.HEXAGONAL:     "hexagonal_design_partner",
    ArchitecturePattern.MONOLITH:      "monolith_design_partner",
    ArchitecturePattern.LAYERED:       "monolith_design_partner",
    ArchitecturePattern.SERVERLESS:    "monolith_design_partner",
}

_HYBRID_PAIR = frozenset({"microservices_design_partner", "hexagonal_design_partner"})
_HYBRID_MIN_SCORE = 0.65   # both partners must exceed this normalised threshold
_HYBRID_MAX_GAP   = 0.15   # maximum allowed gap between their scores


# ---------------------------------------------------------------------------
# Signal extraction — convert raw requirement fields to 0–1 numeric signals
# ---------------------------------------------------------------------------

def _parse_user_count(raw: str) -> int | None:
    m = re.search(r"([\d,.]+)\s*([mk]?)", raw)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = m.group(2).lower()
    if suffix == "m":
        return int(num * 1_000_000)
    if suffix == "k":
        return int(num * 1_000)
    return int(num)


def _scalability_signal(req: ArchitectureRequirements) -> float:
    raw = (req.scalability.expected_users or "").lower()
    count = _parse_user_count(raw) if raw else None
    if count is None:
        return 0.05
    if count >= 5_000_000:
        return 1.00
    if count >= 1_000_000:
        return 0.85
    if count >= 500_000:
        return 0.75
    if count >= 100_000:
        return 0.55
    if count >= 10_000:
        return 0.25
    return 0.10


def _team_size_signal(req: ArchitectureRequirements) -> float:
    
    raw = (req.team_size.engineering_team_size or "").lower()
    if any(kw in raw for kw in ["large", "enterprise", "100+", "50+"]):
        return 0.90
    if any(kw in raw for kw in ["medium", "20-50", "20+", "30+", "40+"]):
        return 0.65
    if any(kw in raw for kw in ["10-20", "15-20", "12-20"]):
        return 0.50
    if any(kw in raw for kw in ["small", "solo", "1-5", "2-5", "startup", "1-3", "2-3", "1-10", "5-10"]):
        return 0.15
    m = re.search(r"(\d+)", raw)
    if m:
        n = int(m.group(1))
        if n >= 50:
            return 0.90
        if n >= 20:
            return 0.65
        if n >= 10:
            return 0.50
        return 0.15
    return 0.30


def _domain_complexity_signal(req: ArchitectureRequirements) -> float:
    count = max(
        len(req.domain_boundaries.bounded_contexts or []),
        len(req.domain_boundaries.subdomains or []),
    )
    if count >= 10:
        return 1.00
    if count >= 6:
        return 0.80
    if count >= 4:
        return 0.65
    if count >= 2:
        return 0.45
    if count == 1:
        return 0.30
    return 0.15


def _operational_maturity_signal(req: ArchitectureRequirements) -> float:
    budget_tier = (req.budget.tier or "").lower()
    org_maturity = (req.team_size.organizational_maturity or "").lower()
    signals: list[float] = []

    if any(kw in budget_tier for kw in ["enterprise", "large"]):
        signals.append(0.90)
    elif any(kw in budget_tier for kw in ["mid", "growth", "scale", "market"]):
        signals.append(0.60)
    elif any(kw in budget_tier for kw in ["startup", "seed", "bootstrap", "low", "free"]):
        signals.append(0.20)

    if any(kw in org_maturity for kw in ["mature", "experienced", "senior", "expert"]):
        signals.append(0.90)
    elif any(kw in org_maturity for kw in ["medium", "growing", "intermediate"]):
        signals.append(0.60)
    elif any(kw in org_maturity for kw in ["junior", "early", "learning"]):
        signals.append(0.20)

    return sum(signals) / len(signals) if signals else 0.40


def _time_to_market_signal(req: ArchitectureRequirements) -> float:
    budget_tier = (req.budget.tier or "").lower()
    team_raw = (req.team_size.engineering_team_size or "").lower()

    is_startup_budget = any(kw in budget_tier for kw in ["startup", "seed", "bootstrap", "low", "free"])
    is_small_team = any(kw in team_raw for kw in ["small", "solo", "1-5", "2-5", "1-3", "startup"])

    if is_startup_budget and is_small_team:
        return 0.90
    if is_startup_budget:
        return 0.70
    if is_small_team:
        return 0.55
    if any(kw in budget_tier for kw in ["enterprise", "large"]):
        return 0.15
    return 0.35


def _extract_signals(req: ArchitectureRequirements) -> dict[str, float]:
    return {
        "scalability_demand":      _scalability_signal(req),
        "large_team":              _team_size_signal(req),
        "domain_complexity":       _domain_complexity_signal(req),
        "operational_maturity":    _operational_maturity_signal(req),
        "time_to_market_pressure": _time_to_market_signal(req),
    }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _compute_fitness(
    signals: dict[str, float],
    partner: str,
) -> tuple[float, list[PartnerDimensionScore]]:
    
    aptitude = _PARTNER_APTITUDE[partner]
    raw_score = 0.0
    dim_scores: list[PartnerDimensionScore] = []

    for dim, weight in _DIMENSION_WEIGHTS.items():
        s = signals[dim]
        a = aptitude[dim]
        contrib = s * a * weight
        raw_score += contrib
        dim_scores.append(
            PartnerDimensionScore(
                dimension=dim,
                signal_strength=round(s, 4),
                aptitude=a,
                contribution=round(contrib, 4),
            )
        )

    max_score = _PARTNER_MAX_SCORE[partner]
    fitness = round(raw_score / max_score, 4) if max_score > 0 else 0.0
    return fitness, dim_scores


def _primary_partner_name(decision: SolutionArchitectureDecision) -> str:
    primary = decision.primary_pattern
    if primary is None:
        return "monolith_design_partner"
    return _PATTERN_TO_PARTNER.get(primary.pattern, "monolith_design_partner")


def _secondary_partner_name(primary: str) -> str:
    
    for partner in _HYBRID_PAIR:
        if partner != primary:
            return partner
    return ""


def _should_activate_hybrid(
    primary_partner: str,
    scores: dict[str, float],
) -> bool:
    
    if primary_partner not in _HYBRID_PAIR:
        return False
    secondary = _secondary_partner_name(primary_partner)
    if not secondary:
        return False
    p_score = scores[primary_partner]
    s_score = scores[secondary]
    gap = abs(p_score - s_score)
    return (
        p_score >= _HYBRID_MIN_SCORE
        and s_score >= _HYBRID_MIN_SCORE
        and gap <= _HYBRID_MAX_GAP
    )


# ---------------------------------------------------------------------------
# Configuration resolver
# ---------------------------------------------------------------------------

def _resolve_configuration(
    partner: str,
    req: ArchitectureRequirements,
    signals: dict[str, float],
) -> PartnerConfiguration:
    contexts = req.domain_boundaries.bounded_contexts or []

    if partner == "microservices_design_partner":
        return PartnerConfiguration(
            partner_name=partner,
            parameters={
                "service_count_threshold": max(3, len(contexts)),
                "use_service_mesh": len(contexts) > 5 or signals["scalability_demand"] > 0.70,
                "event_driven_mode": (
                    req.integration.real_time is True
                    or signals["scalability_demand"] > 0.80
                ),
                "module_granularity_level": (
                    "fine" if signals["domain_complexity"] > 0.60 else "coarse"
                ),
            },
        )

    if partner == "hexagonal_design_partner":
        return PartnerConfiguration(
            partner_name=partner,
            parameters={
                "module_granularity": (
                    "fine" if signals["domain_complexity"] > 0.60 else "coarse"
                ),
                "strict_port_isolation": bool(req.compliance.frameworks),
                "bounded_context_count": len(contexts),
            },
        )

    # monolith_design_partner
    return PartnerConfiguration(
        partner_name=partner,
        parameters={
            "module_style": (
                "feature_modules" if signals["domain_complexity"] > 0.40 else "layered"
            ),
            "embedded_db": False,
            "target_module_count": max(3, len(contexts)),
        },
    )


# ---------------------------------------------------------------------------
# Rationale builder
# ---------------------------------------------------------------------------

_REJECTION_TEMPLATES: dict[str, dict[str, str]] = {
    "microservices_design_partner": {
        "monolith_design_partner": (
            "Rejected: low scalability demand and time-to-market pressure favour a "
            "simpler deployable unit over distributed service complexity."
        ),
        "hexagonal_design_partner": (
            "Rejected: domain complexity signal is insufficient to justify the "
            "ports-and-adapters overhead; microservices suffices for scale isolation."
        ),
    },
    "hexagonal_design_partner": {
        "microservices_design_partner": (
            "Rejected: scalability demand does not require independent service deployment; "
            "hexagonal architecture provides sufficient domain isolation within a single process."
        ),
        "monolith_design_partner": (
            "Rejected: domain complexity signal is insufficient to justify hexagonal "
            "overhead; a simpler layered approach is more cost-effective."
        ),
    },
    "monolith_design_partner": {
        "microservices_design_partner": (
            "Rejected: scale and team-size signals do not justify the operational "
            "overhead of a distributed system at this stage."
        ),
        "hexagonal_design_partner": (
            "Rejected: domain complexity is low; hexagonal ports-and-adapters overhead "
            "is not warranted for this requirement profile."
        ),
    },
}


def _build_partner_scores(
    all_scores: dict[str, tuple[float, list[PartnerDimensionScore]]],
    selected_names: set[str],
    primary_partner: str,
) -> list[PartnerScore]:
    result: list[PartnerScore] = []
    for partner, (fitness, dim_scores) in all_scores.items():
        selected = partner in selected_names
        rejection_reason: str | None = None
        if not selected:
            templates = _REJECTION_TEMPLATES.get(primary_partner, {})
            rejection_reason = templates.get(
                partner,
                f"Fitness score {fitness:.2f} below activation threshold for this requirement profile.",
            )
        result.append(
            PartnerScore(
                partner_name=partner,
                fitness_score=fitness,
                dimension_scores=dim_scores,
                selected=selected,
                rejection_reason=rejection_reason,
            )
        )
    # Consistent ordering: highest score first
    result.sort(key=lambda s: s.fitness_score, reverse=True)
    return result


def _dominant_signals(signals: dict[str, float]) -> list[str]:
    threshold = 0.55
    return [dim for dim, val in signals.items() if val >= threshold]


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class ArchitecturePatternSelector:
    """Translates a SolutionArchitectureDecision into a DesignPartnerPlan.

    For each invocation:
    1. Extracts requirement signals (scalability, team size, domain complexity,
       operational maturity, time-to-market pressure).
    2. Scores all three design partners via the aptitude matrix.
    3. Determines whether hybrid activation is warranted.
    4. Resolves per-partner configuration parameters.
    5. Produces a DesignPartnerPlan with a full SelectionRationale including
       per-pattern scores and rejection reasons for non-selected partners.

    The scoring matrix is purely deterministic — identical inputs always produce
    identical outputs.
    """

    def select(
        self,
        decision: SolutionArchitectureDecision,
        requirements: ArchitectureRequirements,
    ) -> DesignPartnerPlan:
        signals = _extract_signals(requirements)

        # Score all partners
        raw_scores: dict[str, tuple[float, list[PartnerDimensionScore]]] = {}
        fitness_map: dict[str, float] = {}
        for partner in _PARTNER_APTITUDE:
            fitness, dim_scores = _compute_fitness(signals, partner)
            raw_scores[partner] = (fitness, dim_scores)
            fitness_map[partner] = fitness

        primary_partner = _primary_partner_name(decision)
        is_hybrid = _should_activate_hybrid(primary_partner, fitness_map)

        # Build activation list
        activations: list[PartnerActivation] = []
        selected_names: set[str] = set()

        # Primary activation
        primary_config = _resolve_configuration(primary_partner, requirements, signals)
        primary_rationale = (
            f"Primary partner selected from decision pattern "
            f"'{decision.primary_pattern.pattern.value if decision.primary_pattern else 'unknown'}'. "
            f"Fitness score: {fitness_map[primary_partner]:.2f}."
        )
        activations.append(
            PartnerActivation(
                partner_name=primary_partner,
                activation_order=1,
                configuration=primary_config,
                rationale=primary_rationale,
            )
        )
        selected_names.add(primary_partner)

        # Secondary activation (hybrid only)
        if is_hybrid:
            secondary_partner = _secondary_partner_name(primary_partner)
            if secondary_partner:
                secondary_config = _resolve_configuration(
                    secondary_partner, requirements, signals
                )
                activations.append(
                    PartnerActivation(
                        partner_name=secondary_partner,
                        activation_order=2,
                        configuration=secondary_config,
                        rationale=(
                            f"Hybrid secondary: both scalability demand "
                            f"({signals['scalability_demand']:.2f}) and domain complexity "
                            f"({signals['domain_complexity']:.2f}) exceed hybrid thresholds. "
                            f"Fitness score: {fitness_map[secondary_partner]:.2f}."
                        ),
                    )
                )
                selected_names.add(secondary_partner)

        # Build per-partner scores with rejection reasons
        partner_scores = _build_partner_scores(raw_scores, selected_names, primary_partner)

        # Dominant signals for summary
        dominant = _dominant_signals(signals)

        hybrid_reason: str | None = None
        if is_hybrid:
            secondary = _secondary_partner_name(primary_partner)
            hybrid_reason = (
                f"Both '{primary_partner}' (score: {fitness_map[primary_partner]:.2f}) and "
                f"'{secondary}' (score: {fitness_map.get(secondary, 0):.2f}) "
                f"exceed the hybrid threshold ({_HYBRID_MIN_SCORE}) with a gap of "
                f"{abs(fitness_map[primary_partner] - fitness_map.get(secondary, 0)):.2f} "
                f"(<= {_HYBRID_MAX_GAP}). High scalability demand combined with high domain "
                f"complexity warrants activating both partners."
            )

        rationale = SelectionRationale(
            summary=(
                f"Selected {'hybrid: ' + ' + '.join(sorted(selected_names)) if is_hybrid else primary_partner}. "
                f"Dominant requirement signals: {', '.join(dominant) if dominant else 'none above threshold'}."
            ),
            per_partner_scores=partner_scores,
            primary_signals=dominant,
            hybrid_reason=hybrid_reason,
        )

        return DesignPartnerPlan(
            decision_id=decision.decision_id,
            selected_partners=activations,
            is_hybrid=is_hybrid,
            rationale=rationale,
            scoring_deterministic=True,
        )
