from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["concepts"])

CONCEPTS_DIR = Path(__file__).resolve().parent.parent.parent / "concepts"


def _parse_frontmatter(content: str) -> dict[str, str]:
    fm: dict[str, str] = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            raw = content[3:end].strip()
            for line in raw.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    fm[key.strip()] = val.strip().strip('"')
    return fm


def _strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3 :].strip()
    return content


@router.get("/api/v1/concepts")
async def get_concepts() -> list[dict[str, str]]:
    if not CONCEPTS_DIR.exists():
        return []
    cards: list[dict[str, str]] = []
    for md_file in sorted(CONCEPTS_DIR.glob("*.md")):
        content = md_file.read_text()
        card_id = md_file.stem
        frontmatter = _parse_frontmatter(content)
        title = frontmatter.get("title", card_id.replace("-", " ").title())
        difficulty = frontmatter.get("difficulty", "beginner")
        cards.append(
            {
                "id": card_id,
                "title": title,
                "difficulty": difficulty,
            }
        )
    return cards


@router.get("/api/v1/concepts/{concept_id}")
async def get_concept_content(concept_id: str) -> dict[str, str]:
    md_path = CONCEPTS_DIR / f"{concept_id}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Concept not found")
    content = md_path.read_text()
    body = _strip_frontmatter(content)
    return {"id": concept_id, "content": body}
