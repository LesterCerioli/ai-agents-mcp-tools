from src.architecture.schemas.requirements import ArchitectureRequirements, SpecificationStatus


_CLARIFICATION_QUESTIONS: dict[str, str] = {
    "scalability": (
        "How many concurrent users do you expect at peak load, "
        "and what is your projected growth over the next 12 months?"
    ),
    "availability": (
        "What is your acceptable downtime? Do you require high availability (99.9%+)? "
        "What are your Recovery Time Objective (RTO) and Recovery Point Objective (RPO) targets?"
    ),
    "compliance": (
        "Are there regulatory or compliance requirements? "
        "(e.g., GDPR for EU users, HIPAA for healthcare data, PCI-DSS for payment processing, SOC2 for SaaS)"
    ),
    "domain_boundaries": (
        "What is the primary business domain of this system? "
        "Are there distinct subdomains or bounded contexts that should be independently deployable?"
    ),
    "integration": (
        "What external systems or third-party services will this system integrate with? "
        "(e.g., payment gateways, identity providers, notification services, analytics platforms)"
    ),
    "budget": (
        "What is the infrastructure budget tier — startup, mid-market, or enterprise? "
        "Do you have a preferred cloud provider (AWS, GCP, Azure) or must it be cloud-agnostic?"
    ),
    "team_size": (
        "How large is the engineering team that will build and maintain this system, "
        "and what is the organization's maturity level (startup, scale-up, enterprise)?"
    ),
}


class ClarificationEngine:
    """Generates targeted clarification questions for missing or ambiguous requirement dimensions.

    SRP: responsible only for identifying gaps and producing questions — no extraction, no scoring.
    """

    def generate_questions(self, requirements: ArchitectureRequirements) -> list[str]:
        dims: dict[str, object] = {
            "scalability": requirements.scalability,
            "availability": requirements.availability,
            "compliance": requirements.compliance,
            "domain_boundaries": requirements.domain_boundaries,
            "integration": requirements.integration,
            "budget": requirements.budget,
            "team_size": requirements.team_size,
        }
        return [
            _CLARIFICATION_QUESTIONS[dim_name]
            for dim_name, dim in dims.items()
            if getattr(dim, "status", None) in (
                SpecificationStatus.NOT_SPECIFIED,
                SpecificationStatus.AMBIGUOUS,
            )
        ]
