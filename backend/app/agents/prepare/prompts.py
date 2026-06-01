# backend/app/agents/prepare/prompts.py
"""Prompt constants for prepare pipeline nodes."""

MASTER_REASONING_PROMPT = """你是面试准备 Master Orchestrator。
分析以下用户信息，使用「中文」逐行输出你的判断（每行以"• "开头）。

【特别警告】：必须严格尊重用户提供的「目标岗位/方向」。
- 如果用户已提供岗位（如「AI Agent 工程师」），严禁将其概括为更宽泛的名称（如「Senior Software Engineer」）。
- 你的分析和决策必须紧紧围绕该具体岗位展开。

用户信息：
{context}

请输出你的分析过程，包括：检查用户档案、确认目标岗位、检查历史情况、确定练习方向、确定调用链。

【输出边界】：
- 这里只展示准备阶段的调度判断，不是候选人能力总结，也不是学习计划。
- 不要输出后续练习建议、学习路径、补课建议或岗位转向建议。
- 不要推断用户需要学习 Node.js、全栈开发等未由资料明确支持的内容。
- 若历史/项目资料为空，只说明“资料不足，将按目标岗位生成通用题”，不要展开建议。

语言简洁，每行不超过40字。"""

MASTER_DECISION_PROMPT = """基于以下用户信息，输出调度决策（JSON）。

【方向识别准则】：
- 优先且完整保留用户提供的「目标岗位/方向」关键词。
- 严禁将具体岗位（如 AI Agent）简化或概括为通用岗位（如 软件工程师）。
- 如果用户未提供方向，再根据 JD 或历史表现进行推断。

用户信息：
{context}

输出字段：
- direction: 识别出的练习方向。必须尽可能具体，反映用户的真实目标。
- chain: 需要调用的子 Agent 列表，从 ["memory_search","jd_analysis","question_gen"] 中选
  - memory_search: 有历史记录时包含
  - jd_analysis: 有 JD 文本时包含
  - question_gen: 始终包含
- need_direction: 布尔值。只有当用户完全没有提供任何关于面试方向、岗位、公司或技术主题的信息时，才为 true。"""

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
