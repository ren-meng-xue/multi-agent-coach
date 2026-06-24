# 基于嵌入的检索概述（Advanced Retrieval for AI with Chroma p02）

## 一句话总结

这一讲手把手搭建最基础的 RAG 管道：PDF → 两步分块 → Sentence Transformers 嵌入 → Chroma 向量数据库 → 余弦相似度检索 → GPT-3.5 生成答案，是后续所有高级检索技术的起点。

## 核心观点

1. **两步分块策略解决嵌入模型窗口限制** — 先用 `RecursiveCharacterTextSplitter`（chunk_size=1000）按语义边界切分，再用 `SentenceTransformersTokenTextSplitter`（tokens_per_chunk=256）按 token 数二次切分。两步分开的原因：第一步保留语义完整性，第二步适配 Sentence Transformers 模型的最大上下文窗口（256 tokens）。直接用 token 切分容易在句子中间切断，语义碎片化。

2. **Chroma 是"零配置"本地向量数据库，内置嵌入函数** — `SentenceTransformerEmbeddingFunction` 封装了 `all-MiniLM-L6-v2` 模型，`chroma_collection.add()` 自动调用嵌入函数，免去手动管理向量的步骤。适合快速原型，支持内存模式（开发测试）和持久化模式（生产存储）。

3. **嵌入模型产生的向量维度决定语义表达能力** — 课程中 Sentence Transformers 产生约 358 维向量（本地轻量模型）；企业级的 text-embedding-ada-002 产生约 1550 维向量，语义细粒度更高但成本更大。维度越高，区分相似含义的能力越强，同时存储和检索成本也越高。

4. **top-k 最近邻检索是基础方案，也是高级技术的对照基准** — `chroma_collection.query(query_texts=[query], n_results=5)` 自动对查询生成嵌入，在向量空间找余弦距离最近的 5 个 chunk。这个方案简单但有固有局限（查询语义与文档语义的偏差、结果同质化等），后续几讲将针对这些问题逐一改进。

5. **RAG 的 system prompt 设计是质量边界** — 课程中的 system prompt 明确限定了三点：角色（财务研究助手）、信息来源约束（only use this information）、任务（回答年度报告相关问题）。这种设计能有效减少 LLM 使用训练集知识"发挥"，提高答案可追溯性。

6. **这一讲的目的是建立基准，而非给出最优方案** — 完整的基础 RAG 管道（5 步）本身并不是课程重点，而是作为"对照组"存在。下一讲会展示这套方案在什么情况下失败（pitfalls），从而引出后续三种高级技术：查询扩展、交叉编码器重排序、嵌入适配器。

## 时间线笔记

| 时间点 | 内容                                                                      |
| ------ | ------------------------------------------------------------------------- |
| 00:00  | 课程注意事项：警告可忽略，LLM 输出不确定                                  |
| 00:01  | 本讲定位：基础 RAG 管道，后续高级技术的起点                               |
| 01:00  | Step 1：用 pypdf 加载 PDF，逐页提取并过滤空页                             |
| 02:30  | Step 2a：RecursiveCharacterTextSplitter 字符级切分（chunk_size=1000）     |
| 04:00  | Step 2b：SentenceTransformersTokenTextSplitter token 级切分（256 tokens） |
| 05:30  | Step 3a：SentenceTransformerEmbeddingFunction 生成 ~358 维嵌入            |
| 07:00  | Step 3b：创建 Chroma 集合，add() 自动嵌入并存储                           |
| 08:30  | Step 4：query() 向量相似度检索，返回 top-5 文档块                         |
| 10:00  | Step 5a：rag() 函数设计，system prompt 限定信息来源                       |
| 12:00  | Step 5b：调用 GPT-3.5-turbo 生成最终答案                                  |
| 13:30  | 小结：5 步 RAG 完整流程回顾                                               |

## RAG 基础管道五步

