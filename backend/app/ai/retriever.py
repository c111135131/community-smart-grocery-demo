"""Retrieval interface and a dependency-free local retriever (the "R" in RAG).

`Retriever` is the interface the rest of the AI layer depends on, so this simple
implementation can later be swapped for pgvector / embeddings without touching the
agent or the tools.

`KeywordRetriever` scores each knowledge entry as

    score = cosine(char-bigram TF-IDF of query, of entry)      0 .. 1
          + 0.75 * (number of the entry's keywords found in the query, max 3)
          + 0.50 * (number of the entry's tags requested by the caller, max 2)

Character bigrams are used because Chinese has no spaces between words. Ties are
broken by entry id, so results are fully deterministic and easy to explain.
"""
import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.ai.knowledge import KnowledgeEntry

KEYWORD_WEIGHT = 0.75
TAG_WEIGHT = 0.5
MAX_KEYWORD_HITS = 3
MAX_TAG_HITS = 2
MIN_SCORE = 0.2  # below this an entry is not considered relevant

_RUN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9]+")


@dataclass(frozen=True)
class Snippet:
    """A retrieved knowledge entry plus its relevance score."""

    id: str
    title: str
    text: str
    tags: tuple[str, ...]
    product_codes: tuple[int, ...]
    score: float


class Retriever(Protocol):
    def search(
        self, query: str, *, tags: Sequence[str] = (), limit: int = 3
    ) -> list[Snippet]: ...


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.casefold())


def _bigrams(text: str) -> list[str]:
    """Character bigrams inside each CJK / alphanumeric run (unigram for 1-char runs)."""
    grams: list[str] = []
    for run in _RUN_RE.findall(text.casefold()):
        if len(run) == 1:
            grams.append(run)
        else:
            grams.extend(run[i : i + 2] for i in range(len(run) - 1))
    return grams


class KeywordRetriever:
    def __init__(self, entries: Sequence[KnowledgeEntry]) -> None:
        self._entries = list(entries)
        docs = [_bigrams(f"{e.title} {e.text} {' '.join(e.keywords)}") for e in self._entries]
        n = len(docs)
        df: Counter[str] = Counter()
        for grams in docs:
            df.update(set(grams))
        self._idf = {g: math.log((n + 1) / (c + 1)) + 1.0 for g, c in df.items()}
        self._unseen_idf = math.log(n + 1) + 1.0
        self._vectors = [self._vector(grams) for grams in docs]

    def _vector(self, grams: list[str]) -> dict[str, float]:
        tf = Counter(grams)
        vec = {g: (1.0 + math.log(c)) * self._idf.get(g, self._unseen_idf) for g, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}

    def search(self, query: str, *, tags: Sequence[str] = (), limit: int = 3) -> list[Snippet]:
        qvec = self._vector(_bigrams(query))
        qnorm = _normalize(query)
        wanted = set(tags)
        scored: list[Snippet] = []
        for entry, dvec in zip(self._entries, self._vectors, strict=True):
            cosine = sum(w * dvec.get(g, 0.0) for g, w in qvec.items())
            hits = sum(1 for k in set(entry.keywords) if _normalize(k) and _normalize(k) in qnorm)
            tag_hits = len(wanted & set(entry.tags))
            score = (
                cosine
                + KEYWORD_WEIGHT * min(hits, MAX_KEYWORD_HITS)
                + TAG_WEIGHT * min(tag_hits, MAX_TAG_HITS)
            )
            if score >= MIN_SCORE:
                scored.append(
                    Snippet(
                        entry.id, entry.title, entry.text, tuple(entry.tags),
                        tuple(entry.product_codes), round(score, 4),
                    )
                )
        scored.sort(key=lambda s: (-s.score, s.id))
        return scored[: max(0, limit)]
