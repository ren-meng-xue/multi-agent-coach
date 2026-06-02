from enum import StrEnum
from typing import TypedDict


class TargetType(StrEnum):
    QUESTION = "question"
    SCORING = "scoring"
    FOLLOWUP = "followup"
    AGENT_QUALITY = "agent_quality"
    REVIEW = "review"
    PLAN = "plan"


class JudgeMode(StrEnum):
    RUBRIC = "rubric"
    COMPARATIVE = "comparative"
    BINARY = "binary"


class Dimension(TypedDict):
    name: str
    description: str
    rubric_text: str
    pass_threshold: float


DIMENSIONS: dict[TargetType, list[Dimension]] = {
    TargetType.QUESTION: [
        {
            "name": "relevance",
            "description": "相关性：问题是否紧扣面试背景、岗位要求及候选人之前的回答。",
            "rubric_text": "1-3: 与背景无关或生硬跳转；4-6: 基本相关但略显通用；7-10: 高度契合上下文，针对性极强。",
            "pass_threshold": 6.0,
        },
        {
            "name": "specificity",
            "description": "具体性：问题是否指向具体的场景、技术细节或行为表现，而非泛泛而谈。",
            "rubric_text": "1-3: 过于笼统（如'谈谈你的项目'）；4-6: 有一定场景设定；7-10: 设定了清晰的边界条件和考察点。",
            "pass_threshold": 6.0,
        },
        {
            "name": "depth",
            "description": "深度：问题是否能挖掘出候选人的底层原理理解、方案权衡或复杂问题解决能力。",
            "rubric_text": "1-3: 仅停留于表面概念；4-6: 涉及部分原理；7-10: 触及核心架构、性能权衡或疑难杂症处理。",
            "pass_threshold": 6.0,
        },
        {
            "name": "clarity",
            "description": "清晰度：语言表达是否简洁准确，意图是否明确，无歧义。",
            "rubric_text": "1-3: 表达混乱，意图不明；4-6: 基本清晰，但可能需要二次确认；7-10: 表达精炼，任务指引极度明确。",
            "pass_threshold": 6.0,
        },
    ],
    TargetType.SCORING: [
        {
            "name": "score_agreement_technical_depth",
            "description": "技术深度评分一致性：评分是否真实反映了回答中展现的技术理解水平。",
            "rubric_text": "对比 Golden 评分，误差在±1分以内为高一致性。",
            "pass_threshold": 7.0,
        },
        {
            "name": "score_agreement_quantified_results",
            "description": "量化结果评分一致性：对回答中是否有具体量化产出的识别与评分是否准确。",
            "rubric_text": "准确识别量化指标且评分合理。",
            "pass_threshold": 7.0,
        },
        {
            "name": "score_agreement_failure_tradeoffs",
            "description": "失败权衡评分一致性：对回答中是否提及思考权衡、失败案例的识别是否准确。",
            "rubric_text": "准确识别权衡思考且评分合理。",
            "pass_threshold": 7.0,
        },
        {
            "name": "score_agreement_structure",
            "description": "结构化表达评分一致性：对回答逻辑性和条理性的评分是否准确。",
            "rubric_text": "对逻辑清晰度的判断与专家标准一致。",
            "pass_threshold": 7.0,
        },
        {
            "name": "signal_reasonableness",
            "description": "隐含信号合理性：识别出的潜在特质（如'沟通成本高'、'架构思维强'）是否有充分的事实支撑。",
            "rubric_text": "信号必须有对应对话内容的引用或逻辑推导，严禁凭空猜测。",
            "pass_threshold": 6.0,
        },
    ],
    TargetType.FOLLOWUP: [
        {
            "name": "weakness_targeting",
            "description": "命中弱点：追问是否针对候选人前序回答中的模糊点、矛盾点或薄弱环节。",
            "rubric_text": "1-3: 完全忽略弱点；4-6: 捕捉到部分模糊点；7-10: 精准刺破回答中最薄弱或最值得深挖的部分。",
            "pass_threshold": 7.0,
        },
        {
            "name": "specificity",
            "description": "具体性：追问是否包含具体的补充要求或修正场景。",
            "rubric_text": "要求候选人针对某一具体点进行补充或在特定约束下重新思考。",
            "pass_threshold": 6.0,
        },
        {
            "name": "depth_probe",
            "description": "深度追问：追问是否在引导候选人走向更深层的思考。",
            "rubric_text": "不仅是补充信息，而是要求解释底层逻辑或做更难的权衡。",
            "pass_threshold": 6.0,
        },
    ],
    TargetType.AGENT_QUALITY: [
        {
            "name": "decision_quality",
            "description": "Chief 决策质量：是否在该追问、出新题或收尾时做出正确选择。",
            "rubric_text": "1-3: 明显误判流程；4-6: 大方向可接受但节奏不佳；7-10: 精准匹配回答质量、题数进度和候选人意图。",
            "pass_threshold": 7.0,
        },
        {
            "name": "delegation_quality",
            "description": "委托质量：Chief 是否在合适时机调用 Evaluator 和 Designer。",
            "rubric_text": "首轮可直接设计问题；非首轮应先评估再出题/追问；题满或终止意图应避免无意义工具调用。",
            "pass_threshold": 7.0,
        },
        {
            "name": "signal_coverage",
            "description": "信号覆盖：Evaluator 报告是否覆盖 golden 中期望识别的信号和弱点。",
            "rubric_text": "识别出的 signals/missing_dimensions 应与回答事实和 golden 方向一致。",
            "pass_threshold": 7.0,
        },
    ],
    TargetType.REVIEW: [
        {
            "name": "insight_depth",
            "description": "洞察深度：复盘内容是否穿透了表面表现，触及了候选人的核心胜任力模式。",
            "rubric_text": "提供超越回答字面意思的深度分析。",
            "pass_threshold": 6.0,
        },
        {
            "name": "cross_session_awareness",
            "description": "跨 session 模式识别：是否能够联系之前的面试表现，识别出一致性的优点或缺点。",
            "rubric_text": "能够引用前序 session 的表现进行对比分析。",
            "pass_threshold": 6.0,
        },
        {
            "name": "actionability",
            "description": "可操作性：给出的建议是否具体、可落地，对教练计划有直接指导意义。",
            "rubric_text": "建议应包含具体的学习路径或刻意练习方向。",
            "pass_threshold": 7.0,
        },
        {
            "name": "tone_balance",
            "description": "语气平衡：复盘语气是否客观专业，既不打压也不盲目吹捧。",
            "rubric_text": "维持建设性的、基于事实的反馈风格。",
            "pass_threshold": 6.0,
        },
    ],
    TargetType.PLAN: [
        {
            "name": "weakness_alignment",
            "description": "针对弱点：提升计划是否紧扣面试中暴露出的最核心问题。",
            "rubric_text": "计划内容与识别出的弱点有明确的对应关系。",
            "pass_threshold": 7.0,
        },
        {
            "name": "specificity",
            "description": "具体性：计划是否包含具体的行动项、书单或练习题。",
            "rubric_text": "包含可量化或可观察的练习目标。",
            "pass_threshold": 6.0,
        },
        {
            "name": "feasibility",
            "description": "可行性：计划是否考虑了候选人的现状，是否可以在合理时间内完成。",
            "rubric_text": "难度和量级适合候选人的当前水平。",
            "pass_threshold": 6.0,
        },
        {
            "name": "role_accuracy",
            "description": "岗位准确性：计划是否符合目标岗位对胜任力的要求。",
            "rubric_text": "重点提升项必须是该岗位最核心的技能点。",
            "pass_threshold": 7.0,
        },
    ],
}
