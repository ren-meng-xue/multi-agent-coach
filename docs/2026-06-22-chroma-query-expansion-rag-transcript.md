# 原始字幕：吴恩达 AI 高级检索 p04 — 查询扩展

来源：https://www.bilibili.com/video/BV1D3jB6TE2V?p=4
作者：明文传输不（B 站）/ 原课程：Anton Troynikov（Chroma 联合创始人）× DeepLearning.AI
字幕轨道：**无**（该视频仅有弹幕，无任何文本字幕）

> **说明**：本视频为中文配音课程，B 站平台未生成 AI 字幕。本文档内容基于 DeepLearning.AI 官方课程 Notebook（Lab 3 - Query Expansion）重建，逐步还原讲师在视频中演示的内容与说明。原始课程为 _Advanced Retrieval for AI with Chroma_（[deeplearning.ai](https://www.deeplearning.ai/courses/advanced-retrieval-for-ai)）。

---

**[00:00:00]**

上一讲我们看到简单向量搜索的三类失效场景，其中最核心的问题是：嵌入模型在编码时不了解任务需求，导致查询向量与真正包含答案的文档向量之间存在语义偏差。这一讲介绍第一类解决方案：**查询扩展（Query Expansion）**——用 LLM 来增强或扩展原始查询，让检索"瞄得更准"。

初始化环境，加载已有的 Chroma 集合并训练 UMAP：

```python
from helper_utils import load_chroma, word_wrap, project_embeddings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

embedding_function = SentenceTransformerEmbeddingFunction()

chroma_collection = load_chroma(
    filename='microsoft_annual_report_2022.pdf',
    collection_name='microsoft_annual_report_2022',
    embedding_function=embedding_function
)

import umap

embeddings = chroma_collection.get(include=['embeddings'])['embeddings']
umap_transform = umap.UMAP(random_state=0, transform_seed=0).fit(embeddings)
projected_dataset_embeddings = project_embeddings(embeddings, umap_transform)
```

**[00:01:30]**

## 技术一：用假设性答案扩展查询（Expansion with Generated Answers）

这个技术来自论文 [HyDE：Precise Zero-Shot Dense Retrieval without Relevance Labels](https://arxiv.org/abs/2305.03653)。

**核心思路**：让 LLM 先"脑补"一个假设性答案，然后用"原始查询 + 假设性答案"的拼接文本做检索，而不是只用原始查询。

为什么这样有效？当 LLM 生成假设答案时，它会使用年度报告中可能出现的行文风格和词汇——这使得拼接后的向量更接近真实文档所在的语义区域。

```python
def augment_query_generated(query, model="gpt-3.5-turbo"):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful expert financial research assistant. "
                       "Provide an example answer to the given question, that might be found "
                       "in a document like an annual report."
        },
        {"role": "user", "content": query}
    ]

    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
    )
    content = response.choices[0].message.content
    return content
```

关键在 system prompt：**"provide an example answer that might be found in a document like an annual report"**——这让 LLM 模仿年报的语言风格写答案，而不是给出通用的解释性答案。

**[00:03:30]**

实际使用：

```python
original_query = "Was there significant turnover in the executive team?"
hypothetical_answer = augment_query_generated(original_query)

joint_query = f"{original_query} {hypothetical_answer}"
print(word_wrap(joint_query))
```

拼接后的 `joint_query` 可能长这样（示例）：

> "Was there significant turnover in the executive team? During fiscal year 2022, Microsoft experienced several key leadership transitions. Satya Nadella continued as CEO while Amy Hood served as CFO. The company appointed..."

然后用这个扩展后的查询去检索：

```python
results = chroma_collection.query(
    query_texts=joint_query,
    n_results=5,
    include=['documents', 'embeddings']
)
retrieved_documents = results['documents'][0]

for doc in retrieved_documents:
    print(word_wrap(doc))
    print('')
```

**[00:05:00]**

### UMAP 可视化：对比原始查询 vs 扩展查询

```python
retrieved_embeddings = results['embeddings'][0]
original_query_embedding = embedding_function([original_query])
augmented_query_embedding = embedding_function([joint_query])

projected_original_query_embedding = project_embeddings(original_query_embedding, umap_transform)
projected_augmented_query_embedding = project_embeddings(augmented_query_embedding, umap_transform)
projected_retrieved_embeddings = project_embeddings(retrieved_embeddings, umap_transform)
```

```python
import matplotlib.pyplot as plt

plt.figure()
plt.scatter(projected_dataset_embeddings[:, 0], projected_dataset_embeddings[:, 1], s=10, color='gray')
plt.scatter(projected_retrieved_embeddings[:, 0], projected_retrieved_embeddings[:, 1], s=100, facecolors='none', edgecolors='g')
plt.scatter(projected_original_query_embedding[:, 0], projected_original_query_embedding[:, 1], s=150, marker='X', color='r')
plt.scatter(projected_augmented_query_embedding[:, 0], projected_augmented_query_embedding[:, 1], s=150, marker='X', color='orange')

plt.gca().set_aspect('equal', 'datalim')
plt.title(f'{original_query}')
plt.axis('off')
```

图中新增了**橙色 X**（扩展后的查询向量），与红色 X（原始查询）对比，可以看到：

- 橙色 X 通常会移动到数据云更密集的区域（更接近真实文档）
- 绿色圆圈（检索结果）会比纯用原始查询时更聚集，且更靠近数据云中心

**[00:07:00]**

## 技术二：多查询扩展（Expansion with Multiple Queries）

第二个技术思路不同：不是生成假设答案，而是让 LLM 从不同角度将原始问题**拆解成多个子问题**，分别检索，然后合并去重结果。

```python
def augment_multiple_query(query, model="gpt-3.5-turbo"):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful expert financial research assistant. "
                       "Your users are asking questions about an annual report. "
                       "Suggest up to five additional related questions to help them find "
                       "the information they need, for the provided question. "
                       "Suggest only short questions without compound sentences. "
                       "Suggest a variety of questions that cover different aspects of the topic. "
                       "Make sure they are complete questions, and that they are related to the original question. "
                       "Output one question per line. Do not number the questions."
        },
        {"role": "user", "content": query}
    ]

    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
    )
    content = response.choices[0].message.content
    content = content.split("\n")
    return content
```

System prompt 的几个关键设计：

- "up to five additional related questions"——扩展为多个维度
- "cover different aspects of the topic"——确保多样性，避免生成重复问题
- "Output one question per line. Do not number the questions."——格式控制，便于 `.split("\n")` 解析

**[00:09:00]**

实际使用：

```python
original_query = "What were the most important factors that contributed to increases in revenue?"
augmented_queries = augment_multiple_query(original_query)

for query in augmented_queries:
    print(query)
```

LLM 可能生成（示例）：

> "What product lines drove the highest revenue growth?"
> "How did cloud services contribute to overall revenue?"
> "What geographic regions showed the strongest revenue increases?"
> "How did acquisitions impact total revenue?"
> "What was the year-over-year revenue change for each business segment?"

**[00:09:45]**

将原始查询和所有扩展查询一起批量检索，并去重：

```python
queries = [original_query] + augmented_queries
results = chroma_collection.query(query_texts=queries, n_results=5, include=['documents', 'embeddings'])

retrieved_documents = results['documents']

# 去重
unique_documents = set()
for documents in retrieved_documents:
    for document in documents:
        unique_documents.add(document)
```

去重是关键步骤——多个查询可能检索到同一个 chunk，使用 Python `set` 自动去除重复文档。最终传给 LLM 的只有去重后的唯一文档集合。

UMAP 可视化中，会看到**多个橙色 X**（每个子问题一个），它们散布在数据云不同位置，而绿色圆圈从多个方向覆盖，比单一查询检索到更广泛的相关内容。

**[00:10:30]**

## 两种技术的对比

| 维度         | 假设答案扩展（HyDE）                       | 多查询扩展                             |
| ------------ | ------------------------------------------ | -------------------------------------- |
| 原理         | 模拟文档语言风格，拉近查询与文档的语义距离 | 多角度覆盖，扩大召回范围               |
| LLM 调用次数 | 1 次                                       | 1 次（但生成多个问题）                 |
| 检索次数     | 1 次（拼接后的单个查询）                   | N 次（原始 + 扩展问题各一次）          |
| 适合场景     | 查询词与文档词不匹配、语义漂移             | 问题有多个子维度、需要更广覆盖         |
| 主要风险     | LLM 生成的假设答案可能偏离事实，引入噪音   | 扩展问题可能偏题，token 消耗和延迟更高 |

这一讲的核心洞察：**语义漂移问题的根源是"查询太短、信息太少"**，通过 LLM 增加信息量，可以让嵌入向量更准确地落在含有答案的文档区域。
