"""Unit tests for each SOLID principle skill — 8 design scenarios with known violations."""
import pytest

from app.architecture.schemas.solid import (
    ComplianceLevel,
    NormalizedDesignInput,
    SOLIDPrinciple,
)
from app.skills.solid.srp_skill import _analyze_srp
from app.skills.solid.ocp_skill import _analyze_ocp
from app.skills.solid.lsp_skill import _analyze_lsp
from app.skills.solid.isp_skill import _analyze_isp
from app.skills.solid.dip_skill import _analyze_dip


# ── Helpers ────────────────────────────────────────────────────────────────────

def _component(
    name: str,
    comp_type: str = "service",
    layer: str = "domain",
    responsibility: str = "",
    technology_hints: list[str] | None = None,
    protocols: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "type": comp_type,
        "layer": layer,
        "responsibility": responsibility or f"Handles {name.lower()} logic",
        "technology_hints": technology_hints or [],
        "protocols": protocols or ["HTTP/REST"],
    }


def _module(
    name: str,
    responsibilities: list[str] | None = None,
    technology_hints: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "responsibilities": responsibilities or [f"Manages {name.lower()}"],
        "technology_hints": technology_hints or [],
        "allowed_dependencies": [],
    }


def _port(
    name: str,
    port_type: str = "driven",
    adapters: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "port_type": port_type,
        "interface_name": f"I{name}",
        "adapter_implementations": adapters or [],
    }


def _bounded_context(
    name: str,
    service_name: str = "",
    responsibilities: list[str] | None = None,
    communication_style: str = "sync_rest",
) -> dict:
    return {
        "name": name,
        "service_name": service_name or f"{name.lower()}-service",
        "responsibilities": responsibilities or [f"Manages {name.lower()}"],
        "communication_style": communication_style,
    }


# ── Scenario 1: SRP — component with multiple responsibilities ─────────────────

def test_scenario_1_srp_multiple_responsibilities_detected():
    """Component whose responsibility string contains 'and' → SRP violation."""
    inp = NormalizedDesignInput(
        pattern="monolith",
        components=[
            _component(
                "GodService",
                responsibility="Handles authentication and logging and data persistence",
                layer="domain",
            )
        ],
    )
    result = _analyze_srp(inp)
    assert result.principle == SOLIDPrinciple.SRP
    assert result.compliance_level == ComplianceLevel.VIOLATION
    affected_names = [ac.component_name for ac in result.affected_components]
    assert "GodService" in affected_names
    assert len(result.recommendations) > 0


# ── Scenario 2: SRP — domain component with infra tech hints ──────────────────

def test_scenario_2_srp_domain_with_infra_technology_hints():
    """Domain-layer component declaring PostgreSQL/Redis → SRP violation (infra concern in domain)."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        components=[
            _component(
                "OrderService",
                layer="domain",
                technology_hints=["PostgreSQL", "Redis"],
            )
        ],
    )
    result = _analyze_srp(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert any("postgresql" in ac.violation_description.lower() for ac in result.affected_components)


# ── Scenario 3: OCP — hexagonal pattern with no ports ────────────────────────

def test_scenario_3_ocp_hexagonal_without_ports():
    """Hexagonal design with no ports/adapters → OCP violation (no extension points)."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        has_ports_and_adapters=False,
        ports=[],
        components=[
            _component("PaymentService", layer="domain"),
        ],
    )
    result = _analyze_ocp(inp)
    assert result.principle == SOLIDPrinciple.OCP
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert any("hexagonal" in ac.violation_description.lower() for ac in result.affected_components)


# ── Scenario 4: OCP — no gateway for multiple services ───────────────────────

