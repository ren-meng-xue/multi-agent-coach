import os
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_eval_auth_failure():
    # Set APP_ENV to prod to trigger auth check
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch.dict(os.environ, {"APP_ENV": "prod", "RUN_LLM_EVAL": "secret"}):
            response = await ac.post("/api/v1/eval/runs", json={"suite": "test"})
            assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_suites_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/eval/suites")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_trigger_eval_api():
    # Mocking dependencies for trigger_eval
    with patch("app.eval.storage.EvalStorage.get_suite_by_name") as mock_get_suite:
        mock_suite = AsyncMock()
        mock_suite.id = UUID("00000000-0000-0000-0000-000000000000")
        mock_suite.cases = []
        mock_get_suite.return_value = mock_suite
        
        with patch("app.eval.storage.EvalStorage.create_run") as mock_create_run:
            mock_run = AsyncMock()
            mock_run.id = UUID("11111111-1111-1111-1111-111111111111")
            mock_create_run.return_value = mock_run
            
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                with patch.dict(os.environ, {"APP_ENV": "dev"}):
                    response = await ac.post("/api/v1/eval/runs", json={"suite": "interviewer_v0"})
                    assert response.status_code == 200
                    assert response.json() == str(mock_run.id)


@pytest.mark.asyncio
async def test_list_runs_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/eval/runs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_run_detail_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Mocking run not found
        response = await ac.get("/api/v1/eval/runs/22222222-2222-2222-2222-222222222222")
        assert response.status_code == 404
