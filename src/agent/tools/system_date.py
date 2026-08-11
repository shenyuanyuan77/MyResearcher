"""系统日期工具：禁止模型臆测「今天大约是哪天」。"""

from __future__ import annotations

import json
from datetime import date, timedelta

from langchain_core.tools import tool


@tool
def get_system_date(offset_days: int = 0) -> str:
    """获取服务器当前真实日期，并可按天数推算目标日。

    下单推算 expectedDeliveryDate 时必须先调用本工具，禁止臆测「今天约为 YYYY-MM-DD」。

    Args:
        offset_days: 相对今天的偏移天数。0=今天；交期 4 天则传 4，得到预计交货日。

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
            "hint": "expectedDeliveryDate 请使用 result；对外说明可用「交期 N 天 / 预计 result」",
        },
        ensure_ascii=False,
    )
