"""
手动 LLM Eval：验证 master_node 对强/弱回答的实际 chain 决策。

运行方式：
    cd backend && .venv/bin/python -m pytest tests/eval/ -s -v

不加 assert，只打印 LLM 实际输出，用于人工观察 prompt 效果。
不纳入 CI，需要真实 OPENAI_API_KEY。
"""
import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer.nodes import master_node

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVAL") != "1",
    reason="manual LLM eval; set RUN_LLM_EVAL=1 to run",
)

_QUESTION = "请介绍你在 AI Agent 项目中遇到的最大技术挑战，以及你是如何解决的。"

_BASE = {
    "session_id": "eval-session",
    "user_id": "eval-user",
    "is_first_time": False,
    "target_role": "AI Agent 工程师",
    "target_company": "字节跳动",
    "user_background": "开发了一个多 Agent 面试教练系统",
    "stage": "interview",
    "question_count": 1,
    "total_questions": 5,
    "followup_count": 0,
    "max_followups": 2,
    "assistant_message": "",
}


@pytest.mark.asyncio
async def test_weak_answer_expect_followup():
    """
    弱回答：没有量化结果、没有失败/权衡细节。
    预期：LLM 选择需要追问的 chain。
    """
    state = {
        **_BASE,
        "messages": [
            AIMessage(content=_QUESTION),
            HumanMessage(content="我遇到的最大挑战是 Agent 之间的协调。我用了 LangGraph 来解决这个问题，最后效果很好。"),
        ],
    }
    result = await master_node(state)
    print("\n[弱回答]")
    print(f"  chain : {result.get('chain')}")
    print(f"  reason: {result.get('master_reason')}")


@pytest.mark.asyncio
async def test_strong_answer_expect_next_question():
    """
    强回答：有 STAR 结构、量化结果、失败与权衡。
    预期：LLM 选择评估后进入下一题或收尾前的合理 chain。
    """
    state = {
        **_BASE,
        "messages": [
            AIMessage(content=_QUESTION),
            HumanMessage(
                content=(
                    "最大的挑战是多 Agent 并发时状态不一致。"
                    "背景：系统有 3 个并发 Agent，共享一个 PostgreSQL 状态表。"
                    "我负责设计状态同步机制。"
                    "做法：引入乐观锁（version 字段），写入时用 SELECT FOR UPDATE 保证原子性，"
                    "并加了 exponential backoff retry（最多 3 次）。"
                    "结果：并发冲突从每 100 请求约 15 次降到 0，p99 延迟从 800ms 降到 230ms。"
                    "权衡：FOR UPDATE 会阻塞读，后来改成 SKIP LOCKED 解决了热点锁竞争，"
                    "但 SKIP LOCKED 会跳过被锁行，需要在应用层补一次重试队列。"
                )
            ),
        ],
    }
    result = await master_node(state)
    print("\n[强回答]")
    print(f"  chain : {result.get('chain')}")
    print(f"  reason: {result.get('master_reason')}")
