"""Unit tests for individual quality assessment skills."""
import json
import pytest

import app.skills.quality_assessment  # noqa: F401 — registers skills

from app.architecture.schemas.solid import NormalizedDesignInput
from app.skills.registry import SkillRegistry


def _hexagonal_input() -> dict:
    return NormalizedDesignInput(
        pattern="hexagonal",
        components=[
            {
                "name": "APIGateway",
                "type": "gateway",
                "layer": "presentation",
                "responsibility": "Routes requests.",
                "technology_hints": ["Kong"],
                "protocols": ["HTTP/REST"],
            },
            {
                "name": "OrderService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Manages orders.",
                "technology_hints": [],
                "protocols": [],
            },
        ],
        has_gateway=True,
        has_repositories=True,
        has_ports_and_adapters=True,
        service_count=2,
    ).to_dict()


def _monolith_input() -> dict:
    return NormalizedDesignInput(
        pattern="monolith",
        components=[
            {
                "name": "GodClass",
                "type": "service",
                "layer": "domain",
                "responsibility": "Does everything and also manages DB and along with caching.",
                "technology_hints": ["PostgreSQL", "Redis", "Kafka", "S3", "Elasticsearch"],
                "protocols": [],
            }
        ],
        has_gateway=False,
        has_repositories=False,
        has_ports_and_adapters=False,
        has_shared_database=True,
    ).to_dict()


# ── Maintainability ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_maintainability_compliant_scores_high():
    skill = SkillRegistry.get("quality_assessment.maintainability_assess")
    result = await skill.execute(
        design_input=_hexagonal_input(),
        solid_violations=[],
        solid_warnings=[],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] >= 80.0


@pytest.mark.asyncio
async def test_maintainability_violations_reduce_score():
    skill = SkillRegistry.get("quality_assessment.maintainability_assess")
    result = await skill.execute(
        design_input=_monolith_input(),
        solid_violations=["srp", "ocp"],
        solid_warnings=[],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] < 80.0


# ── Extensibility ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extensibility_compliant_hexagonal_scores_high():
    skill = SkillRegistry.get("quality_assessment.extensibility_assess")
    result = await skill.execute(
        design_input=_hexagonal_input(),
        solid_violations=[],
        solid_warnings=[],
        architecture_style="hexagonal",
        pattern_names=["strategy", "decorator"],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] >= 80.0


@pytest.mark.asyncio
async def test_extensibility_dip_ocp_violations_reduce_score():
    skill = SkillRegistry.get("quality_assessment.extensibility_assess")
    result = await skill.execute(
        design_input=_monolith_input(),
        solid_violations=["ocp", "dip"],
        solid_warnings=[],
        architecture_style="monolith",
        pattern_names=[],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] < 50.0


# ── Testability ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_testability_ports_and_adapters_bonus():
    skill = SkillRegistry.get("quality_assessment.testability_assess")
    result = await skill.execute(
        design_input=_hexagonal_input(),
        solid_violations=[],
        solid_warnings=[],
        pattern_names=["abstract_factory"],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] >= 90.0


@pytest.mark.asyncio
async def test_testability_isp_dip_violations_reduce_score():
    skill = SkillRegistry.get("quality_assessment.testability_assess")
    result = await skill.execute(
        design_input=_monolith_input(),
        solid_violations=["isp", "dip"],
        solid_warnings=[],
        pattern_names=[],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] < 50.0


# ── Scalability ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scalability_microservices_with_cqrs_scores_high():
    ms_input = NormalizedDesignInput(
        pattern="microservices",
        has_gateway=True,
        service_count=5,
        has_shared_database=False,
    ).to_dict()
    skill = SkillRegistry.get("quality_assessment.scalability_assess")
    result = await skill.execute(
        design_input=ms_input,
        architecture_style="microservices",
        pattern_names=["cqrs", "event_sourcing", "saga"],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] >= 80.0


@pytest.mark.asyncio
async def test_scalability_monolith_shared_db_scores_low():
    skill = SkillRegistry.get("quality_assessment.scalability_assess")
    result = await skill.execute(
        design_input=_monolith_input(),
        architecture_style="monolith",
        pattern_names=[],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] < 55.0


# ── Security Boundary Clarity ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_security_boundary_full_features_scores_high():
    skill = SkillRegistry.get("quality_assessment.security_boundary_assess")
    result = await skill.execute(
        design_input=_hexagonal_input(),
        solid_violations=[],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] >= 80.0


@pytest.mark.asyncio
async def test_security_boundary_no_gateway_reduces_score():
    skill = SkillRegistry.get("quality_assessment.security_boundary_assess")
    result = await skill.execute(
        design_input=_monolith_input(),
        solid_violations=["srp"],
    )
    assert result.success
    data = json.loads(result.artifacts[0].content)
    assert data["score"] < 60.0


# ── Registry ──────────────────────────────────────────────────────────────────

def test_all_five_quality_skills_registered():
    expected = {
        "quality_assessment.maintainability_assess",
        "quality_assessment.extensibility_assess",
        "quality_assessment.testability_assess",
        "quality_assessment.scalability_assess",
        "quality_assessment.security_boundary_assess",
    }
    registered = set(SkillRegistry.names())
    assert expected.issubset(registered), (
        f"Missing quality skills: {expected - registered}"
    )
