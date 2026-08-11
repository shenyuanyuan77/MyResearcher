"""
研途智探AI · 意图路由（轻量版）。

提供：
  - latest_user_text(messages)：取最近一条用户消息文本
  - routing_notice(context, user_text)：生成本轮硬分流提示（注入 SystemMessage）
  - is_quick_lookup(user_text)：判断是否快速查询（主 Agent 自处理，不委派）

研途五大引擎分流由系统提示词主导，这里仅做轻量提示注入。
"""

from __future__ import annotations

from typing import Any, Optional


def latest_user_text(messages: list[Any]) -> str:
    """取最后一条 HumanMessage 的文本内容。"""
    for m in reversed(messages or []):
        # HumanMessage 的 type 为 "human"，role 为 "user"
        rtype = getattr(m, "type", None) or (
            getattr(m, "role", None) if hasattr(m, "role") else None
        )
        if rtype in {"human", "user"}:
            content = getattr(m, "content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # 取 text 块
                return " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
                )
    return ""


_ENGINES = {
    "方向构建": ["研究方向", "选题", "topic_radar", "方向构建", "开题", "研究计划"],
    "情报提纯": ["检索", "综述", "文献", "paper_search", "情报", "精读", "DOI"],
    "资产透视": ["学者", "导师", "作者", "author_profile", "资产透视", "h指数", "h-index"],
    "跨界启发": ["跨界", "融合", "结合", "交叉", "cross_search", "可行性"],
    "成果审稿": ["审稿", "润色", "修改", "review", "规范", "论文草稿", "我的论文"],
}


def detect_engine(user_text: str) -> Optional[str]:
    """粗判当前问题落在哪个引擎（仅作提示，真正分流由系统提示词+模型完成）。"""
    if not user_text:
        return None
    for engine, kws in _ENGINES.items():
        if any(kw in user_text for kw in kws):
            return engine
    return None


def routing_notice(user_text: str) -> str:
    """生成本轮分流提示（注入为 SystemMessage）。

    注意：ContextInjectionMiddleware 调用签名为 routing_notice(user_text)。
    """
    engine = detect_engine(user_text)
    parts = []
    if engine:
        parts.append(f"【本轮疑似引擎】{engine}。请对照系统提示词的引擎分流规则执行。")
    parts.append("【硬性要求】所有文献类回答必须来自工具召回的真实数据（带 DOI），禁止编造任何文献/作者/DOI。")
    return " ".join(parts)


# 快速查询判定：纯事实查询（查某篇/某作者/某主题文献数量），主 Agent 自处理，不委派子 Agent
_QUICK_PATTERNS = ["帮我查", "这篇", "有几篇", "这个作者", "这篇论文的doi", "查一下", "这个doi"]


def is_quick_lookup(user_text: str) -> bool:
    if not user_text:
        return False
    if any(p in user_text for p in _QUICK_PATTERNS):
        return True
    # 短问题 + 含 DOI/作者名 → 快速查询
    if len(user_text) < 40 and ("doi" in user_text.lower() or "10." in user_text):
        return True
    return False
