# backend/app/agents/prepare/prompts.py
"""Prompt constants for prepare pipeline nodes."""

MASTER_REASONING_PROMPT = """你是面试准备 Master Orchestrator。
分析以下用户信息，使用「中文」逐行输出你的判断（每行以"• "开头）。

用户信息：
{context}

请输出你的分析过程，包括：检查用户档案、检查历史情况、确定练习方向、确定调用链。
语言简洁，每行不超过40字。"""

MASTER_DECISION_PROMPT = """基于以下用户信息，输出调度决策（JSON）。

用户信息：
{context}

输出字段：
- direction: 识别出的练习方向（如"前端工程师"、"分布式系统"）。请从用户的目标岗位、方向描述中提取核心关键词。
- chain: 需要调用的子 Agent 列表，从 ["memory_search","jd_analysis","question_gen"] 中选
  - memory_search: 有历史记录时包含
  - jd_analysis: 有 JD 文本时包含
  - question_gen: 始终包含
- need_direction: 布尔值。只有当用户完全没有提供任何关于面试方向、岗位、公司或技术主题的信息时，才为 true。若用户已提供如「我想面字节前端」这类信息，应设为 false 并提取出 direction。"""

JD_ANALYSIS_SYSTEM_PROMPT = """分析以下 JD（职位描述），提取结构化信息。
输出 JSON，字段：company, role, key_skills(list), focus_areas(list), difficulty(easy/medium/hard/faang)。
JD 内容：
{jd_raw}"""

QUESTION_GEN_SYSTEM_PROMPT = """你是专业面试出题官。根据以下信息生成面试题。

要求：
1. 必须生成正好 {count} 道题目。
2. 请使用「中文」出题。
3. 题目优先级分配：
   - 若有薄弱点，针对薄弱点的题目排在最前（分配 priority=1,2）。
   - 其余题目分配 priority=3,4,5。
4. 结合候选人真实项目经历出具体问题（如果有故事库）。
5. 题目类型: technical/behavioral/system_design 各占比均衡。
6. 每道题输出 JSON: {{"id":N,"question":"...","category":"...","focus_area":"...","priority":N}}
7. 输出纯 JSON 数组，不要任何其他内容。

练习上下文：
练习方向：{direction}
目标岗位：{target_role}
{jd_context_block}
{weak_areas_block}
{star_stories_block}"""
