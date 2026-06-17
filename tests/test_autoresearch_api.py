import asyncio
import time
import pytest
import httpx
from src.api import app

# Basic auth header for admin:admin
AUTH_HEADERS = {"Authorization": "Basic YWRtaW46YWRtaW4="}

@pytest.mark.anyio
async def test_autoresearch_run_non_blocking(monkeypatch):
    """
    Test that calling POST /api/autoresearch/run runs the CPU-intensive seeder
    in a thread pool and does NOT block the FastAPI event loop, allowing other
    concurrent requests to be processed.
    """
    post_completed = False
    get_completed_while_post_running = False

    # Mock seed_pool_stats to simulate a 1-second long-running execution
    def mock_seed_pool_stats(*args, **kwargs):
        time.sleep(1.0)  # Blocking sleep in the thread
        return {}, {}    # Return dummy pool and stats

    monkeypatch.setattr("autoresearch.seed_stats.seed_pool_stats", mock_seed_pool_stats)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        
        async def send_post():
            nonlocal post_completed
            # This triggers the mocked seed_pool_stats (takes 1.0s)
            response = await ac.post("/api/autoresearch/run", json={"market_steps": 100}, headers=AUTH_HEADERS)
            assert response.status_code == 200
            post_completed = True

        async def send_get():
            nonlocal get_completed_while_post_running
            # Wait a short moment to ensure the POST request has started executing
            await asyncio.sleep(0.2)
            # Fetch another API endpoint
            response = await ac.get("/api/state", headers=AUTH_HEADERS)
            assert response.status_code == 200
            if not post_completed:
                get_completed_while_post_running = True

        # Run both concurrently
        await asyncio.gather(send_post(), send_get())

    # Assert that the GET request completed while the POST request was still running
    assert get_completed_while_post_running, "FastAPI event loop was blocked by the synchronous seeder run!"
