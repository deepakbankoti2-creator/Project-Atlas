"""
Ollama Embedding Service for Project Atlas
Generates vector embeddings using the local Ollama instance with nomic-embed-text.
"""

from typing import List, Dict, Any
import hashlib
import math
import logging
import requests
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def generate_fallback_embedding(text: str, dim: int = 768) -> List[float]:
    """
    Generate a deterministic fallback unit vector when Ollama is offline (for tests/offline use).
    Uses SHA-256 seed hashing to produce normalized pseudo-embeddings.
    """
    vector = []
    base_bytes = text.encode("utf-8")
    for i in range(dim):
        h = hashlib.sha256(base_bytes + str(i).encode()).digest()
        val = int.from_bytes(h[:4], "big", signed=True) / (2**31)
        vector.append(val)
    
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


class OllamaEmbeddingService:
    """Service to generate embeddings using Ollama's local REST API."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_EMBED_MODEL,
        timeout: float = settings.OLLAMA_TIMEOUT_SECONDS
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.embed_url = f"{self.base_url}/api/embed"
        self.embeddings_legacy_url = f"{self.base_url}/api/embeddings"
        self._ollama_available: bool | None = None

    def is_available(self) -> bool:
        """Probe if local Ollama server is reachable."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            self._ollama_available = (resp.status_code == 200)
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string."""
        results = self.embed_batch([text])
        return results[0] if results else []

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of text strings using Ollama's API.
        Falls back to deterministic fallback embeddings if Ollama is unreachable.
        """
        if not texts:
            return []

        # If Ollama is known to be offline, fall back directly to avoid blocking
        if not self.is_available():
            logger.debug("Ollama is currently offline at '%s'. Using deterministic fallback embedding.", self.base_url)
            return [generate_fallback_embedding(t) for t in texts]

        # 1. Try modern Ollama /api/embed (batch)
        try:
            payload = {"model": self.model, "input": texts}
            response = requests.post(self.embed_url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if "embeddings" in data and len(data["embeddings"]) == len(texts):
                    return data["embeddings"]
        except Exception as err:
            logger.debug("Modern Ollama /api/embed request failed: %s", err)

        # 2. Try legacy /api/embeddings per item
        try:
            embeddings: List[List[float]] = []
            for t in texts:
                payload = {"model": self.model, "prompt": t}
                response = requests.post(self.embeddings_legacy_url, json=payload, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    if "embedding" in data:
                        embeddings.append(data["embedding"])
                    else:
                        raise ValueError(f"Missing 'embedding' key in response: {data}")
                else:
                    raise ConnectionError(f"Ollama returned HTTP {response.status_code}: {response.text}")

            if len(embeddings) == len(texts):
                return embeddings
        except Exception as err:
            logger.warning(
                "Ollama service at '%s' unavailable (%s). Using deterministic fallback embedding.",
                self.base_url,
                err
            )

        # 3. Graceful fallback
        return [generate_fallback_embedding(t) for t in texts]


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """ChromaDB compatible embedding function wrapping OllamaEmbeddingService."""

    def __init__(self, service: OllamaEmbeddingService = None):
        self.service = service or OllamaEmbeddingService()

    def name(self) -> str:
        return "ollama_nomic_embed"

    def get_config(self) -> Dict[str, Any]:
        return {
            "model": self.service.model,
            "base_url": self.service.base_url
        }

    def __call__(self, input: Documents) -> Embeddings:
        return self.service.embed_batch(list(input))
