"""中文/英文检索分词（供 retriever 与 reranker 共用）。

中文连续片段按双字切分（如「退款流程」→「退款」「款流」「流程」），
英文数字保留整词，无外部分词依赖。
"""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[一-鿿]+")
_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    """中文连续片段按双字切分，英文/数字保留整词。"""
    tokens: list[str] = []
    for part in _WORD_RE.findall(text.lower()):
        tokens.append(part)
    for part in _CJK_RE.findall(text.lower()):
        if len(part) <= 2:
            tokens.append(part)
        else:
            tokens.extend(part[i : i + 2] for i in range(len(part) - 1))
    return tokens
