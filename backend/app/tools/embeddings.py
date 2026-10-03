"""
create_embeddings / chunking tool.

EMBEDDING_PROVIDER=local              -> TF-IDF vectors (always available,
                                          zero network, zero extra deps)
EMBEDDING_PROVIDER=sentence_transformers -> real dense embeddings, used if
                                          the optional `sentence-transformers`
                                          package is installed (it is NOT
                                          installed by default in this repo's
                                          minimal requirements because of its
                                          large torch dependency; see README)

Chunking is real: word-window chunks with overlap, not "the whole
document as one chunk" — this is what makes retrieval below the
document level possible.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import get_settings


@dataclass
class Chunk:
    id: str
    source_id: str
    text: str


def chunk_text(source_id: str, text: str, *, chunk_size: int = 180, overlap: int = 40) -> list[Chunk]:
    words = text.split()
    if not words:
        return []
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text_ = " ".join(words[start:end])
        chunks.append(Chunk(id=f"{source_id}_chunk_{idx}", source_id=source_id, text=chunk_text_))
        idx += 1
        if end == len(words):
            break
        start = end - overlap
    return chunks


class EmbeddingBackend:
    """Fits a TF-IDF vectorizer over a corpus of chunks and embeds a query
    into the same space. This is a real (if simple) local/free embedding
    method: no network call, no API key, works out of the box.
    """

    def __init__(self):
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._chunks: list[Chunk] = []

    def fit(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        texts = [c.text for c in chunks] or [""]
        self._vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        self._matrix = self._vectorizer.fit_transform(texts)

    def query(self, text: str, k: int = 6) -> list[tuple[Chunk, float]]:
        if self._vectorizer is None or not self._chunks:
            return []
        from sklearn.metrics.pairwise import cosine_similarity

        qvec = self._vectorizer.transform([text])
        sims = cosine_similarity(qvec, self._matrix).flatten()
        ranked = sorted(zip(self._chunks, sims), key=lambda x: x[1], reverse=True)
        return [(c, float(s)) for c, s in ranked[:k] if s > 0]


def get_embedding_backend() -> EmbeddingBackend:
    settings = get_settings()
    if settings.embedding_provider == "sentence_transformers":
        try:
            from app.tools._st_embeddings import SentenceTransformerBackend  # optional

            return SentenceTransformerBackend(settings.embedding_model)
        except ImportError:
            pass  # fall through to local TF-IDF
    return EmbeddingBackend()
