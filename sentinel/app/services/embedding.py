"""Embedding service — ONE model, ONE service, EVERYWHERE.

CRITICAL: nomic-embed-text must be used for ALL embeddings (documents AND queries).
Never mix embedding models — vectors become incomparable if different models are used.
See ARCHITECTURE.md §2 and CODE_PATTERNS.md §11.
"""
import httpx

from app.config import settings

EXPECTED_DIMENSION = 768


class DimensionMismatchError(Exception):
    """Raised when the embedding model returns unexpected vector dimensions."""


class EmbeddingService:
    """Produces 768-dimensional text embeddings using nomic-embed-text via local Ollama.

    Always uses settings.OLLAMA_MODEL_EMBED — model is never configurable per-call.
    Verifies 768d on first call and raises immediately if the model changes.
    """

    def __init__(self) -> None:
        self._verified = False

    @property
    def model(self) -> str:
        """The embedding model name — always from config, never hardcoded."""
        return settings.OLLAMA_MODEL_EMBED

    def _verify_dimension(self, vector: list[float]) -> None:
        """Verify the returned vector is 768-dimensional. Raises on mismatch."""
        if len(vector) != EXPECTED_DIMENSION:
            raise DimensionMismatchError(
                f"Embedding dimension mismatch: expected {EXPECTED_DIMENSION}, "
                f"got {len(vector)}. Check that OLLAMA_MODEL_EMBED is set to "
                f"'nomic-embed-text' and the model is pulled."
            )
        self._verified = True

    async def _call_ollama(self, text: str) -> list[float]:
        """POST to local Ollama embeddings endpoint and return the float vector."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_LOCAL_URL}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string. Returns a 768-dimensional float vector.

        Verifies dimension on first call — raises DimensionMismatchError immediately
        if the wrong model is configured.
        """
        vector = await self._call_ollama(text)
        if not self._verified:
            self._verify_dimension(vector)
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Each call is independent (Ollama has no batch API)."""
        results = []
        for text in texts:
            results.append(await self.embed(text))
        return results


# ── singleton factory ──────────────────────────────────────────────────────────

_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return the global EmbeddingService singleton.

    Using a singleton ensures the same model instance is used everywhere,
    preventing accidental model drift across different parts of the codebase.
    """
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance
