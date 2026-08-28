"""导出意图小样本为 JSONL 训练集（供后续接入 PEFT 微调）。

用法：
    python -m scripts.export_intent_samples [输出路径]
默认输出 data/intent_samples.jsonl，每行：{"text": "...", "intent": "..."}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from agent.intent_samples import INTENT_SAMPLES


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/intent_samples.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for text, intent in INTENT_SAMPLES:
            f.write(json.dumps({"text": text, "intent": intent}, ensure_ascii=False) + "\n")
    print(f"[export] 已导出 {len(INTENT_SAMPLES)} 条样本 -> {out}")


if __name__ == "__main__":
    main()
