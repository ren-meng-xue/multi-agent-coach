#!/usr/bin/env python3
"""
AI 面试官质量评估沙箱

直接调 LangGraph，不需要启动 HTTP 服务。
跑完一场模拟面试后，用 gpt-4o 对照 qa-reports/2026-06-05-ai-interviewer-test-checklist.md
的质量维度打分，输出 Markdown 报告。

运行：
    cd backend
    uv run python scripts/quality_eval.py

可选参数：
    --turns N      最大对话轮数（默认 8）
    --output PATH  报告输出路径（默认 scripts/eval_report.md）
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, ".")

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.interviewer.graph import build_interviewer_graph
from app.agents.interviewer.state import InterviewState
from app.core.config import get_settings

# ── 模拟候选人脚本 ────────────────────────────────────────────
# 第一条是开场介绍，后续是对面试官问题的预设回答队列
# 当脚本耗尽后，会循环使用最后一条
MOCK_CANDIDATE_SCRIPT = [
    # 开场：带出岗位 + 背景
    "我想练 AI Agent 工程师面试，目标大厂，我做了一个多 Agent 面试教练系统，用 LangGraph + PostgreSQL 实现",

    # 弱回答：无量化、无权衡 → 预期触发追问
    "我遇到的最大挑战是多个 Agent 并发协调，用了 LangGraph 解决，效果还不错",

    # 强回答：加量化 + 权衡
    (
        "具体说：多 Agent 并发写同一状态表会冲突，我加了乐观锁（version 字段），"
        "写入时校验 version，失败则 exponential backoff 重试最多 3 次。"
        "上线后冲突率从每百次 15 次降到 0，p99 延迟从 800ms 到 230ms。"
        "权衡：SELECT FOR UPDATE 会阻塞读，后来换成 SKIP LOCKED + 应用层队列解决热点锁。"
    ),

    # 中等回答：缺量化
    (
        "监控方面用 LangSmith 做追踪，每个节点的输入输出、token 用量和延迟都会上报，"
        "有问题可以回放完整执行路径。"
    ),

    # 补充量化
    (
        "发现 chief_think 节点偶尔误判弱回答为 next_question，"
        "过滤出异常后发现是 prompt 没要求量化基线对比，修复后误判率从 20% 降到 3%。"
        "同时接了 Grafana 看板做趋势监控。"
    ),

    # 行为题：中等
    "遇到分歧时我通常先把双方观点写下来，找共同目标，然后看数据说话",

    # 兜底：候选人表示回答完毕
    "我觉得我说完了，没有要补充的",
]

MOCK_JD = """
岗位：AI Agent 工程师（Senior）
职责：
1. 设计并实现多 Agent 协作系统，负责 Agent 编排、状态管理和工具调用
2. 优化 LLM 推理链路，降低延迟和成本
3. 构建可观测性体系，包括追踪、监控和评测

要求：
- 熟悉 LangChain/LangGraph 或类似 Agent 框架
- 有生产环境 LLM 应用经验
- 理解异步/并发编程，PostgreSQL 等持久化方案
- 具备系统设计和性能优化能力
"""

# ── Judge Prompt ─────────────────────────────────────────────
JUDGE_SYSTEM = """你是一名专业的 AI 面试官质量评审员。
你的任务是根据提供的 JD、面试官问题和候选人回答，从多个维度评估面试官的表现。
请严格、客观，用证据支撑每条评分。"""

JUDGE_PROMPT_TEMPLATE = """
## 背景信息

**岗位 JD：**
{jd}

**完整面试对话（面试官问题 + 候选人回答）：**
{transcript}

---

## 评估任务

请从以下 5 个维度评估面试官表现，每个维度：
- 评分：1-5 分（5 = 优秀，1 = 很差）
- 证据：从对话中引用 1-2 句原文作为依据
- 改进建议：如果评分 < 4，给出 1 句具体改进意见

### 评估维度

**Q1. 问题与 JD 相关性**
面试官的问题是否紧扣 JD 中的岗位职责和技能要求？

**Q2. 问题个性化程度**
面试官是否结合候选人的具体背景（而非泛泛而问）？

**Q3. 追问质量**
面试官是否能识别浅层回答并给出有效追问？追问是否有层次（技术细节/行为逻辑/量化结果）？

**Q4. 语气中立性**
面试官语气是否专业中立？是否有暗示答案、过度称赞或冷漠敷衍的情况？

**Q5. 覆盖率与节奏**
面试是否覆盖了 JD 中的核心能力维度？问题间过渡是否自然，有无重复或跳跃？

---

