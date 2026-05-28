import json
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from structlog import get_logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.eval.dimensions import DIMENSIONS, TargetType
from app.eval.schemas import (
    BinaryScore,
    ComparativeScore,
    JudgeConfig,
    ReflectionScore,
    RubricDimensionScore,
    RubricJudgeScore,
)

log = get_logger("app.eval.judge")

JudgeResult = RubricJudgeScore | ComparativeScore | BinaryScore

_RETRYABLE = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)

_retry_llm = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)


class BaseJudge(ABC):
    def __init__(self, config: JudgeConfig):
        self.config = config
        self.settings = get_settings()

    @abstractmethod
    async def judge(
        self,
        input_json: dict,
        system_output: dict,
        golden: dict | None = None,
        **kwargs: Any,
    ) -> JudgeResult:
        pass

    def _chat_model(self, streaming: bool = False) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.config.model,
            api_key=self.settings.openai_api_key,
            temperature=self.config.temperature,
            streaming=streaming,
            timeout=30,
        )


class RubricJudge(BaseJudge):
    async def judge(
        self,
        input_json: dict,
        system_output: dict,
        golden: dict | None = None,
        target_type: TargetType = TargetType.QUESTION,
        **kwargs: Any,
    ) -> RubricJudgeScore:
        dimensions = DIMENSIONS.get(target_type, [])
        context = {
            "target_type": target_type.value,
            "input_json": input_json,
            "system_output": system_output,
            "golden": golden,
            "dimensions": dimensions,
        }

        try:
            await self._reasoning_stream(context)
            score = await self._rubric_score(context)
            return score
        except Exception as exc:
            log.error("rubric_judge_failed", error=str(exc), target_type=target_type)
            return RubricJudgeScore(
                target_type=target_type.value,
                dimensions=[
                    RubricDimensionScore(
                        dimension_name=d["name"], score=5.0, reasoning="Judge failed, fallback to default"
                    )
                    for d in dimensions
                ],
                overall=5.0,
                reasoning=f"Judge failed: {str(exc)}",
            )

    @_retry_llm
    async def _reasoning_stream(self, context: dict) -> None:
        model = self._chat_model(streaming=True).with_config(tags=["eval_judge_reasoning"])
        prompt = self._build_reasoning_prompt(context)
        async for _ in model.astream([SystemMessage(content=prompt)]):
            pass

    @_retry_llm
    async def _rubric_score(self, context: dict) -> RubricJudgeScore:
        model = self._chat_model().with_structured_output(RubricJudgeScore)
        prompt = self._build_rubric_prompt(context)
        out = await model.ainvoke([SystemMessage(content=prompt)])
        if isinstance(out, RubricJudgeScore):
            return out
        raise ValueError("LLM returned non-RubricJudgeScore object")

    def _build_reasoning_prompt(self, context: dict) -> str:
        return f"""你是一个专业的 AI 面试教练评测专家。
请对以下面试 AI 的输出进行深度分析。

【评测目标类型】: {context['target_type']}
【输入上下文】: {json.dumps(context['input_json'], ensure_ascii=False)}
【AI 输出内容】: {json.dumps(context['system_output'], ensure_ascii=False)}
【标准参考 (Golden)】: {json.dumps(context['golden'], ensure_ascii=False) if context['golden'] else "无"}

请根据以下维度进行推理分析，思考每个维度的优缺点：
{json.dumps(context['dimensions'], ensure_ascii=False, indent=2)}

请先输出你的推理过程（Chain of Thought）。"""

    def _build_rubric_prompt(self, context: dict) -> str:
        return f"""根据之前的推理分析，请为以下 AI 输出进行打分。

【评测目标类型】: {context['target_type']}
【维度标准】: 
{json.dumps(context['dimensions'], ensure_ascii=False, indent=2)}

请严格按照 RubricJudgeScore 格式输出 JSON。
每个维度分数范围 0-10。总体分数 (overall) 应该是各维度的加权或综合体现。"""


