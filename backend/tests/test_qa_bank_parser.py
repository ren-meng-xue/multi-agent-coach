"""unit tests for QA bank markdown parser — no DB required."""
import pytest
from app.services.qa_bank import parse_qa_markdown


def test_parse_happy_path():
    content = """\
## 技术题

### 题目 1
**问题：** 解释 RAG 的原理
**参考答案：** RAG 是检索增强生成
**标签：** AI, RAG, 检索增强

---

## HR题

### 题目 1
**问题：** 介绍一下你自己
**参考答案：** 我有 5 年经验
**标签：** 自我介绍

---

## 项目讲解

### 题目 1
**问题：** 介绍你的项目
**参考答案：** 这个项目的核心是
**标签：** AI Agent

---
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 3
    assert skipped == 0
    assert items[0].category == "technical"
    assert items[0].question == "解释 RAG 的原理"
    assert items[0].model_answer == "RAG 是检索增强生成"
    assert items[0].tags == ["AI", "RAG", "检索增强"]
    assert items[1].category == "hr"
    assert items[2].category == "project"


def test_new_project_label():
    content = """\
## 项目经验

### 题目 1
**问题：** 介绍你的项目经验
**参考答案：** 我的项目经验包括...
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 1
    assert items[0].category == "project"
    assert items[0].question == "介绍你的项目经验"


def test_skip_item_missing_answer():
    content = """\
## 技术题

### 题目 1
**问题：** 解释 RAG

---
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 0
    assert skipped == 1


def test_skip_item_missing_question():
    content = """\
## 技术题

### 题目 1
**参考答案：** 答案内容

---
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 0
    assert skipped == 1


def test_optional_tags():
    content = """\
## 技术题

### 题目 1
**问题：** 问题内容
**参考答案：** 答案内容

---
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 1
    assert items[0].tags is None


def test_partial_section_only():
    content = """\
## 技术题

### 题目 1
**问题：** Q1
**参考答案：** A1

---

### 题目 2
**问题：** Q2
**参考答案：** A2
**标签：** tag1, tag2

---
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 2
    assert all(i.category == "technical" for i in items)
    assert items[1].tags == ["tag1", "tag2"]


def test_unknown_section_ignored():
    content = """\
## 未知分类

### 题目 1
**问题：** Q
**参考答案：** A

---

## 技术题

### 题目 1
**问题：** Valid Q
**参考答案：** Valid A

---
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 1
    assert items[0].category == "technical"


def test_empty_content():
    items, skipped = parse_qa_markdown("")
    assert items == []
    assert skipped == 0


def test_mixed_valid_and_skipped():
    content = """\
## 技术题

### 题目 1
**问题：** Q1
**参考答案：** A1

---

### 题目 2
**问题：** Q2 no answer

---

### 题目 3
**问题：** Q3
**参考答案：** A3

---
"""
    items, skipped = parse_qa_markdown(content)
    assert len(items) == 2
    assert skipped == 1
