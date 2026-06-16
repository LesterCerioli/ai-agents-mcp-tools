import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ComplianceLevel(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"


class SOLIDPrinciple(str, Enum):
    SRP = "srp"
    OCP = "ocp"
    LSP = "lsp"
    ISP = "isp"
    DIP = "dip"


PRINCIPLE_NAMES: dict[SOLIDPrinciple, str] = {
    SOLIDPrinciple.SRP: "Single Responsibility Principle",
    SOLIDPrinciple.OCP: "Open/Closed Principle",
    SOLIDPrinciple.LSP: "Liskov Substitution Principle",
    SOLIDPrinciple.ISP: "Interface Segregation Principle",
    SOLIDPrinciple.DIP: "Dependency Inversion Principle",
}


class AffectedComponent(BaseModel):
    component_name: str
    violation_description: str
    layer: str = ""
    component_type: str = ""


class PrincipleResult(BaseModel):
    principle: SOLIDPrinciple
    compliance_level: ComplianceLevel
    affected_components: list[AffectedComponent] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""


class CrossPrincipleCorrelation(BaseModel):
    primary_principle: SOLIDPrinciple
    cascaded_principles: list[SOLIDPrinciple]
    component_name: str
    description: str


class SOLIDComplianceReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    principle_results: list[PrincipleResult] = Field(default_factory=list)
    cross_principle_correlations: list[CrossPrincipleCorrelation] = Field(default_factory=list)
    overall_compliance: ComplianceLevel = ComplianceLevel.COMPLIANT
    components_analyzed: int = 0
    analysis_summary: str = ""
    architecture_pattern: str = ""

    def get_result(self, principle: SOLIDPrinciple) -> "PrincipleResult | None":
        return next((r for r in self.principle_results if r.principle == principle), None)


_INFRA_KEYWORDS: frozenset[str] = frozenset({
    "postgresql", "mysql", "mariadb", "mongodb", "sqlite", "oracle", "sqlserver",
    "redis", "memcached", "elasticsearch", "opensearch",
    "kafka", "rabbitmq", "activemq", "sqs", "pubsub",
    "s3", "blob", "gcs", "minio",
})

_MULTI_RESPONSIBILITY_INDICATORS: tuple[str, ...] = (
    " and ", " also ", " as well as ", " in addition ", " plus ", " additionally ",
    " while ", " along with ", " together with ",
)


@dataclass
class NormalizedDesignInput:
    """Normalized representation of any architecture artifact for SOLID analysis."""

    pattern: str = ""
    domain: str = ""
    components: list[dict[str, Any]] = field(default_factory=list)
    modules: list[dict[str, Any]] = field(default_factory=list)
    ports: list[dict[str, Any]] = field(default_factory=list)
    bounded_contexts: list[dict[str, Any]] = field(default_factory=list)
    domain_services: list[dict[str, Any]] = field(default_factory=list)
    has_gateway: bool = False
    has_repositories: bool = False
    has_ports_and_adapters: bool = False
    has_shared_database: bool = False
    service_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "domain": self.domain,
            "components": self.components,
            "modules": self.modules,
            "ports": self.ports,
            "bounded_contexts": self.bounded_contexts,
            "domain_services": self.domain_services,
            "has_gateway": self.has_gateway,
            "has_repositories": self.has_repositories,
            "has_ports_and_adapters": self.has_ports_and_adapters,
            "has_shared_database": self.has_shared_database,
            "service_count": self.service_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NormalizedDesignInput":
        return cls(
            pattern=data.get("pattern", ""),
            domain=data.get("domain", ""),
            components=data.get("components", []),
            modules=data.get("modules", []),
            ports=data.get("ports", []),
            bounded_contexts=data.get("bounded_contexts", []),
            domain_services=data.get("domain_services", []),
            has_gateway=data.get("has_gateway", False),
            has_repositories=data.get("has_repositories", False),
            has_ports_and_adapters=data.get("has_ports_and_adapters", False),
            has_shared_database=data.get("has_shared_database", False),
            service_count=data.get("service_count", 0),
        )
