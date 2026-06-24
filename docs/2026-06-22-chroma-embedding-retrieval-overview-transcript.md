# 原始字幕：吴恩达 AI 高级检索 p02 — 基于嵌入的检索概述

来源：https://www.bilibili.com/video/BV1D3jB6TE2V?p=2
作者：明文传输不（B 站）/ 原课程：Anton Troynikov（Chroma 联合创始人）× DeepLearning.AI
字幕轨道：**无**（该视频仅有弹幕，无任何文本字幕）

> **说明**：本视频为中文配音课程，B 站平台未生成 AI 字幕。本文档内容基于 DeepLearning.AI 官方课程 Notebook（Lab 1 - Overview of embeddings-based retrieval）重建，逐步还原讲师在视频中演示的内容与说明。原始课程为 _Advanced Retrieval for AI with Chroma_（[deeplearning.ai](https://www.deeplearning.ai/courses/advanced-retrieval-for-ai)）。

---

**[00:00:00]**

欢迎来到本课程！在开始之前，先说几点关于课程 Notebook 的注意事项：运行 Notebook 时会弹出一些警告，这是正常的，可以忽略。另外，某些操作（例如调用 LLM，或使用生成数据的操作）会返回不确定的结果，所以你的 Notebook 输出可能与视频中看到的不完全一致。

本课（第 2 讲）是整个课程的基础篇，介绍基于嵌入的检索是什么，以及如何搭建一个最基本的 RAG（检索增强生成）管道。

**[00:01:00]**

## 第一步：加载 PDF 文档

我们使用一份真实的文档作为示例——微软 2022 年年度报告（Microsoft Annual Report 2022）。

```python
from pypdf import PdfReader

reader = PdfReader("microsoft_annual_report_2022.pdf")
pdf_texts = [p.extract_text().strip() for p in reader.pages]

# 过滤空字符串
pdf_texts = [text for text in pdf_texts if text]

print(word_wrap(pdf_texts[0]))
```

我们用 `PdfReader` 逐页提取文本，然后过滤掉空白页。这份年度报告包含大量财务数据和公司运营信息，是测试 RAG 问答系统的好素材。

**[00:02:30]**

## 第二步：文本分块（Text Splitting）

原始 PDF 文本太长，无法直接放入嵌入模型的上下文窗口，需要先切分成小块（chunks）。我们用两步切分策略：

**第一步：字符级切分**

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

character_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n", ". ", " ", ""],
    chunk_size=1000,
    chunk_overlap=0
)
character_split_texts = character_splitter.split_text('\n\n'.join(pdf_texts))

print(word_wrap(character_split_texts[10]))
print(f"\nTotal chunks: {len(character_split_texts)}")
```

`RecursiveCharacterTextSplitter` 会按优先级尝试不同的分隔符：先按段落（`\n\n`），再按行（`\n`），再按句子（`. `），最后按空格。这样能尽量保持语义完整性。

**[00:04:00]**

**第二步：Token 级切分**

```python
from langchain.text_splitter import SentenceTransformersTokenTextSplitter

token_splitter = SentenceTransformersTokenTextSplitter(chunk_overlap=0, tokens_per_chunk=256)

token_split_texts = []
for text in character_split_texts:
    token_split_texts += token_splitter.split_text(text)

print(word_wrap(token_split_texts[10]))
print(f"\nTotal chunks: {len(token_split_texts)}")
```

为什么要做第二步切分？因为我们接下来要用 Sentence Transformers 做嵌入，而它的上下文窗口最大只有 **256 个 token**。如果 chunk 超过这个长度，内容会被截断，导致嵌入质量下降。所以这一步将字符级 chunk 再按 256 个 token 切分，确保每个块都能完整进入嵌入模型。

**[00:05:30]**

## 第三步：生成嵌入向量并存入 Chroma

```python
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

embedding_function = SentenceTransformerEmbeddingFunction()
print(embedding_function([token_split_texts[10]]))
```

`SentenceTransformerEmbeddingFunction` 使用本地的 `all-MiniLM-L6-v2` 模型，将每个文本块转换成一个 **约 358 维的向量**。维度越高，能捕获的语义信息越丰富，但也需要更多的存储和计算资源。

**[00:07:00]**

接下来，创建 Chroma 集合并将所有文本块及其嵌入存入数据库：

```python
chroma_client = chromadb.Client()
chroma_collection = chroma_client.create_collection(
    "microsoft_annual_report_2022",
    embedding_function=embedding_function
)

ids = [str(i) for i in range(len(token_split_texts))]

chroma_collection.add(ids=ids, documents=token_split_texts)
chroma_collection.count()
```

`chroma_collection.add()` 会自动调用 `embedding_function` 对每个文档块生成嵌入，然后把文本和对应的向量一起存入 Chroma。`chroma_collection.count()` 可以验证存储了多少个 chunk。

**[00:08:30]**

## 第四步：检索——向量相似度查询

现在来做最基础的检索。给定一个用户问题，我们将它转换成向量，然后在数据库里找最近邻：

```python
query = "What was the total revenue?"

results = chroma_collection.query(query_texts=[query], n_results=5)
retrieved_documents = results['documents'][0]

for document in retrieved_documents:
    print(word_wrap(document))
    print('\n')
```

`query_texts=[query]` 会自动对查询文本调用同一个嵌入函数，生成查询向量，然后在 Chroma 中找出向量距离最近的 5 个文档块。这就是所谓的"基于嵌入的相似度检索"（embedding-based similarity retrieval）。

**[00:10:00]**

## 第五步：生成答案——构建完整的 RAG 管道

有了检索到的文档，接下来把它们交给 LLM 来生成最终答案：

```python
import openai
from openai import OpenAI

openai_client = OpenAI()

def rag(query, retrieved_documents, model="gpt-3.5-turbo"):
    information = "\n\n".join(retrieved_documents)

    messages = [
        {
            "role": "system",
            "content": "You are a helpful expert financial research assistant. "
                       "Your users are asking questions about information contained in an annual report. "
                       "You will be shown the user's question, and the relevant information from the annual report. "
                       "Answer the user's question using only this information."
        },
        {"role": "user", "content": f"Question: {query}. \n Information: {information}"}
    ]

    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
    )
    content = response.choices[0].message.content
    return content

output = rag(query=query, retrieved_documents=retrieved_documents)
print(word_wrap(output))
```

**[00:12:00]**

`rag()` 函数做了三件事：

1. 把检索到的文档块拼接成一个 `information` 字符串
2. 构造系统提示词，告诉模型它是一个财务研究助手，只能基于提供的信息回答
3. 将问题和文档一起发给 GPT-3.5-turbo，得到最终答案

这就是最基础的 RAG 管道：**检索 → 增强提示 → 生成（Retrieve → Augment → Generate）**。

**[00:13:30]**

## 小结

本讲演示了一个完整的基础 RAG 流程：

1. **加载文档**：用 `pypdf` 提取 PDF 文本
2. **分块**：两步切分——字符级（保语义完整）+ Token 级（适配嵌入模型窗口）
3. **嵌入 + 存储**：用 Sentence Transformers 生成向量，存入 Chroma
4. **检索**：向量相似度查询（top-k 最近邻）
5. **生成**：把检索结果传给 LLM，生成最终答案

这是后续所有高级检索技术的出发点。在下一讲，我们会看到这套基础方案的局限——为什么简单的向量相似度检索会失败。
