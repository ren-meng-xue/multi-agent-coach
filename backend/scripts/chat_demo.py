#!/usr/bin/env python3
"""
模拟真实面试一问一答，直接调 LangGraph，不需要启动 HTTP 服务。

运行：
    cd backend && .venv/bin/python scripts-old1-old/chat_demo.py
"""
import asyncio
import sys
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage

sys.path.insert(0, ".")

from app.agents.interviewer.graph import build_interviewer_graph
from app.agents.interviewer.state import InterviewState

graph = build_interviewer_graph()  # 无 DB checkpointer，内存运行


async def one_turn(state: InterviewState, user_input: str) -> tuple[str, InterviewState]:
    """用户说一句话，图跑一轮，返回面试官回复和更新后的 state。"""
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=user_input))

    result: InterviewState = await graph.ainvoke(
        {**state, "messages": messages},
        config={"configurable": {"thread_id": state["session_id"]}},
    )

    reply = result.get("assistant_message", "")
    updated_messages = messages + ([AIMessage(content=reply)] if reply else [])
    return reply, {**result, "messages": updated_messages}


def print_turn(role: str, text: str):
    print(f"\n{'面试官' if role == 'ai' else '  用户'}：{text}")


async def main():
    session_id = str(uuid4())
    state: InterviewState = {
        "session_id": session_id,
        "user_id": "demo-user",
        "is_first_time": True,
        "stage": "opening",
        "question_count": 0,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
    }

    # 预设的对话脚本（模拟一个真实候选人，5 轮完整对话）
    script = [
        # ── opening：一句话带齐三要素 ──────────────────────────
        "我想练 AI Agent 工程师面试，目标大厂，项目是做了一个多 Agent 面试教练系统",

        # ── 第 1 题：弱回答（没量化、没权衡），预期触发追问 ──
        "我遇到的最大挑战是 Agent 之间的协调问题，用 LangGraph 解决了，效果挺好的",

        # ── 追问后：强回答，预期进入第 2 题 ───────────────────
        (
            "具体来说，多个 Agent 并发写同一个 PostgreSQL 状态表会产生冲突。"
            "我引入了乐观锁（version 字段），写入时做 version 校验，失败则 exponential backoff 重试最多 3 次。"
            "上线后并发冲突从每百次请求约 15 次降到 0，p99 延迟从 800ms 降到 230ms。"
            "权衡：SELECT FOR UPDATE 会阻塞读，后来换成 SKIP LOCKED + 应用层重试队列解决了热点锁竞争。"
        ),

        # ── 第 2 题：监控与调试，中等回答（缺量化），预期追问 ─
        (
            "我们用 LangSmith 做主要的追踪。"
            "每个节点的输入/输出 State、LLM 调用的 prompts、token 用量和延迟都会自动上报，"
            "当某个 Agent 决策异常时可以直接在 LangSmith 里回放完整执行路径。"
        ),

        # ── 追问后：加入量化和权衡，预期进入第 3 题 ──────────
        (
            "具体 case：decide_next 节点偶尔把弱回答判成 next_question。"
            "我在 LangSmith 过滤出这批异常，发现是 prompts 里没要求量化结果需有基线对比。"
            "修复后误判率从约 20% 降到 3%。"
            "同时用 structlog 记录每轮 action/reason，接入 Grafana 看板做趋势监控。"
            "权衡：LangSmith 全量追踪成本高，prod 只追踪异常路径，dev 全量开。"
        ),
    ]

    print("=" * 50)
    print("模拟面试开始")
    print("=" * 50)

    for user_input in script:
        print_turn("user", user_input)
        reply, state = await one_turn(state, user_input)
        print_turn("ai", reply)
        print(f"  [stage={state.get('stage')}, 第{state.get('question_count')}题, followup={state.get('followup_count')}]")

    print("\n" + "=" * 50)
    print("脚本结束")


if __name__ == "__main__":
    asyncio.run(main())