请以如下 JSON 格式输出（不要加 markdown 代码块）：
{{
  "Q1_relevance": {{"score": N, "evidence": "...", "suggestion": "..."}},
  "Q2_personalization": {{"score": N, "evidence": "...", "suggestion": "..."}},
  "Q3_followup": {{"score": N, "evidence": "...", "suggestion": "..."}},
  "Q4_neutrality": {{"score": N, "evidence": "...", "suggestion": "..."}},
  "Q5_coverage": {{"score": N, "evidence": "...", "suggestion": "..."}},
  "overall_score": 以上5个维度的平均分（保留1位小数，范围1.0-5.0的浮点数）,
  "summary": "一句话总结面试官本次表现"
}}
"""


# ── 运行面试 ─────────────────────────────────────────────────
async def run_mock_interview(max_turns: int) -> list[dict]:
    """跑一场模拟面试，返回 transcript（role + content 列表）。"""
    graph = build_interviewer_graph()
    session_id = str(uuid4())

    state: InterviewState = {
        "session_id": session_id,
        "user_id": "eval-user",
        "is_first_time": True,
        "target_role": "AI Agent 工程师",
        "target_company": "字节跳动",
        "user_background": "开发了多 Agent 面试教练系统，使用 LangGraph + PostgreSQL",
        "stage": "opening",
        "question_count": 0,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "messages": [],
        "jd_context": {"raw": MOCK_JD},
    }

    transcript = []
    script = list(MOCK_CANDIDATE_SCRIPT)

    for turn in range(max_turns):
        # 候选人发言
        if script:
            candidate_input = script.pop(0)
        else:
            candidate_input = "我没有更多要补充的了"

        print(f"\n[Turn {turn + 1}] 候选人：{candidate_input[:80]}...")
        transcript.append({"role": "candidate", "content": candidate_input})

        # 更新 messages
        messages = list(state.get("messages", []))
        messages.append(HumanMessage(content=candidate_input))
        state = {**state, "messages": messages}

        # 面试官回复
        result: InterviewState = await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": session_id}},
        )

        reply = result.get("assistant_message", "")
        print(f"         面试官：{reply[:100]}...")
        transcript.append({"role": "interviewer", "content": reply})

        # 更新 state
        updated_messages = messages + ([AIMessage(content=reply)] if reply else [])
        state = {**result, "messages": updated_messages}

        # 检查面试是否结束
        if result.get("stage") == "closing" and result.get("question_count", 0) >= result.get("total_questions", 5):
            print("\n[面试官主动结束]")
            break

    return transcript


# ── LLM Judge ────────────────────────────────────────────────
def run_judge(transcript: list[dict]) -> dict:
    """用 gpt-4o 对 transcript 打分，返回评分 dict。"""
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    # 格式化 transcript
    lines = []
    for item in transcript:
        role_label = "面试官" if item["role"] == "interviewer" else "候选人"
        lines.append(f"**{role_label}**：{item['content']}")
    transcript_text = "\n\n".join(lines)

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        jd=MOCK_JD.strip(),
        transcript=transcript_text,
    )

    print("\n[Judge] 正在调用 gpt-4o 评分...")
    response = client.chat.completions.create(
        model=settings.openai_model_judge,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content or "{}"
    # 清理可能的 markdown 代码块
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])

    return json.loads(raw)


# ── 生成报告 ──────────────────────────────────────────────────
def render_report(transcript: list[dict], scores: dict, output_path: Path) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    overall = scores.get("overall_score", "N/A")
    summary = scores.get("summary", "")

    dim_labels = {
        "Q1_relevance": "Q1 问题与 JD 相关性",
        "Q2_personalization": "Q2 问题个性化程度",
        "Q3_followup": "Q3 追问质量",
        "Q4_neutrality": "Q4 语气中立性",
        "Q5_coverage": "Q5 覆盖率与节奏",
    }

    lines = [
        f"# AI 面试官质量评估报告",
        f"",
        f"**评估时间**：{now}  ",
        f"**总分**：{overall} / 5  ",
        f"**总结**：{summary}",
        f"",
        f"---",
        f"",
        f"## 各维度评分",
        f"",
        f"| 维度 | 评分 | 证据 | 改进建议 |",
        f"|------|------|------|----------|",
    ]

    for key, label in dim_labels.items():
        dim = scores.get(key, {})
        score = dim.get("score", "-")
        evidence = dim.get("evidence", "").replace("|", "｜")
        suggestion = dim.get("suggestion", "—").replace("|", "｜")
        lines.append(f"| {label} | {score}/5 | {evidence} | {suggestion} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 完整面试 Transcript",
        f"",
    ]

    for item in transcript:
        role_label = "**面试官**" if item["role"] == "interviewer" else "**候选人**"
        lines.append(f"{role_label}：{item['content']}")
        lines.append("")

    report = "\n".join(lines)
    output_path.write_text(report, encoding="utf-8")
    return report


# ── 主入口 ────────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(description="AI 面试官质量评估")
    parser.add_argument("--turns", type=int, default=8, help="最大对话轮数")
    parser.add_argument(
        "--output",
        type=str,
        default="scripts/eval_report.md",
        help="报告输出路径",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("AI 面试官质量评估沙箱")
    print("=" * 60)

    # 1. 跑面试
    print("\n[Step 1] 运行模拟面试...")
    transcript = await run_mock_interview(max_turns=args.turns)
    print(f"\n✓ 面试完成，共 {len(transcript)} 条对话")

    # 2. LLM Judge
    print("\n[Step 2] LLM-as-Judge 评分...")
    scores = run_judge(transcript)
    print(f"✓ 评分完成，总分：{scores.get('overall_score')}/5")

    # 3. 输出报告
    output_path = Path(args.output)
    render_report(transcript, scores, output_path)
    print(f"\n✓ 报告已保存：{output_path.resolve()}")

    # 终端打印摘要
    print("\n" + "=" * 60)
    print("评分摘要")
    print("=" * 60)
    dim_labels = {
        "Q1_relevance": "问题相关性",
        "Q2_personalization": "个性化程度",
        "Q3_followup": "追问质量",
        "Q4_neutrality": "语气中立性",
        "Q5_coverage": "覆盖率与节奏",
    }
    for key, label in dim_labels.items():
        score = scores.get(key, {}).get("score", "-")
        print(f"  {label:12s} {score}/5")
    print(f"\n  总分：{scores.get('overall_score')}/5")
    print(f"  总结：{scores.get('summary')}")


if __name__ == "__main__":
    asyncio.run(main())
