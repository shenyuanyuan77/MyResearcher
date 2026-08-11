"""系统日期工具：禁止模型臆测「今天大约是哪天」。"""

from __future__ import annotations

import json
from datetime import date, timedelta

from langchain_core.tools import tool


@tool
def get_system_date(offset_days: int = 0) -> str:
    """获取服务器当前真实日期，并可按天数推算目标日（用于文献时间范围、研究时间线）。

    学术场景：筛选"近 N 年文献"、计算某研究方向的时间跨度、生成时间线时，
    必须先调用本工具获取真实日期，禁止臆测「今天约为 YYYY-MM-DD」。

    Args:
        offset_days: 相对今天的偏移天数。0=今天；近 3 年则配合 -1095 等。

    Returns:
        JSON 字符串：today（今天）、result（today+offset）、offset_days
    """
    try:
        days = int(offset_days or 0)
    except (TypeError, ValueError):
        days = 0
    today = date.today()
    target = today + timedelta(days=days)
    return json.dumps(
        {
            "today": today.isoformat(),
            "result": target.isoformat(),
            "offset_days": days,
            "hint": "时间范围筛选请使用 result（如 year_from）；对外说明可用「截止 result / 近 N 年」",
        },
        ensure_ascii=False,
    )