```
PDF/文档
    ↓ pypdf 提取文本
字符级切分（chunk_size=1000，RecursiveCharacterTextSplitter）
    ↓
Token 级切分（tokens_per_chunk=256，适配嵌入模型窗口）
    ↓
SentenceTransformers 嵌入（~358 维）→ 存入 Chroma
    ↓
用户查询 → 嵌入 → 向量相似度检索（top-k）
    ↓
检索结果 + 查询 → LLM（GPT-3.5-turbo）→ 最终答案
```

## 可执行建议

- **分块顺序不能颠倒**：先字符级、再 token 级，反过来（先 token 切分）容易在句子中间断开，语义完整性差。
- **tokens_per_chunk 必须匹配你的嵌入模型**：Sentence Transformers（all-MiniLM-L6-v2）上限是 256 tokens；用 OpenAI text-embedding-ada-002 时上限约 8191 tokens，可以显著加大 chunk 大小。
- **Chroma 内存模式用于开发，持久化模式用于生产**：`chromadb.Client()` 是内存模式，进程结束后数据消失；`chromadb.PersistentClient(path="./db")` 保存到本地磁盘。
- **system prompt 加"只能使用以下信息"约束**：明确告诉 LLM 只能基于检索到的文档回答，可有效减少"凭记忆编造"的幻觉。
- **用这个基础管道作为你的 baseline**：在引入查询扩展、重排序等高级技术之前，先跑通这个基础版本并记录性能指标，后续改进才有对比依据。
- **UMAP 可视化是诊断检索质量的工具**：后续课程会用 UMAP 将高维向量投影到二维，可视化检索结果的分布，直观判断检索是否命中目标区域（课程后续讲义中使用）。

## 关键术语

| 术语                                  | 说明                                                           |
| ------------------------------------- | -------------------------------------------------------------- |
| RAG（Retrieval-Augmented Generation） | 检索增强生成，先检索相关文档再让 LLM 生成答案                  |
| Embedding（嵌入向量）                 | 将文本转换为固定维度浮点数向量，语义相近的文本在向量空间距离近 |
| Chroma                                | 开源轻量向量数据库，零依赖部署，开发友好                       |
| Sentence Transformers                 | 开源嵌入模型库，`all-MiniLM-L6-v2` 是其常用轻量模型            |
| RecursiveCharacterTextSplitter        | LangChain 中按字符和语义边界递归切分文本的工具                 |
| SentenceTransformersTokenTextSplitter | 按 token 数切分，确保 chunk 不超过嵌入模型上下文窗口           |
| top-k 检索                            | 返回向量距离最近的 k 个文档块（本课 k=5）                      |
| 余弦相似度                            | 衡量两个向量方向相似程度的指标，Chroma 默认使用                |
| chunk_overlap                         | 相邻文本块之间的重叠 token 数，本课设为 0                      |
| UMAP                                  | 降维可视化技术，用于将高维嵌入投影到二维平面以便检查           |

## 适合谁看

- 正在学习 RAG 应用开发、想从零搭建检索管道的工程师
- 了解 LLM 基础概念，想进一步学习向量数据库使用的开发者
- 准备面试，需要能演示完整 RAG 流程的候选人
- 已有 RAG 经验，想回顾基础后对比理解高级技术差异的研究者

## 来源与限制

- **原始视频无文字字幕**：B 站视频（BV1D3jB6TE2V p=2）仅有弹幕（danmaku），无任何 AI 生成或人工字幕，字幕原文文件内容基于官方课程 Notebook 重建
- **内容来源**：DeepLearning.AI 课程 _Advanced Retrieval for AI with Chroma_，讲师为 Anton Troynikov（Chroma 联合创始人），Lab 1 Notebook 通过 GitHub 公开仓库获取
- **Notebook 与视频存在少量差异**：公开 Notebook 为"student 版本"（部分代码留空供练习），视频中可能有更多口头解释未被捕获
- **模型版本已过时**：课程使用 GPT-3.5-turbo 和 all-MiniLM-L6-v2，现已有更新更强的选项；但检索架构的设计原则不变
- **B 站 UP 主**：明文传输不，提供中文配音版本，原始英文版在 [DeepLearning.AI 平台](https://www.deeplearning.ai/courses/advanced-retrieval-for-ai)
