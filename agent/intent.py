"""意图分层识别：规则快速命中 → LLM 零样本 few-shot 兜底。

- 规则层：关键词匹配，命中即高置信，低延迟（不消耗 LLM）。
- LLM 层：把当前输入 + 近两轮历史意图 + 小样本示例交给模型分类，返回 JSON。
- 歧义消解：输入过短 / LLM 置信度低时，结合历史意图做倾向，仍低则标记需澄清。
"""
from __future__ import annotations

import logging
from typing import Any

from agent.intent_samples import INTENT_LABELS, INTENT_SAMPLES, RULE_KEYWORDS
from bootstrap.settings import settings
from core.exceptions import LLMError
from core.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def classify_by_rule(text: str) -> tuple[str, float, str] | None:
    """规则匹配。返回 (intent, confidence, reason) 或 None。"""
    text_l = text.lower()
    best_intent: str | None = None
    best_hits = 0
    hits_text: list[str] = []
    for intent, keywords in RULE_KEYWORDS.items():
        hits = [k for k in keywords if k.lower() in text_l]
        if len(hits) > best_hits:
            best_intent = intent
            best_hits = len(hits)
            hits_text = hits
    if best_intent and best_hits > 0:
        conf = 0.9 if best_hits >= 2 else 0.85
        return best_intent, conf, f"规则命中关键词: {'、'.join(hits_text)}"
    return None


def _build_llm_prompt(text: str, history_intents: list[str]) -> str:
    labels = "\n".join(f"- {k}：{v}" for k, v in INTENT_LABELS.items())
    examples = "\n".join(
        f"问题：{q} → 意图：{i}" for q, i in INTENT_SAMPLES[:18]
    )
    history_part = ""
    if history_intents:
        history_part = (
            "以下是用户本会话前面的意图序列（由近到远）：\n"
            + " → ".join(history_intents[:4])
            + "\n若本次输入语义不完整，请优先延续最近的意图。\n"
        )
    return (
        "任务：判断客服对话中用户最新一句话的意图。\n"
        f"可选意图：\n{labels}\n"
        f"示例：\n{examples}\n"
        f"{history_part}"
        "仅输出 JSON：{\"intent\": \"<意图代码>\", \"confidence\": 0到1的数字, \"reason\": \"一句话理由\"}\n"
        f"用户最新输入：{text}\n"
    )


async def classify_intent(
    text: str, history_intents: list[str] | None = None
) -> dict[str, Any]:
    """识别意图，返回 {intent, confidence, reason}。"""
    text = (text or "").strip()
    if not text:
        return {"intent": "other", "confidence": 0.0, "reason": "空输入"}

    # 第一层：规则快速命中
    rule = classify_by_rule(text)
    if rule:
        intent, conf, reason = rule
        return {"intent": intent, "confidence": conf, "reason": reason}

    # 第二层：LLM few-shot
    llm = get_llm_client()
    if llm.configured:
        try:
            result = await llm.complete_json(
                system="你是客服意图识别引擎，只输出 JSON。",
                user_prompt=_build_llm_prompt(text, history_intents or []),
            )
            intent = str(result.get("intent", "other")).strip()
            conf = max(0.0, min(1.0, float(result.get("confidence", 0.3))))
            reason = str(result.get("reason", "LLM few-shot 分类"))[:200]
            if intent not in INTENT_LABELS:
                intent = "other"
            return {"intent": intent, "confidence": conf, "reason": reason}
        except LLMError as exc:
            logger.warning("意图识别 LLM 失败，退回规则结果: %s", exc)
        except Exception as exc:
            logger.warning("意图识别异常: %s", exc)

    # 未配置 LLM 或失败：保守返回 other
    return {"intent": "other", "confidence": 0.15, "reason": "无 LLM，规则未命中"}
