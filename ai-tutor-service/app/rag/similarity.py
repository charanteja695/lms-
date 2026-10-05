"""Scoring: dense (cosine over embeddings) and the lexical fallback used when embeddings are unavailable."""

import math
import re
from collections import Counter
from collections.abc import Sequence

import numpy as np

_WORD = re.compile(r"[a-z0-9_+#.]{2,}")
_STOPWORDS = frozenset(
    "the a an and or but if then of to in on at for from by with as is are was were be been it its this that these those "
    "i me my we you your he she they them do does did done can could should would will may might how what why when where "
    "which who whom not no yes so than too very just about into over under again also".split()
)


def tokenize(text: str) -> list[str]:
    return [w.strip(".") for w in _WORD.findall(text.lower()) if w.strip(".") not in _STOPWORDS and len(w.strip(".")) > 1]


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    result: np.ndarray = matrix / norms
    return result


def cosine_scores(query: Sequence[float], normalized: np.ndarray) -> np.ndarray:
    """Cosine similarity of ``query`` against every row of an already row-normalised matrix."""
    vector = np.asarray(query, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm == 0 or normalized.shape[0] == 0 or vector.shape[0] != normalized.shape[1]:
        return np.zeros(normalized.shape[0], dtype=np.float32)
    return np.asarray(normalized @ (vector / norm), dtype=np.float32)


def top_k(scores: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Indexes and scores of the ``k`` highest scores, best first (stable for ties: the earlier row wins)."""
    if scores.size == 0:
        return []
    order = sorted(range(scores.size), key=lambda i: (-float(scores[i]), i))[:k]
    return [(i, float(scores[i])) for i in order]


class LexicalIndex:
    """Inverse-document-frequency-weighted word overlap: the share of the question's (rare-word-weighted) vocabulary a
    passage contains, 0..1. Deliberately simple — it exists so the tutor degrades to "still finds the right lesson"
    rather than to "cannot answer" when the embedding service is down."""

    def __init__(self, documents: Sequence[str]) -> None:
        self._tokens = [Counter(tokenize(d)) for d in documents]
        frequency: Counter[str] = Counter()
        for tokens in self._tokens:
            frequency.update(tokens.keys())
        n = max(len(documents), 1)
        self._idf = {word: math.log(1 + n / count) for word, count in frequency.items()}

    def scores(self, query: str) -> np.ndarray:
        words = set(tokenize(query))
        if not words:
            return np.zeros(len(self._tokens), dtype=np.float32)
        # A question word no passage contains counts as the rarest possible word: it stays in the denominator, so
        # "how does quantum recursion work" cannot score 1.0 against a lesson that only covers recursion.
        rarest = math.log(1 + max(len(self._tokens), 1))
        weight = {w: self._idf.get(w, rarest) for w in words}
        total = sum(weight.values())
        return np.asarray([sum(weight[w] for w in words if w in tokens) / total for tokens in self._tokens], dtype=np.float32)
