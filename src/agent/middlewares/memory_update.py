"""
自动记忆更新中间件（学术版）。

在每轮 Agent 回复完成后（aafter_agent 钩子），自动提取对话中涉及的学术实体
（研究方向、认知等级、偏好语言、研究主题、读过的论文），更新 Store 中的用户偏好。

伴随式成长（千人千面）的真实落地：用户的 research_direction / cognitive_level /
research_topics 会跨会话累积，下次对话自动注入 ResearchContext。

使用方式:
    from agent.middlewares.memory_update import MemoryUpdateMiddleware
    middleware = MemoryUpdateMiddleware(model=SUMMARY_MODEL)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from agent.intent_router import is_quick_lookup

logger = logging.getLogger(__name__)

# 触发自动更新的学术关键词（中英文）
_TRIGGER_KEYWORDS = [
    # 研究行为
    "研究", "方向", "领域", "课题", "选题", "开题", "综述", "文献",
    "精读", "审稿", "投稿", "期刊", "会议", "论文", "导师", "实验",
    "数据集", "方法", "模型", "算法", "baseline", "消融", "对比",
    "跨界", "融合", "推演", "可行性", "创新点", "贡献",
    # 认知/阶段
    "开题", "中期", "答辩", "毕业", "博一", "博二", "研一", "研二",
    # 语言偏好
    "中文", "英文", "English", "Chinese",
    # 研究动词
    "检索", "查", "找", "读", "写", "分析", "总结", "提炼", "对比", "评估",
    # 英文触发
    "research", "paper", "literature", "review", "survey", "topic",
    "direction", "field", "domain", "method", "experiment", "dataset",
]

# 跳过更新的无意义消息模式
_SKIP_PATTERNS = [
    "你好", "在吗", "嗨", "hello", "hi", "hey",
    "你能做什么", "你有哪些功能", "你是谁",
    "我之前的偏好", "我的偏好", "我的记忆",
    "谢谢", "感谢", "thanks", "ok", "好的",
]


def _extract_last_user_message(messages: List[BaseMessage]) -> Optional[str]:
    """从消息列表末尾找到最后一条用户消息，返回其文本内容。"""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            content = msg.content
            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            content = str(content).strip()
            return content if content else None
    return None


def _is_meaningful_academic_exchange(messages: List[BaseMessage]) -> Optional[str]:
    """检查最后一条用户消息是否为有意义的学术交互。

    Returns:
        用户消息文本（有意义时），或 None（应跳过）。
    """
    last_user_msg_text = _extract_last_user_message(messages)
    if last_user_msg_text is None:
        return None

    # 跳过无意义消息
    content_lower = last_user_msg_text.lower().replace(" ", "")
    for pattern in _SKIP_PATTERNS:
        if pattern.lower().replace(" ", "") in content_lower:
            return None

    # 检查是否包含学术关键词
    has_academic_keyword = any(
        kw.lower() in content_lower for kw in _TRIGGER_KEYWORDS
    )
    if has_academic_keyword:
        return last_user_msg_text

    # 兜底：检查是否委派了子 Agent（messages 中有 task 工具调用）
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "task":
                    return last_user_msg_text
    return None


def _is_quick_lookup(user_message: str) -> bool:
    """单点查询：跳过记忆 LLM，节省 token。与 intent_router 同一套规则。"""
    return is_quick_lookup(user_message)


def _extract_ai_summary(messages: List[BaseMessage]) -> str:
    """提取最后一条 AI 消息的前 400 字符作为摘要。"""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai":
            content = msg.content
            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content)[:400]
    return ""


async def _extract_academic_entities(
    model: BaseChatModel, user_message: str, ai_summary: str
) -> Dict[str, Any]:
    """使用 LLM 从对话中提取学术实体。

    Returns:
        {
            "research_direction": str,   # 研究方向（如"联邦学习+医疗影像"）
            "cognitive_level": str,      # 认知等级 novice|intermediate|advanced|expert
            "preferred_language": str,   # 偏好语言 zh|en|bilingual
            "research_topics": list[str],# 研究主题/关键词
            "papers_read": list[str],    # 本次提到的论文标题/DOI
        }
    """
    prompt = f"""Extract academic research entities from this conversation.

Rules:
1. "research_direction": The user's research direction/field (e.g. "federated learning for medical imaging"). Empty string if not inferable.
2. "cognitive_level": User's academic level — one of: novice (undergrad/early master), intermediate (senior master), advanced (PhD candidate), expert (postdoc/faculty). Empty string if unclear.
3. "preferred_language": User's preferred working language — "zh", "en", or "bilingual". Empty string if unclear.
4. "research_topics": 0-8 specific research topics/keywords discussed (e.g. ["differential privacy", "CNN", "MRI segmentation"]). Empty list if none.
5. "papers_read": Paper titles or DOIs explicitly discussed/read this turn. Empty list if none.

User message: {user_message}

Assistant response summary: {ai_summary}

