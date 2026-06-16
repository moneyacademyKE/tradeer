import pytest
import asyncio
from src.exchange import async_retry

@pytest.mark.anyio
async def test_async_retry_success_after_failures():
    attempts = 0

    @async_retry(max_retries=3, initial_delay=0.01, backoff_factor=1.0)
    async def mock_api():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("API error")
        return "success"

    res = await mock_api()
    assert res == "success"
    assert attempts == 3

@pytest.mark.anyio
async def test_async_retry_raises_after_max_retries():
    attempts = 0

    @async_retry(max_retries=3, initial_delay=0.01, backoff_factor=1.0)
    async def mock_api_fail():
        nonlocal attempts
        attempts += 1
        raise ValueError("Persistent API error")

    with pytest.raises(ValueError, match="Persistent API error"):
        await mock_api_fail()
    assert attempts == 3
