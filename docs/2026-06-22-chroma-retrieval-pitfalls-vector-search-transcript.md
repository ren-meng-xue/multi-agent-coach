# 原始字幕：吴恩达 AI 高级检索 p03 — 检索的陷阱：简单向量搜索何时失效

来源：https://www.bilibili.com/video/BV1D3jB6TE2V?p=3
作者：明文传输不（B 站）/ 原课程：Anton Troynikov（Chroma 联合创始人）× DeepLearning.AI
字幕轨道：**无**（该视频仅有弹幕，无任何文本字幕）

> **说明**：本视频为中文配音课程，B 站平台未生成 AI 字幕。本文档内容基于 DeepLearning.AI 官方课程 Notebook（Lab 2 - Pitfalls of retrieval - when simple vector search fails）重建，逐步还原讲师在视频中演示的内容与说明。原始课程为 _Advanced Retrieval for AI with Chroma_（[deeplearning.ai](https://www.deeplearning.ai/courses/advanced-retrieval-for-ai)）。

---

**[00:00:00]**

在上一讲，我们搭建了基础的 RAG 管道——加载文档、切分、嵌入、存入 Chroma、检索、生成答案。这一讲，我们来看这套基础方案在哪些情况下会失败。

首先加载上一讲已经处理好的 Chroma 集合，不需要重新处理 PDF：

```python
from helper_utils import load_chroma, word_wrap
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

embedding_function = SentenceTransformerEmbeddingFunction()

chroma_collection = load_chroma(
    filename='microsoft_annual_report_2022.pdf',
    collection_name='microsoft_annual_report_2022',
    embedding_function=embedding_function
)
chroma_collection.count()
```

`load_chroma()` 是 `helper_utils` 里封装的工具函数，直接从 PDF 重建 Chroma 集合（内部复用了上一讲的分块和嵌入逻辑）。

**[00:01:30]**

## UMAP 降维可视化——把"看不见"的检索变成可见的

在诊断检索质量之前，我们先把整个文档知识库的嵌入向量投影到二维平面，这样就能直观地看到查询落在哪里、检索到的文档分布在哪里。

```python
import umap
import numpy as np
from tqdm import tqdm

embeddings = chroma_collection.get(include=['embeddings'])['embeddings']
umap_transform = umap.UMAP(random_state=0, transform_seed=0).fit(embeddings)
```

**UMAP（Uniform Manifold Approximation and Projection）** 是一种降维算法，它在尽量保留原始高维空间中点与点之间相对距离关系的同时，将约 358 维的嵌入向量压缩到二维。训练完 `umap_transform` 之后，任何新的嵌入向量都可以被投影到同一个二维坐标系中。

**[00:03:00]**

接下来定义投影函数，并把整个数据集的嵌入全部投影到二维：

```python
def project_embeddings(embeddings, umap_transform):
    umap_embeddings = np.empty((len(embeddings), 2))
    for i, embedding in enumerate(tqdm(embeddings)):
        umap_embeddings[i] = umap_transform.transform([embedding])
    return umap_embeddings

projected_dataset_embeddings = project_embeddings(embeddings, umap_transform)
```

```python
import matplotlib.pyplot as plt

plt.figure()
plt.scatter(projected_dataset_embeddings[:, 0], projected_dataset_embeddings[:, 1], s=10)
plt.gca().set_aspect('equal', 'datalim')
plt.title('Projected Embeddings')
plt.axis('off')
```

这张散点图就是整个微软年度报告的"知识地图"——每个点代表一个文本块（chunk），在语义上相近的 chunk 会聚集在一起，形成若干"内容簇"。

**[00:04:30]**

## 可视化实验一：相关性查询（Relevant Query）

第一个测试是一个能在文档中找到答案的问题：

```python
query = "What is the total revenue?"

results = chroma_collection.query(
    query_texts=query,
    n_results=5,
    include=['documents', 'embeddings']
)

retrieved_documents = results['documents'][0]

for document in results['documents'][0]:
    print(word_wrap(document))
    print('')
```

把查询向量和检索结果一起投影到 UMAP 空间：

```python
query_embedding = embedding_function([query])[0]
retrieved_embeddings = results['embeddings'][0]

projected_query_embedding = project_embeddings([query_embedding], umap_transform)
projected_retrieved_embeddings = project_embeddings(retrieved_embeddings, umap_transform)
```

```python
plt.figure()
plt.scatter(projected_dataset_embeddings[:, 0], projected_dataset_embeddings[:, 1], s=10, color='gray')
plt.scatter(projected_query_embedding[:, 0], projected_query_embedding[:, 1], s=150, marker='X', color='r')
plt.scatter(projected_retrieved_embeddings[:, 0], projected_retrieved_embeddings[:, 1], s=100,
            facecolors='none', edgecolors='g')
plt.gca().set_aspect('equal', 'datalim')
plt.title(f'{query}')
plt.axis('off')
```

可视化说明：

- **灰色小点**：整个知识库的所有 chunk
- **红色 X**：用户查询的向量位置
- **绿色圆圈**：检索到的 top-5 文档的向量位置

当检索表现良好时，绿色圆圈会聚集在红色 X 附近，说明检索到的内容与查询语义接近。

**[00:06:00]**

## 可视化实验二：复杂语义查询

```python
query = "What is the strategy around artificial intelligence (AI) ?"
results = chroma_collection.query(query_texts=query, n_results=5, include=['documents', 'embeddings'])
```

这个问题更复杂——"AI 策略"这个概念在文档中可能被多种不同词汇表达（machine learning、cloud services、innovation 等），向量检索需要能跨越这些词汇表达差异，找到语义相关的内容。

对比可视化图可以发现，绿色圆圈的分布比第一个问题更加散开。即使个别检索结果在语义上接近，整体的"凝聚度"也不如精确查询的效果好。

**[00:07:30]**

## 可视化实验三：研发投入查询

```python
query = "What has been the investment in research and development?"
results = chroma_collection.query(query_texts=query, n_results=5, include=['documents', 'embeddings'])
```

研发投入信息分散在年报的多个章节——财务报表、管理层讨论、产品章节都可能有相关内容。这展示了当相关信息在文档中分布较为分散时，向量相似度检索的表现：它会从不同的"知识簇"各取若干 chunk，但这些 chunk 之间缺乏连贯性，可能没有一个能完整回答问题。

**[00:09:00]**

## 可视化实验四："离群查询"——知识库里根本没有答案

```python
query = "What has Michael Jordan done for us lately?"
results = chroma_collection.query(query_texts=query, n_results=5, include=['documents', 'embeddings'])
```

这是最重要的实验。Michael Jordan 完全不在微软年度报告中，但向量检索**仍然会返回 5 个结果**——它找的是"相对最近邻"，而不管这些邻居到底相不相关。

从 UMAP 可视化图可以清楚地看到：查询向量（红色 X）落在整个文档数据云的**边缘甚至外部**，而绿色圆圈是从最近的"数据边界"附近强行取的内容。这些内容与"Michael Jordan"完全无关，但检索系统没有能力说"我不知道"——它永远会返回内容。

**[00:11:00]**

## 这一讲揭示的三类检索失效场景

通过四个实验，可以总结出简单向量搜索的三类根本性缺陷：

**缺陷一：结果分散（Scattered Results / Distractors）**
当用户的查询概念在文档中分布于多个语义聚类时，检索到的 top-k 可能来自完全不同的内容域，每个都"稍微相关"但没有一个完整回答问题。

**缺陷二：语义漂移（Semantic Gap）**
用户用"AI strategy"查询，但文档里用的是"machine learning investment"、"cloud innovation"等表述。基础嵌入不了解任务需求，只能做通用语义匹配，无法针对问题的真正意图做精准对齐。

**缺陷三：无法识别知识边界（Out-of-Distribution Queries）**
当问题的答案根本不在知识库中时，向量检索系统无法识别"我不知道"，会将边界附近最相似的内容强行返回，这是 RAG 系统产生幻觉的重要来源之一。

**[00:12:30]**

## 小结

UMAP 可视化是诊断 RAG 检索质量的强大工具。通过将查询和检索结果投影到二维，可以直观判断：

- 绿色圆圈聚集在红色 X 附近 → 检索质量好
- 绿色圆圈散布在 UMAP 空间各处 → "distractor" 问题，检索结果不聚焦
- 红色 X 在数据云边缘/外部 → 知识库无相关内容，这是高风险情况

这三个问题就是接下来三讲的主题：查询扩展（解决语义漂移）、交叉编码器重排序（解决结果分散）、嵌入适配器（让嵌入模型理解任务需求）。
