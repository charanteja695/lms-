"""Words and similarity for matching. Deterministic and dependency-free: the fallback when embeddings are unavailable, and the
normalisation that makes "Node.js", "nodejs" and "NodeJS" the same skill."""

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z][a-z0-9+#.\-]*[a-z0-9+#]|[a-z]")
_STOP = frozenset(
    """a about after all also an and any are as at be been but by can for from has have in into is it its of on or our out over per that the their them
    then there these they this to up us was we were what when which who will with within you your ability able experience experienced strong team work working
    role roles skills skill years year required preferred good great excellent knowledge understanding including include using use used etc""".split()
)
# the same skill written differently: matching is on the canonical spelling (the key of each group)
_VARIANTS = {
    "javascript": ("js", "ecmascript"), "typescript": ("ts",), "python": ("py", "python3"), "postgresql": ("postgres", "psql"), "kubernetes": ("k8s",),
    "node": ("nodejs", "node.js"), "react": ("reactjs", "react.js"), "vue": ("vuejs", "vue.js"), "angular": ("angularjs",), "go": ("golang",),
    "mongodb": ("mongo",), "ml": ("machine learning",), "dl": ("deep learning",), "nlp": ("natural language processing",), "c++": ("cpp",), "c#": ("csharp",),
    ".net": ("dotnet",), "gcp": ("google cloud",), "aws": ("amazon web services",), "cicd": ("ci/cd", "ci cd"), "rest": ("rest api", "restful", "rest apis"),
    "scikit-learn": ("sklearn", "scikit learn"), "api": ("apis",),
}
_ALIASES = {variant: canon for canon, variants in _VARIANTS.items() for variant in variants}
_CANON = frozenset(_VARIANTS)


def canonical(skill: str) -> str:
    """A skill's matching form: lower case, trimmed, plural and spelling variants folded."""
    word = " ".join(skill.lower().strip().split()).strip(".-")
    if word in _ALIASES:
        return _ALIASES[word]
    if word in _CANON:
        return word
    if len(word) > 3 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    return _ALIASES.get(word, word)


def tokens(text: str) -> list[str]:
    return [canonical(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def lexical_cosine(a: str, b: str) -> float:
    """Cosine similarity of two texts' word counts (sublinear term frequency). 0..1."""
    ca, cb = Counter(tokens(a)), Counter(tokens(b))
    if not ca or not cb:
        return 0.0
    wa = {t: 1 + math.log(n) for t, n in ca.items()}
    wb = {t: 1 + math.log(n) for t, n in cb.items()}
    dot = sum(wa[t] * wb[t] for t in wa.keys() & wb.keys())
    norm = math.sqrt(sum(v * v for v in wa.values())) * math.sqrt(sum(v * v for v in wb.values()))
    return dot / norm if norm else 0.0


def dense_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def scale_lexical(cosine: float) -> float:
    """Word-overlap cosines between a profile and a job description are small even for a good fit: 0.4 counts as a full match."""
    return min(1.0, cosine / 0.4)


def scale_dense(cosine: float) -> float:
    """Embedding cosines between texts of the same domain start high: 0.25 counts as unrelated and 0.75 as a full match."""
    return min(1.0, max(0.0, (cosine - 0.25) / 0.5))
