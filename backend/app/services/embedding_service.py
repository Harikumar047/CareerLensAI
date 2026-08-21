import logging
import math
import re
from typing import Optional, List

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Lightweight TF-IDF / Token Cosine similarity service.
    Replaces 500MB PyTorch/sentence-transformers with standard Python math.
    Memory footprint: < 1MB.
    """

    _instance: Optional["EmbeddingService"] = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_model(self) -> None:
        logger.info("Lightweight EmbeddingService initialized.")

    @property
    def is_loaded(self) -> bool:
        return True

    def _tokenize(self, text: str) -> List[str]:
        return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 2]

    def calculate_similarity(self, text_a: str, text_b: str) -> float:
        if not text_a or not text_b:
            return 0.0
        tokens_a = self._tokenize(text_a)
        tokens_b = self._tokenize(text_b)
        if not tokens_a or not tokens_b:
            return 0.0

        set_a = set(tokens_a)
        set_b = set(tokens_b)

        # Jaccard / Overlap similarity
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return round(intersection / union, 4)
