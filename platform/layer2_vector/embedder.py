"""Dense and sparse embedding helpers for Layer 2 hybrid search.

Author: Sarala Biswal
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from platform.core.config import settings
from typing import Any

from rank_bm25 import BM25Okapi

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")

SEMANTIC_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "hardship": ("financial_hardship", "payment_deferral", "assistance"),
    "deferral": ("payment_deferral", "hardship"),
    "defer": ("payment_deferral", "hardship"),
    "missed": ("delinquency", "payment_risk", "hardship_signal"),
    "payments": ("payment", "payment_risk"),
    "payment": ("payments", "payment_risk"),
    "checking": ("deposit_account", "cash_flow"),
    "balance": ("cash_flow", "deposit_account"),
    "direct": ("direct_deposit", "cash_flow"),
    "deposit": ("direct_deposit", "cash_flow"),
    "utilization": ("credit_card_exposure", "payment_risk"),
    "propensity": ("payment_propensity", "model_signal"),
    "contact": ("contact_frequency", "outreach"),
    "frequency": ("contact_frequency", "outreach"),
    "dispute": ("billing_dispute", "regulation_e"),
    "regulation": ("regulation_e", "compliance"),
    "investigation": ("dispute_resolution", "regulation_e"),
    "credit": ("credit_card", "card_account"),
    "limit": ("credit_limit", "responsible_lending"),
    "churn": ("retention", "attrition"),
    "retention": ("churn", "customer_retention"),
}


class DenseEmbedder:
    """Produces dense vectors for semantic retrieval.

    The class can use sentence-transformers when explicitly requested. The
    default deterministic encoder keeps tests and local demos fast while using
    the same list-of-floats interface as the model-backed encoder.
    """

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL,
        dimensions: int = 64,
        use_sentence_transformer: bool = False,
    ) -> None:
        """Create a dense embedder."""
        self.model_name = model_name
        self.dimensions = dimensions
        self._use_sentence_transformer = use_sentence_transformer
        self._model: Any | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into normalized dense vectors."""
        if self._use_sentence_transformer:
            model_vectors = self._embed_with_sentence_transformer(texts)
            if model_vectors is not None:
                return model_vectors
        return [self._deterministic_vector(text) for text in texts]

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text into a normalized dense vector."""
        return self.embed([text])[0]

    def _embed_with_sentence_transformer(self, texts: list[str]) -> list[list[float]] | None:
        try:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            encoded = self._model.encode(texts, normalize_embeddings=True)
        except (OSError, ImportError, RuntimeError):
            return None
        return [[float(value) for value in vector] for vector in encoded]

    def _deterministic_vector(self, text: str) -> list[float]:
        vector = [0.0 for _ in range(self.dimensions)]
        terms = _semantic_terms(text)
        if not terms:
            return vector

        for term, frequency in Counter(terms).items():
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] >= 128 else -1.0
            vector[index] += sign * (1.0 + math.log(float(frequency)))

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0.0:
            return vector
        return [value / magnitude for value in vector]


class SparseEmbedder:
    """Builds BM25 sparse vectors and scores queries over a fitted corpus."""

    def __init__(self) -> None:
        """Create an unfitted sparse embedder."""
        self._bm25: BM25Okapi | None = None
        self._vocabulary: dict[str, int] = {}
        self._terms_by_id: dict[int, str] = {}

    def fit(self, corpus: Sequence[str]) -> None:
        """Fit BM25 statistics over the full knowledge-base corpus."""
        tokenized_corpus = [_tokenize(text, include_numbers=True) for text in corpus]
        self._bm25 = BM25Okapi(tokenized_corpus)
        vocabulary = sorted({token for tokens in tokenized_corpus for token in tokens})
        self._vocabulary = {term: index for index, term in enumerate(vocabulary)}
        self._terms_by_id = {index: term for term, index in self._vocabulary.items()}

    def embed(self, texts: list[str]) -> list[dict[int, float]]:
        """Represent texts as sparse term-frequency vectors."""
        return [self.embed_one(text) for text in texts]

    def embed_one(self, text: str) -> dict[int, float]:
        """Represent one text as a sparse term-frequency vector."""
        counts = Counter(_tokenize(text, include_numbers=True))
        return {
            self._vocabulary[token]: float(count)
            for token, count in counts.items()
            if token in self._vocabulary
        }

    def scores(self, query_vector: dict[int, float]) -> list[float]:
        """Return BM25 scores for the fitted corpus."""
        if self._bm25 is None:
            return []
        query_tokens = [
            self._terms_by_id[index]
            for index, weight in query_vector.items()
            if weight > 0.0 and index in self._terms_by_id
        ]
        raw_scores = self._bm25.get_scores(query_tokens)
        return [float(score) for score in raw_scores]

    def token_count(self) -> int:
        """Return the fitted sparse vocabulary size."""
        return len(self._vocabulary)


def _semantic_terms(text: str) -> list[str]:
    tokens = [token for token in _tokenize(text, include_numbers=False) if not _has_digit(token)]
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        expanded.extend(SEMANTIC_EXPANSIONS.get(token, ()))

    normalized = text.lower()
    phrase_expansions = {
        "2+ missed payments": ("hardship_eligible", "delinquency"),
        "2 missed payments": ("hardship_eligible", "delinquency"),
        "checking balance": ("cash_flow_hardship", "deposit_account"),
        "no direct deposit": ("cash_flow_hardship", "direct_deposit_absent"),
        "payment deferral": ("hardship", "payment_deferral"),
        "contact frequency": ("contact_frequency", "compliance"),
        "billing dispute": ("billing_dispute", "regulation_e"),
        "credit limit": ("credit_limit", "responsible_lending"),
    }
    for phrase, phrase_terms in phrase_expansions.items():
        if phrase in normalized:
            expanded.extend(phrase_terms)
    return expanded


def _tokenize(text: str, *, include_numbers: bool) -> list[str]:
    tokens = [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
    if include_numbers:
        return tokens
    return [token for token in tokens if not _has_digit(token)]


def _has_digit(value: str) -> bool:
    return any(character.isdigit() for character in value)
