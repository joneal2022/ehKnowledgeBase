"""Unit tests for EmbeddingService — Task 5."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embedding import (
    DimensionMismatchError,
    EmbeddingService,
    EXPECTED_DIMENSION,
    get_embedding_service,
)


FAKE_VECTOR = [0.1] * 768
WRONG_VECTOR = [0.1] * 512


# ── Business Logic ──────────────────────────────────────────────────────────────

class TestEmbedBasic:
    @pytest.mark.asyncio
    async def test_embed_returns_768_dimensional_vector(self):
        svc = EmbeddingService()
        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=FAKE_VECTOR)):
            result = await svc.embed("hello world")
        assert len(result) == 768

    @pytest.mark.asyncio
    async def test_embed_returns_float_list(self):
        svc = EmbeddingService()
        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=FAKE_VECTOR)):
            result = await svc.embed("test")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_embed_batch_returns_one_vector_per_text(self):
        svc = EmbeddingService()
        texts = ["alpha", "beta", "gamma"]
        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=FAKE_VECTOR)):
            results = await svc.embed_batch(texts)
        assert len(results) == 3
        assert all(len(v) == 768 for v in results)

    @pytest.mark.asyncio
    async def test_embed_batch_single_item(self):
        svc = EmbeddingService()
        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=FAKE_VECTOR)):
            results = await svc.embed_batch(["only one"])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self):
        svc = EmbeddingService()
        results = await svc.embed_batch([])
        assert results == []


# ── Model from config (TC-1: never hardcoded) ──────────────────────────────────

class TestModelConfig:
    def test_model_property_reads_from_settings(self):
        svc = EmbeddingService()
        with patch("app.services.embedding.settings") as mock_settings:
            mock_settings.OLLAMA_MODEL_EMBED = "nomic-embed-text"
            assert svc.model == "nomic-embed-text"

    def test_model_property_reflects_config_change(self):
        svc = EmbeddingService()
        with patch("app.services.embedding.settings") as mock_settings:
            mock_settings.OLLAMA_MODEL_EMBED = "other-model"
            assert svc.model == "other-model"

    @pytest.mark.asyncio
    async def test_call_ollama_sends_model_from_settings(self):
        """_call_ollama must use self.model (from config), never a hardcoded string."""
        svc = EmbeddingService()
        captured = {}

        async def fake_post(url, *, json=None, **kwargs):
            captured["json"] = json
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"embedding": FAKE_VECTOR}
            return resp

        with patch("app.services.embedding.settings") as mock_settings:
            mock_settings.OLLAMA_MODEL_EMBED = "nomic-embed-text"
            mock_settings.OLLAMA_LOCAL_URL = "http://localhost:11434"
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(side_effect=fake_post)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client
                await svc._call_ollama("text")

        assert captured["json"]["model"] == "nomic-embed-text"
        assert captured["json"]["prompt"] == "text"


# ── Dimension verification ──────────────────────────────────────────────────────

class TestDimensionVerification:
    @pytest.mark.asyncio
    async def test_wrong_dimension_raises_dimension_mismatch_error(self):
        svc = EmbeddingService()
        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=WRONG_VECTOR)):
            with pytest.raises(DimensionMismatchError):
                await svc.embed("bad model")

    @pytest.mark.asyncio
    async def test_error_message_includes_expected_and_actual(self):
        svc = EmbeddingService()
        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=WRONG_VECTOR)):
            with pytest.raises(DimensionMismatchError, match="768") as exc_info:
                await svc.embed("bad model")
        assert "512" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dimension_verified_only_on_first_call(self):
        """After first successful verification, _verify_dimension is not called again."""
        svc = EmbeddingService()
        call_count = 0
        original_verify = svc._verify_dimension

        def counting_verify(vector):
            nonlocal call_count
            call_count += 1
            return original_verify(vector)

        svc._verify_dimension = counting_verify

        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=FAKE_VECTOR)):
            await svc.embed("first")
            await svc.embed("second")
            await svc.embed("third")

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_verified_flag_set_after_first_embed(self):
        svc = EmbeddingService()
        assert svc._verified is False
        with patch.object(svc, "_call_ollama", new=AsyncMock(return_value=FAKE_VECTOR)):
            await svc.embed("check")
        assert svc._verified is True

    def test_expected_dimension_constant_is_768(self):
        assert EXPECTED_DIMENSION == 768


# ── Error handling ─────────────────────────────────────────────────────────────

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_http_error_propagates(self):
        import httpx
        svc = EmbeddingService()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
            mock_resp.json.return_value = {"embedding": FAKE_VECTOR}
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.services.embedding.settings") as mock_settings:
                mock_settings.OLLAMA_MODEL_EMBED = "nomic-embed-text"
                mock_settings.OLLAMA_LOCAL_URL = "http://localhost:11434"
                with pytest.raises(httpx.HTTPStatusError):
                    await svc.embed("text")

    @pytest.mark.asyncio
    async def test_connection_error_propagates(self):
        import httpx
        svc = EmbeddingService()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("app.services.embedding.settings") as mock_settings:
                mock_settings.OLLAMA_MODEL_EMBED = "nomic-embed-text"
                mock_settings.OLLAMA_LOCAL_URL = "http://localhost:11434"
                with pytest.raises(httpx.ConnectError):
                    await svc.embed("text")


# ── Singleton / regression guards ──────────────────────────────────────────────

class TestSingleton:
    def test_get_embedding_service_returns_same_instance(self):
        import app.services.embedding as mod
        mod._instance = None  # reset for test isolation
        svc1 = get_embedding_service()
        svc2 = get_embedding_service()
        assert svc1 is svc2
        mod._instance = None  # cleanup

    def test_get_embedding_service_returns_embedding_service(self):
        import app.services.embedding as mod
        mod._instance = None
        svc = get_embedding_service()
        assert isinstance(svc, EmbeddingService)
        mod._instance = None
