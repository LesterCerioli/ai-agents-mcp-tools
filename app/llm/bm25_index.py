import re
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@dataclass
class SkillMatch:
    skill_name: str
    agent_name: str
    score: float
    description: str


class SkillBM25Index:
    """In-memory BM25 index over skill name + description + tags. Zero API calls."""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._entries: list[tuple[str, dict[str, Any]]] = []

    def build(self, skills_by_agent: dict[str, list[dict[str, Any]]]) -> None:
        self._entries = [
            (agent_name, skill)
            for agent_name, skills in skills_by_agent.items()
            for skill in skills
        ]
        corpus = [
            _tokenize(
                f"{skill['name']} {skill['description']} {' '.join(skill.get('tags', []))}"
            )
            for _, skill in self._entries
        ]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 5) -> list[SkillMatch]:
        if self._bm25 is None or not self._entries:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: list[SkillMatch] = []
        for idx, score in ranked[:top_k]:
            if score <= 0:
                break
            agent_name, skill = self._entries[idx]
            results.append(
                SkillMatch(
                    skill_name=skill["name"],
                    agent_name=agent_name,
                    score=float(score),
                    description=skill.get("description", ""),
                )
            )
        return results

    @property
    def is_ready(self) -> bool:
        return self._bm25 is not None and len(self._entries) > 0