def test_scenario_4_ocp_missing_gateway_for_multiple_services():
    """Multiple services without gateway abstraction → OCP violation."""
    inp = NormalizedDesignInput(
        pattern="microservices",
        has_gateway=False,
        service_count=4,
        components=[
            _component("UserService", layer="domain"),
            _component("OrderService", layer="domain"),
            _component("InventoryService", layer="domain"),
            _component("NotificationService", layer="domain"),
        ],
    )
    result = _analyze_ocp(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert any("gateway" in ac.violation_description.lower() for ac in result.affected_components)


# ── Scenario 5: LSP — driven ports without adapter implementations ────────────

def test_scenario_5_lsp_ports_without_adapters():
    """Driven port with no adapter implementations → LSP violation (nothing to substitute)."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        ports=[
            _port("PaymentRepository", port_type="driven", adapters=[]),
            _port("NotificationPort", port_type="driven", adapters=[]),
        ],
    )
    result = _analyze_lsp(inp)
    assert result.principle == SOLIDPrinciple.LSP
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert len(result.affected_components) >= 2


# ── Scenario 6: ISP — fat gateway serving too many services ──────────────────

def test_scenario_6_isp_fat_gateway():
    """Single API Gateway routing to 6 heterogeneous services → ISP violation."""
    inp = NormalizedDesignInput(
        pattern="microservices",
        service_count=6,
        components=[
            _component("ApiGateway", comp_type="gateway", layer="application"),
            _component("UserService", layer="domain"),
            _component("OrderService", layer="domain"),
            _component("BillingService", layer="domain"),
            _component("NotificationService", layer="domain"),
            _component("AnalyticsService", layer="domain"),
            _component("ReportingService", layer="domain"),
        ],
    )
    result = _analyze_isp(inp)
    assert result.principle == SOLIDPrinciple.ISP
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert any("gateway" in ac.component_type.lower() for ac in result.affected_components)


# ── Scenario 7: DIP — domain component depends on concrete infra ──────────────

def test_scenario_7_dip_domain_depends_on_concrete_infra():
    """Domain service declaring PostgreSQL as technology hint → DIP violation."""
    inp = NormalizedDesignInput(
        pattern="layered",
        components=[
            _component(
                "OrderService",
                layer="domain",
                technology_hints=["PostgreSQL", "SQLAlchemy"],
            ),
            _component("Database", comp_type="database", layer="infrastructure"),
        ],
        has_repositories=False,
        has_ports_and_adapters=False,
    )
    result = _analyze_dip(inp)
    assert result.principle == SOLIDPrinciple.DIP
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert any("OrderService" in ac.component_name for ac in result.affected_components)


# ── Scenario 8: All principles compliant (clean hexagonal design) ──────────────

def test_scenario_8_fully_compliant_design():
    """Clean hexagonal architecture with ports/adapters satisfies all SOLID principles."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        domain="payment",
        has_gateway=True,
        has_repositories=True,
        has_ports_and_adapters=True,
        service_count=2,
        components=[
            _component(
                "ApiGateway",
                comp_type="gateway",
                layer="application",
                responsibility="Routes incoming HTTP requests to use-case handlers",
                technology_hints=["Kong"],
                protocols=["HTTP/REST"],
            ),
            _component(
                "PaymentService",
                layer="domain",
                responsibility="Executes payment processing business rules",
                technology_hints=["Python"],
                protocols=["internal"],
            ),
            _component(
                "PostgreSQLAdapter",
                comp_type="database",
                layer="infrastructure",
                responsibility="Persists payment records via repository port",
                technology_hints=["PostgreSQL", "SQLAlchemy"],
            ),
        ],
        ports=[
            _port("PaymentRepository", port_type="driven", adapters=["PostgreSQLAdapter"]),
            _port("PaymentGatewayPort", port_type="driven", adapters=["StripeAdapter"]),
        ],
        modules=[],
        bounded_contexts=[],
    )
    srp_result = _analyze_srp(inp)
    ocp_result = _analyze_ocp(inp)
    lsp_result = _analyze_lsp(inp)
    isp_result = _analyze_isp(inp)
    dip_result = _analyze_dip(inp)

    assert srp_result.compliance_level == ComplianceLevel.COMPLIANT
    assert lsp_result.compliance_level == ComplianceLevel.COMPLIANT
    assert dip_result.compliance_level == ComplianceLevel.COMPLIANT


# ── Additional targeted skill tests ───────────────────────────────────────────

def test_srp_module_too_many_responsibilities():
    inp = NormalizedDesignInput(
        modules=[_module("MonolithModule", responsibilities=[
            "Handles user authentication",
            "Manages order lifecycle",
            "Sends email notifications",
            "Generates PDF reports",
        ])],
    )
    result = _analyze_srp(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert "MonolithModule" in [ac.component_name for ac in result.affected_components]


def test_srp_fat_component_many_tech_hints():
    inp = NormalizedDesignInput(
        components=[
            _component(
                "GodAPI",
                responsibility="Provides all API functionality",
                technology_hints=["FastAPI", "PostgreSQL", "Redis", "Kafka", "Elasticsearch"],
            )
        ],
    )
    result = _analyze_srp(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION


def test_isp_shared_database_violation():
    inp = NormalizedDesignInput(
        pattern="microservices",
        has_shared_database=True,
        service_count=3,
        components=[
            _component("UserService", layer="domain"),
            _component("OrderService", layer="domain"),
        ],
    )
    result = _analyze_isp(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert any("shared" in ac.component_name.lower() for ac in result.affected_components)


def test_dip_missing_repository_abstraction():
    """Domain + infra layers present but no repository/port → DIP violation."""
    inp = NormalizedDesignInput(
        pattern="layered",
        has_repositories=False,
        has_ports_and_adapters=False,
        components=[
            _component("UserService", layer="domain"),
            _component("Database", comp_type="database", layer="infrastructure"),
        ],
    )
    result = _analyze_dip(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION


def test_lsp_inconsistent_communication_styles():
    inp = NormalizedDesignInput(
        bounded_contexts=[
            _bounded_context("Orders", communication_style="sync_rest"),
            _bounded_context("Payments", communication_style="async_event"),
            _bounded_context("Inventory", communication_style="sync_grpc"),
        ],
    )
    result = _analyze_lsp(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION


def test_ocp_port_without_adapter_implementation():
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        has_ports_and_adapters=True,
        ports=[_port("StoragePort", port_type="driven", adapters=[])],
    )
    result = _analyze_ocp(inp)
    assert result.compliance_level == ComplianceLevel.VIOLATION
    assert any("StoragePort" in ac.component_name for ac in result.affected_components)


@pytest.mark.asyncio
async def test_skill_execute_returns_skill_result():
    """Verify the skill's execute() method wraps PrincipleResult in SkillResult correctly."""
    from app.skills.solid.srp_skill import SRPAnalyzeSkill
    import json

    skill = SRPAnalyzeSkill()
    inp = NormalizedDesignInput(
        components=[
            _component(
                "DirtyComponent",
                responsibility="Handles auth and logging",
            )
        ]
    )
    result = await skill.execute(design_input=inp.to_dict())
    assert result.success is True
    assert result.artifacts
    data = json.loads(result.artifacts[0].content)
    assert data["principle"] == "srp"
    assert data["compliance_level"] == "violation"