Return ONLY a JSON object, no other text:
{{"research_direction": "", "cognitive_level": "", "preferred_language": "", "research_topics": [], "papers_read": []}}"""

    try:
        response = await model.ainvoke(prompt)
        text = response.content
        if isinstance(text, list):
            text = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in text
            )
        text = str(text).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = json.loads(text[start:end + 1])
            return {
                "research_direction": str(raw.get("research_direction", "") or "").strip(),
                "cognitive_level": str(raw.get("cognitive_level", "") or "").strip(),
                "preferred_language": str(raw.get("preferred_language", "") or "").strip(),
                "research_topics": [
                    str(t).strip() for t in raw.get("research_topics", []) if str(t).strip()
                ][:8],
                "papers_read": [
                    str(p).strip() for p in raw.get("papers_read", []) if str(p).strip()
                ][:10],
            }
    except Exception:
        logger.warning("MemoryUpdateMiddleware: LLM 提取失败，跳过本次更新", exc_info=True)

    return {
        "research_direction": "",
        "cognitive_level": "",
        "preferred_language": "",
        "research_topics": [],
        "papers_read": [],
    }


def _create_file_value(content_str: str) -> dict:
    """创建 Store 兼容的文件值（与 deepagents.backends.utils.create_file_data 一致）。"""
    lines = content_str.split("\n")
    now = datetime.now(timezone.utc).isoformat()
    return {
        "content": lines,
        "created_at": now,
        "modified_at": now,
    }


class MemoryUpdateMiddleware(AgentMiddleware):
    """在 Agent 回复后自动更新用户记忆（学术偏好，跨会话持久化）。

    提取 research_direction / cognitive_level / preferred_language /
    research_topics / papers_read，合并写入 Store。
    """

    def __init__(self, model: BaseChatModel) -> None:
        super().__init__()
        self.model = model

    # ---- 同步钩子（不执行操作）----
    def after_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        return None

    # ---- 异步钩子（核心逻辑）----
    async def aafter_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        """Agent 回复完成后触发：提取学术实体并更新记忆。"""
        try:
            # 1. 获取 user_id
            ctx = getattr(runtime, "context", None)
            if ctx is None:
                return None
            user_id = getattr(ctx, "user_id", None)
            if not user_id:
                return None

            # 2. 获取消息列表
            messages: List[BaseMessage] = state.get("messages", [])
            if not messages:
                return None

            # 3. 判断是否需要更新
            user_message = _is_meaningful_academic_exchange(messages)
            if user_message is None:
                return None

            # 3.5 快速查询不跑记忆 LLM（省一轮模型调用）
            if _is_quick_lookup(user_message):
                logger.info(
                    "MemoryUpdateMiddleware: 跳过快速查询的记忆 LLM user=%s",
                    user_id,
                )
                return None

            # 4. 提取 AI 摘要
            ai_summary = _extract_ai_summary(messages)

            # 5. LLM 提取学术实体
            extracted = await _extract_academic_entities(
                self.model, user_message, ai_summary
            )
            has_data = any(extracted.values())
            if not has_data:
                return None

            logger.info(
                f"MemoryUpdateMiddleware: user={user_id}, "
                f"direction={extracted['research_direction'][:40]}, "
                f"level={extracted['cognitive_level']}, "
                f"topics={len(extracted['research_topics'])}"
            )

            # 6. 从 store 读取当前偏好
            store = getattr(runtime, "store", None)
            if store is None:
                logger.warning("MemoryUpdateMiddleware: runtime.store 不可用")
                return None

            namespace = (user_id,)
            key = "preferences"

            try:
                item = await store.aget(namespace, key)
            except Exception:
                item = None

            # 7. 解析现有内容
            current_prefs: Dict[str, Any] = {}
            if item is not None and hasattr(item, "value"):
                value = item.value
                if isinstance(value, dict):
                    # 优先取 value 里的 dict（持久化时存的 JSON）
                    content = value.get("content", value)
                    if isinstance(content, dict):
                        current_prefs = content
                    elif isinstance(content, list):
                        try:
                            current_prefs = json.loads("\n".join(content))
                        except Exception:
                            current_prefs = {}
                    elif isinstance(content, str):
                        try:
                            current_prefs = json.loads(content)
                        except Exception:
                            current_prefs = {}
                elif isinstance(value, str):
                    try:
                        current_prefs = json.loads(value)
                    except Exception:
                        current_prefs = {}

            # 8. 合并并写回
            updated = _merge_preferences(current_prefs, extracted)
            file_value = {
                "content": json.dumps(updated, ensure_ascii=False, indent=2),
                "created_at": current_prefs.get("_created_at") or datetime.now(timezone.utc).isoformat(),
                "modified_at": datetime.now(timezone.utc).isoformat(),
            }
            await store.aput(namespace, key, file_value)

            logger.info(
                f"MemoryUpdateMiddleware: 已更新 {user_id} 的学术记忆 "
                f"(direction={'yes' if extracted['research_direction'] else 'no'}, "
                f"topics={len(extracted['research_topics'])})"
            )

        except Exception:
            logger.warning("MemoryUpdateMiddleware: 更新失败", exc_info=True)

        return None


def _merge_preferences(
    current: Dict[str, Any], extracted: Dict[str, Any]
) -> Dict[str, Any]:
    """将新提取的学术实体合并到现有偏好中。

    策略：
    - research_direction / cognitive_level / preferred_language：新值覆盖旧值（取最新）。
    - research_topics / papers_read：累积去重，分别上限 20 / 50。
    """
    merged: Dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    # 清理历史 schema 残留
    merged.pop("_created_at", None)
    merged.pop("_modified_at", None)

    # 标量字段：新值优先
    for field in ("research_direction", "cognitive_level", "preferred_language"):
        new_val = extracted.get(field, "")
        if new_val:
            merged[field] = new_val
        else:
            merged.setdefault(field, current.get(field, ""))

    # 列表字段：累积去重
    existing_topics = list(merged.get("research_topics") or [])
    for t in extracted.get("research_topics", []):
        if t not in existing_topics:
            existing_topics.append(t)
    merged["research_topics"] = existing_topics[:20]

    existing_papers = list(merged.get("papers_read") or [])
    for p in extracted.get("papers_read", []):
        if p not in existing_papers:
            existing_papers.append(p)
    merged["papers_read"] = existing_papers[:50]

    # 记录更新时间
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()

    return merged
