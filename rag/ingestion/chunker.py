"""行业化文本分块规则。

针对客服知识库优化：
- 按 Markdown 标题层级切分章节，保留标题链（如「退款流程 / 退货申请」）。
- 识别「问题-答案」配对（Q/问/问题 … A/答/答案），成对保留，避免拆散语义。
- 短文本、口语化片段不做硬切，贪心合并进相邻块，避免语义丢失。
- 相邻块间保留 overlap 重叠窗口，提高检索召回。

对外唯一入口：chunk_text()
"""
from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
QUESTION_TAIL_RE = re.compile(r"[？?]\s*$")
Q_MARKER_RE = re.compile(r"^\s*(问|问题|Q|q)\s*[:：]?\s*")
A_MARKER_RE = re.compile(r"^\s*(答|答案|A|a|回答)\s*[:：]?\s*")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
MIN_SHORT_CHARS = 30  # 低于该长度的块会尽量并入相邻块


@dataclass
class Chunk:
    text: str
    title: str
    chunk_index: int


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _pack_sentences(sentences: list[str], max_chars: int, overlap: int) -> list[str]:
    """贪心打包句子成块，块间用上一块尾部做 overlap 前缀。"""
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_len = 0
    prefix = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if buffer and buffer_len + len(prefix) + len(s) > max_chars:
            text = (prefix + "".join(buffer)).strip()
            chunks.append(text)
            tail = text[-overlap:] if len(text) > overlap else text
            prefix = tail
            buffer, buffer_len = [], 0
        buffer.append(s)
        buffer_len += len(s)
    if buffer:
        text = (prefix + "".join(buffer)).strip()
        chunks.append(text)
    return chunks


def _split_sections(text: str) -> list[tuple[str, str]]:
    """按标题切分为 (标题链, 正文)。标题链用 / 连接。"""
    sections: list[tuple[str, str]] = []
    chain: list[str] = []
    body: list[str] = []

    def flush():
        nonlocal body
        if body or chain:
            sections.append((" / ".join(chain), "\n".join(body)))
        body = []

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            heading = m.group(2).strip()
            # 简化：按标题层级维护链
            chain = chain[: level - 1]
            chain.append(heading)
        else:
            body.append(line)
    flush()
    if not sections:
        sections = [("", text)]
    return sections


def _is_qa_pair(paragraph: str, max_chars: int) -> bool:
    """判断段落是否为可直接整段保留的问题-答案对。"""
    p = paragraph.strip()
    if not p or len(p) > max_chars:
        return False
    first_line = p.splitlines()[0].strip()
    # 以问句开头 或 以问号结尾，且含多个句子（可能带答案）
    return bool(Q_MARKER_RE.match(first_line) or QUESTION_TAIL_RE.search(p))


def chunk_text(text: str, doc_title: str = "", max_chars: int = 400, overlap: int = 50) -> list[Chunk]:
    """把文档正文切成带标题的分块。"""
    max_chars = max(120, min(800, int(max_chars)))
    overlap = max(0, min(120, int(overlap)))
    chunks: list[Chunk] = []
    for title, body in _split_sections(text):
        display_title = f"{doc_title} / {title}".strip(" /") if doc_title else title
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        for para in paragraphs:
            if _is_qa_pair(para, max_chars):
                chunks.append(Chunk(text=para, title=display_title, chunk_index=0))
                continue
            sentences = _split_sentences(para)
            # 短文本：整段作为一块，避免过度切分
            if len(para) <= max_chars:
                chunks.append(Chunk(text=para, title=display_title, chunk_index=0))
            else:
                for packed in _pack_sentences(sentences, max_chars, overlap):
                    if len(packed) < MIN_SHORT_CHARS:
                        continue
                    chunks.append(Chunk(text=packed, title=display_title, chunk_index=0))

    # 回填序号
    for i, c in enumerate(chunks):
        c.chunk_index = i
    return chunks
