"""验证 report_node 的 CandidateMemory 持久化集成。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.interviewer.nodes import report_node


@pytest.mark.asyncio
async def test_report_node_calls_upsert_memory(db):
    """验证 report_node 在生成报告后正确调用了 upsert_candidate_memory。"""
    # 构造模拟 state
    state = {
        "db": db,  # 注入 db 以触发持久化逻辑
        "user_id": "user_test_123",
        "session_id": "84897f1f-479c-4876-b63e-56193792372e",
        "candidate_profile": {
            "latest_level": "senior",
            "latent_signals": ["signal1", "signal2"]
        },
        "turn_evaluations": [
            {
                "missing_dimensions": ["dim1"],
                "technical_depth": 4, "quantified_results": 4, "failure_tradeoffs": 4, "structure": 4
            },
            {
                "missing_dimensions": ["dim2", "dim1"],
                "technical_depth": 5, "quantified_results": 5, "failure_tradeoffs": 5, "structure": 5
            }
        ],
        "messages": []
    }

    # Mock upsert_candidate_memory 和 _report_aggregate_text
    with (
        patch("app.agents.interviewer.nodes.upsert_candidate_memory", new_callable=AsyncMock) as mock_upsert,
        patch("app.agents.interviewer.nodes._report_aggregate_text", new_callable=AsyncMock) as mock_text,
    ):
        mock_text.return_value = MagicMock(
            highlights=[], improvements=[], key_concepts=[], common_mistakes=[]
        )

        await report_node(state)

        # 验证调用
        mock_upsert.assert_called_once()
        # 检查 positional args
        args, kwargs = mock_upsert.call_args
        # 第一个参数是 db，第二个是 user_id
        assert args[1] == "user_test_123"
        assert kwargs["latest_level"] == "senior"
        assert set(kwargs["latent_signals"]) == {"signal1", "signal2"}
        # 验证短板标签去重
        assert set(kwargs["weakness_tags"]) == {"dim1", "dim2"}


@pytest.mark.asyncio
async def test_report_node_swallows_upsert_memory_error(db):
    """验证即使 upsert_candidate_memory 抛错，report_node 也能正常返回。"""
    state = {
        "db": db,
        "user_id": "user_test_123",
        "session_id": "84897f1f-479c-4876-b63e-56193792372e",
        "candidate_profile": {"latest_level": "junior", "latent_signals": []},
        "turn_evaluations": [{
            "bullets": ["b1"],
            "technical_depth": 3, "quantified_results": 3, "failure_tradeoffs": 3, "structure": 3
        }],
        "messages": []
    }

    with (
        patch("app.agents.interviewer.nodes.upsert_candidate_memory", side_effect=Exception("DB Error")),
        patch("app.agents.interviewer.nodes._report_aggregate_text", new_callable=AsyncMock) as mock_text,
    ):
        mock_text.return_value = MagicMock(
            highlights=[], improvements=[], key_concepts=[], common_mistakes=[]
        )

        result = await report_node(state)
        # 验证报告依然产出了
        assert "report" in result
        assert result["report"]["overall_score"] > 0
