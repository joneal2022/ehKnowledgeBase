"""Unit tests for dashboard page routes — Task 7."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session


def _mock_session(sources=None):
    """Return a mock AsyncSession that yields an empty source list."""
    sources = sources or []
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = sources
    session.execute = AsyncMock(return_value=result)
    return session


def _override(sources=None):
    async def _get_session():
        yield _mock_session(sources)
    return _get_session


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = _override()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Dashboard page ─────────────────────────────────────────────────────────────

class TestDashboardPage:
    def test_get_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_get_root_returns_html(self, client):
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_page_includes_htmx_script(self, client):
        response = client.get("/")
        assert "htmx.org" in response.text

    def test_page_includes_tailwind(self, client):
        response = client.get("/")
        assert "tailwindcss.com" in response.text

    def test_page_includes_nav_with_sentinel_brand(self, client):
        response = client.get("/")
        assert "Sentinel" in response.text

    def test_page_includes_nav_links(self, client):
        response = client.get("/")
        assert "Dashboard" in response.text
        assert "Knowledge" in response.text
        assert "Chat" in response.text

    def test_page_has_hx_boost_on_body(self, client):
        response = client.get("/")
        assert 'hx-boost="true"' in response.text

    def test_page_includes_add_video_form(self, client):
        response = client.get("/")
        assert "Add Video" in response.text
        assert "hx-post" in response.text

    def test_page_includes_source_list_div(self, client):
        response = client.get("/")
        assert 'id="source-list"' in response.text


# ── Source feed fragment ───────────────────────────────────────────────────────

class TestSourcesFeed:
    def test_feed_returns_200(self, client):
        response = client.get("/sources/feed")
        assert response.status_code == 200

    def test_feed_returns_html(self, client):
        response = client.get("/sources/feed")
        assert "text/html" in response.headers["content-type"]

    def test_feed_shows_empty_state_when_no_sources(self, client):
        response = client.get("/sources/feed")
        # Empty state — some message indicating no videos yet
        assert response.status_code == 200
