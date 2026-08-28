"""生成每日运营报表（可定时任务调用）。

用法：
    python -m scripts.generate_daily_report          # 今日
    python -m scripts.generate_daily_report 2026-08-26
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal, init_db  # noqa: E402
from system.report import generate_daily_report  # noqa: E402


def main() -> None:
    init_db()
    report_date = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
    with SessionLocal() as db:
        report = generate_daily_report(db, report_date)
        print(f"[report] {report.report_date} 生成完成")
        print(f"  问题总量: {report.total_questions}")
        print(f"  已解决: {report.resolved_questions} / 未解决: {report.unresolved_questions}")
        print(f"  转人工: {report.transferred_count}")
        print(f"  平均响应: {report.avg_latency_ms}ms / 缓存命中: {report.cache_hit_rate:.0%}")
        print(f"  高频问题 Top3: {dict(list(report.high_frequency.items())[:3])}")


if __name__ == "__main__":
    main()
