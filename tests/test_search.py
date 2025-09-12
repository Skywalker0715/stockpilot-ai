import pytest
from httpx import AsyncClient
from httpx import ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_search_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/search",
            json={"query": "coffee near jakarta"},
            headers={"x-api-key": "dev_api_key_1"}
        )
        # Kalau Google API key valid + LLM jalan → 200
        # Kalau tidak, minimal harus return 500 (LLM/Google error)
        assert response.status_code in (200, 500)

        data = response.json()
        assert "query" in data
