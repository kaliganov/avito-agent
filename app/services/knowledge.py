"""
Загрузка скриптов ответов из knowledge/scripts/*.md
Формат файла: YAML frontmatter (опционально) + текст.
Поиск: простое совпадение ключевых слов + релевантность по пересечению с запросом.
"""

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class ScriptChunk:
    title: str
    body: str
    keywords: frozenset[str]
    filename: str = ""


def _split_words(text: str) -> set[str]:
    text = text.lower()
    words = re.findall(r"[а-яёa-z0-9]+", text)
    return set(words)


def _load_md_files(scripts_dir: Path) -> list[ScriptChunk]:
    if not scripts_dir.is_dir():
        return []
    chunks: list[ScriptChunk] = []
    for path in sorted(scripts_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title = path.stem.replace("_", " ")
        body = raw.strip()
        # Первая строка как заголовок, если похоже на # Title
        if body.startswith("#"):
            first, _, rest = body.partition("\n")
            title = first.lstrip("#").strip() or title
            body = rest.strip()
        kw = _split_words(title + " " + body)
        chunks.append(ScriptChunk(title=title, body=body, keywords=kw, filename=path.name))
    return chunks


class KnowledgeBase:
    def __init__(self, scripts_dir: Path | None = None) -> None:
        base = Path(__file__).resolve().parents[2] / "knowledge" / "scripts"
        self._dir = scripts_dir or base
        self._chunks: list[ScriptChunk] = _load_md_files(self._dir)

    def reload(self) -> None:
        self._chunks = _load_md_files(self._dir)

    def retrieve(self, user_message: str, top_k: int = 3) -> list[str]:
        if not self._chunks:
            return []
        # Файлы 00_*.md — база контекста, подмешиваются всегда
        always = [c for c in self._chunks if c.filename.startswith("00_")]
        rest = [c for c in self._chunks if not c.filename.startswith("00_")]

        q = _split_words(user_message)
        if not q:
            picked = rest[:top_k] if rest else self._chunks[:top_k]
            parts = [f"### {c.title}\n{c.body}" for c in always + picked]
            return parts[: top_k + len(always)]

        scored: list[tuple[int, ScriptChunk]] = []
        for c in rest:
            overlap = len(q & c.keywords)
            scored.append((overlap, c))
        scored.sort(key=lambda x: (-x[0], x[1].title))
        out: list[str] = []
        for a in always:
            out.append(f"### {a.title}\n{a.body}")
        for score, chunk in scored[:top_k]:
            if score > 0 or len(scored) == 1:
                out.append(f"### {chunk.title}\n{chunk.body}")
        if scored and len(out) == len(always):
            out.append(f"### {scored[0][1].title}\n{scored[0][1].body}")
        elif not scored and rest:
            out.append(f"### {rest[0].title}\n{rest[0].body}")
        return out
