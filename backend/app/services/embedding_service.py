"""
Semantic embedding service using sentence-transformers/all-MiniLM-L6-v2.

Loads the model once and reuses it for all requests.
Semantic similarity is a SUPPLEMENTARY signal — it must NOT override
hard eligibility rules or skill matching.
"""
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Singleton service for computing semantic embeddings and cosine similarity."""

    _instance: Optional["EmbeddingService"] = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    def load_model(self) -> None:
        """Load the sentence-transformer model once."""
        if self._model is not None:
            return
        import os
        if os.getenv("TESTING") == "1":
            logger.info("TESTING mode — skipping EmbeddingService model load.")
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model all-MiniLM-L6-v2...")
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(f"Embedding model load failed: {e}")

    def generate_embedding(self, text: str):
        """Return the embedding vector for a text string."""
        import os
        if self._model is None and os.getenv("TESTING") != "1":
            self.load_model()
        if self._model is None:
            raise RuntimeError("EmbeddingService model is not loaded. Call load_model() first.")
        return self._model.encode(text, convert_to_numpy=True)

    def calculate_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute cosine similarity between two text strings.
        Returns a float in [0, 1].
        """
        import os
        if self._model is None and os.getenv("TESTING") != "1":
            self.load_model()
        if self._model is None:
            raise RuntimeError("EmbeddingService model is not loaded.")
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        emb_a = self._model.encode([text_a], convert_to_numpy=True)
        emb_b = self._model.encode([text_b], convert_to_numpy=True)
        score = float(cosine_similarity(emb_a, emb_b)[0][0])
        return max(0.0, min(1.0, score))

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