class ComparativeJudge(BaseJudge):
    async def judge(
        self,
        input_json: dict,
        system_output: dict,  # dict with "a" and "b"
        golden: dict | None = None,
        **kwargs: Any,
    ) -> ComparativeScore:
        try:
            return await self._compare(input_json, system_output, golden)
        except Exception as exc:
            log.error("comparative_judge_failed", error=str(exc))
            return ComparativeScore(
                a_better=False,
                b_better=False,
                tie=True,
                reasoning=f"Judge failed: {str(exc)}",
                confidence=0.0,
            )

    @_retry_llm
    async def _compare(self, input_json, system_output, golden) -> ComparativeScore:
        model = self._chat_model().with_structured_output(ComparativeScore)
        prompt = f"""你是一个专业的 AI 评测专家。请对比两个 AI 系统的输出，判断哪一个更好。

【输入上下文】: {json.dumps(input_json, ensure_ascii=False)}
【AI 输出 A】: {json.dumps(system_output.get('a'), ensure_ascii=False)}
【AI 输出 B】: {json.dumps(system_output.get('b'), ensure_ascii=False)}
【标准参考 (Golden)】: {json.dumps(golden, ensure_ascii=False) if golden else "无"}

请判断 A 更好、B 更好还是平局 (tie)，并给出理由和置信度。
只能有一个为 True。"""
        out = await model.ainvoke([SystemMessage(content=prompt)])
        if isinstance(out, ComparativeScore):
            return out
        raise ValueError("LLM returned non-ComparativeScore object")


class BinaryJudge(BaseJudge):
    async def judge(
        self,
        input_json: dict,
        system_output: dict,
        golden: dict | None = None,
        criteria: str = "",
        **kwargs: Any,
    ) -> BinaryScore:
        try:
            return await self._binary_check(input_json, system_output, criteria, golden)
        except Exception as exc:
            log.error("binary_judge_failed", error=str(exc))
            return BinaryScore(passed=False, reasoning=f"Judge failed: {str(exc)}", confidence=0.0)

    @_retry_llm
    async def _binary_check(self, input_json, system_output, criteria, golden) -> BinaryScore:
        model = self._chat_model().with_structured_output(BinaryScore)
        prompt = f"""你是一个专业的 AI 评测专家。请根据指定标准判断 AI 输出是否通过。

【评测标准】: {criteria}
【输入上下文】: {json.dumps(input_json, ensure_ascii=False)}
【AI 输出内容】: {json.dumps(system_output, ensure_ascii=False)}
【标准参考 (Golden)】: {json.dumps(golden, ensure_ascii=False) if golden else "无"}

请判断是否通过 (passed)，并给出理由和置信度。"""
        out = await model.ainvoke([SystemMessage(content=prompt)])
        if isinstance(out, BinaryScore):
            return out
        raise ValueError("LLM returned non-BinaryScore object")


class SelfReflectionJudge:
    def __init__(self, wrapped_judge: BaseJudge):
        self.wrapped_judge = wrapped_judge

    async def judge(
        self, input_json: dict, system_output: dict, golden: dict | None = None
    ) -> ReflectionScore:
        # 1. 运行内层 judge
        base_result = await self.wrapped_judge.judge(input_json, system_output, golden)
        
        # 2. 进行反思
        try:
            return await self._reflect(input_json, system_output, base_result)
        except Exception as exc:
            log.error("reflection_failed", error=str(exc))
            # 这里的 fallback 逻辑可以根据 base_result 构造
            overall = getattr(base_result, "overall", None)
            return ReflectionScore(
                original_confidence=0.5,
                adjusted=False,
                new_overall=overall,
                reasoning=f"Reflection failed: {str(exc)}",
            )

    @_retry_llm
    async def _reflect(self, input_json, system_output, base_result) -> ReflectionScore:
        model = self.wrapped_judge._chat_model().with_structured_output(ReflectionScore)
        prompt = f"""你是一个高级评测审计专家。你刚刚对一个 AI 输出进行了初步评测。
现在请你重新审视你的评测结果，检查是否存在偏见、漏看细节或评分标准掌握不一的情况。

【输入上下文】: {json.dumps(input_json, ensure_ascii=False)}
【AI 输出内容】: {json.dumps(system_output, ensure_ascii=False)}
【初步评测结果】: {base_result.model_dump_json() if hasattr(base_result, 'model_dump_json') else str(base_result)}

请思考：
1. 你的评分是否过于严苛或宽松？
2. 是否有具体的证据支撑你的每一个维度的评分？
3. 如果让你重新打分，你会调整吗？

请输出 ReflectionScore 格式的 JSON。"""
        out = await model.ainvoke([SystemMessage(content=prompt)])
        if isinstance(out, ReflectionScore):
            return out
        raise ValueError("LLM returned non-ReflectionScore object")
