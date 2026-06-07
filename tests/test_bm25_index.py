import pytest
from src.llm.bm25_index import SkillBM25Index, SkillMatch

_MOCK_SKILLS: dict[str, list[dict]] = {
    "nextjs": [
        {
            "name": "nextjs.generate_component",
            "description": "Generate a production-ready Next.js component with TypeScript and Tailwind CSS.",
            "tags": ["component", "react", "typescript"],
        },
        {
            "name": "nextjs.auth",
            "description": "Implement authentication with NextAuth.js including login, signup and session management.",
            "tags": ["auth", "nextauth", "session", "login"],
        },
        {
            "name": "nextjs.routing",
            "description": "Set up App Router file-based routing with dynamic segments and route groups.",
            "tags": ["routing", "app-router", "pages"],
        },
    ],
    "design": [
        {
            "name": "design.color_system",
            "description": "Generate a complete color palette and design tokens for a brand or product.",
            "tags": ["color", "palette", "tokens", "brand"],
        },
        {
            "name": "design.tailwind",
            "description": "Configure Tailwind CSS with custom theme, plugins and design system integration.",
            "tags": ["tailwind", "css", "theme", "design-system"],
        },
    ],
    "vercel": [
        {
            "name": "vercel.deployment",
            "description": "Configure Vercel deployment settings, environment variables and build pipeline.",
            "tags": ["deployment", "vercel", "ci", "build"],
        },
    ],
}


@pytest.fixture
def index() -> SkillBM25Index:
    idx = SkillBM25Index()
    idx.build(_MOCK_SKILLS)
    return idx


def test_is_ready_after_build(index: SkillBM25Index) -> None:
    assert index.is_ready


def test_is_not_ready_before_build() -> None:
    assert not SkillBM25Index().is_ready


def test_auth_query_returns_auth_skill(index: SkillBM25Index) -> None:
    results = index.search("implement user authentication with login and session", top_k=3)
    assert results, "Expected at least one result"
    assert results[0].skill_name == "nextjs.auth"
    assert results[0].agent_name == "nextjs"


def test_color_query_returns_design_skill(index: SkillBM25Index) -> None:
    results = index.search("create a color palette and brand tokens", top_k=3)
    assert results
    assert results[0].skill_name == "design.color_system"


def test_deployment_query_returns_vercel_skill(index: SkillBM25Index) -> None:
    results = index.search("configure vercel deployment and build pipeline", top_k=3)
    assert results
    assert results[0].skill_name == "vercel.deployment"


def test_component_query_returns_component_skill(index: SkillBM25Index) -> None:
    results = index.search("generate a react typescript component", top_k=3)
    assert results
    assert results[0].skill_name == "nextjs.generate_component"


def test_unrelated_query_returns_empty(index: SkillBM25Index) -> None:
    results = index.search("quantum physics supercollider", top_k=5)
    assert results == []


def test_search_respects_top_k(index: SkillBM25Index) -> None:
    results = index.search("nextjs component routing auth", top_k=2)
    assert len(results) <= 2


def test_results_are_descending_by_score(index: SkillBM25Index) -> None:
    results = index.search("nextjs component auth routing tailwind", top_k=5)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_skill_match_fields_are_populated(index: SkillBM25Index) -> None:
    results = index.search("authentication login", top_k=1)
    assert results
    match = results[0]
    assert isinstance(match, SkillMatch)
    assert match.skill_name
    assert match.agent_name
    assert match.score > 0
    assert match.description
