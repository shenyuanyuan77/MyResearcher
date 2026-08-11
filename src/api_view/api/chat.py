"""
对话 API 模块

提供流式对话接口、中断恢复接口和会话状态查询接口
"""

import json
import uuid
import re
import os
import tempfile
from datetime import datetime
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from agent.schema import (
    ChatRequest,
    ChatResponse,
    Message,
)
from api_view.agent_loader import agent_loader
from api_view.auth import UserInfo, get_current_user
from api_view.emit_args_stream import (
    EmitMarkdownStreamer,
    is_emit_research_report_tool,
)
from api_view.observability import write_audit
from api_view.runtime_status import runtime_status


# 创建路由
router = APIRouter()

# 调试日志文件路径（在项目根目录的 temp 文件夹下）
DEBUG_LOG_DIR = os.path.join(tempfile.gettempdir(), "deepagent_debug")
os.makedirs(DEBUG_LOG_DIR, exist_ok=True)


def get_debug_log_path(thread_id: str) -> str:
    """获取当前会话的调试日志文件路径"""
    safe_id = thread_id.replace("/", "_").replace("\\", "_")[:50]
    return os.path.join(DEBUG_LOG_DIR, f"stream_{safe_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")


def write_debug_log(filepath: str, event_type: str, data: dict, raw_token: object = None):
    """写入调试日志"""
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {event_type}\n")
            f.write(f"  data: {json.dumps(data, ensure_ascii=False, default=str)[:2000]}\n")
            if raw_token is not None:
                token_info = {}
                if hasattr(raw_token, 'type'):
                    token_info['type'] = raw_token.type
                if hasattr(raw_token, 'name'):
                    token_info['name'] = raw_token.name
                if hasattr(raw_token, 'content'):
                    c = raw_token.content
                    if isinstance(c, str):
                        token_info['content_preview'] = c[:500]
                    elif isinstance(c, list):
                        token_info['content_len'] = len(c)
                        token_info['content_preview'] = str(c)[:500]
                    else:
                        token_info['content_preview'] = str(c)[:500]
                if hasattr(raw_token, 'tool_call_chunks') and raw_token.tool_call_chunks:
                    token_info['tool_call_chunks'] = str(raw_token.tool_call_chunks)[:500]
                if hasattr(raw_token, 'id'):
                    token_info['id'] = raw_token.id
                f.write(f"  token: {json.dumps(token_info, ensure_ascii=False, default=str)[:2000]}\n")
            f.write("\n")
    except Exception:
        pass  # 调试日志失败不影响主流程


def _load_known_subagents() -> frozenset:
    """从 src/agent/subagents/configs/ 动态加载真实子代理名（.yaml/.yml 文件名去扩展名）。

    历史版本写死了采购项目的虚构子代理名（researcher/general 等），
    实际 configs 目录为空。改为动态加载：有配置文件则用之，否则返回空集
    （extract_subagent_name 会回退到通用 UUID 过滤逻辑）。
    """
    import os
    configs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "agent", "subagents", "configs")
    names = set()
    try:
        if os.path.isdir(configs_dir):
            for fn in os.listdir(configs_dir):
                if fn.endswith((".yaml", ".yml")):
                    names.add(os.path.splitext(fn)[0])
    except OSError:
        pass
    return frozenset(names)


_KNOWN_SUBAGENTS = _load_known_subagents()


def extract_subagent_name(namespace: tuple) -> str:
    """从 namespace 提取子代理逻辑名（优先已知名称，避免 tools:UUID）。"""
    names: list[str] = []
    for segment in namespace:
        if isinstance(segment, str) and segment.startswith("tools:"):
            names.append(segment[len("tools:") :])
    if not names:
        return "main"
    for name in names:
        if name in _KNOWN_SUBAGENTS:
            return name
    for name in names:
        if name and not is_likely_uuid(name):
            return name
    return names[0]


def display_source_for_ui(raw_source: str) -> str:
    """返回可供工作台展示的稳定智能体来源。"""
    return raw_source if raw_source in _KNOWN_SUBAGENTS else "main"


def is_likely_uuid(text: str) -> bool:
    """
    判断文本是否大概率是 UUID（而非有意义的回复内容）
    例如：3576bba4-42e5-a769-c2f7-ea8444829951
    """
    # UUID 格式：8-4-4-4-12
    uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    return bool(re.match(uuid_pattern, text.strip()))


def extract_content_from_token(token) -> str:
    """
    从 token 中提取文本内容

    处理 token.content 可能是字符串、列表或其他类型的情况
    过滤掉明显是 UUID 或无关标识符的内容
    """
    if not hasattr(token, 'content'):
        return ""

    content = token.content

    # 如果 content 是字符串，直接返回
    if isinstance(content, str):
        # 过滤纯 UUID 内容
        if is_likely_uuid(content):
            return ""
        return content

    # 如果 content 是列表，尝试提取其中的文本
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                # 结构化内容：只提取 text 类型，忽略 image_url 等
                item_type = item.get("type", "")
                if item_type == "text":
                    t = item.get("text", "")
                    if not is_likely_uuid(t):
                        text_parts.append(t)
                elif item_type == "image_url":
                    # 图片 URL 不提取为文本，由 serialize_tool_result 处理
                    pass
                elif "text" in item:
                    t = item["text"]
                    if not is_likely_uuid(str(t)):
                        text_parts.append(str(t))
                elif "content" in item:
                    text_parts.append(str(item["content"]))
            else:
                text_parts.append(str(item))
        return ''.join(text_parts)

    # 其他类型转换为字符串
    return str(content) if content is not None else ""


def extract_references_from_tool_result(content) -> list:
    """从学术工具返回的 JSON 结果中提取结构化引用数组（供前端富卡片/[n]气泡）。

    学术工具（paper_search/paper_by_doi/author_profile/cross_search）返回 JSON，
    含 `references` 字段（[{idx,title,authors,year,venue,doi,doi_url,cited_by_count,...}]）。
    """
    if not content:
        return []
    text = content
    if isinstance(content, list):
        # 取 text 块拼接
        text = "".join(
            c.get("text", "") if isinstance(c, dict) else str(c)
            for c in content
        )
    if not isinstance(text, str):
        return []
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            refs = obj.get("references")
            if isinstance(refs, list) and refs:
                return refs
            # 兼容 paper_by_doi 单篇 paper
            paper = obj.get("paper")
            if isinstance(paper, dict) and paper.get("doi"):
                return [paper]
    except Exception:
        return []
    return []


def serialize_tool_result(content) -> dict:
    """
    将工具执行结果序列化为前端可用的结构化数据

    处理 tool 消息的 content，可能是字符串、列表（包含文本和图片）
    提取文本和图片数据，返回结构化字典
    """
    result = {"text": "", "images": []}

    if isinstance(content, str):
        result["text"] = content
        # 提取 markdown 图片语法
        for match in re.finditer(r'!\[.*?\]\((.*?)\)', content):
            url = match.group(1)
            if url not in result["images"]:
                result["images"].append(url)

    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    t = item.get("text", "")
                    text_parts.append(t)
                elif item_type == "image_url":
                    image_url = item.get("image_url", {})
                    url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url)
                    if url:
                        result["images"].append(url)
                elif item_type == "image":
                    image_data = item.get("data", "") or item.get("image_data", "")
                    if image_data:
                        result["images"].append(image_data)
                elif "text" in item:
                    text_parts.append(item["text"])
                elif "content" in item:
                    text_parts.append(str(item["content"]))
                else:
                    text_parts.append(str(item))
            else:
                text_parts.append(str(item))
        result["text"] = ''.join(text_parts)
    else:
        result["text"] = str(content) if content is not None else ""

    # 从文本中提取所有图片 URL（markdown、直链 CDN、data URI）
    if result["text"]:
        for match in re.finditer(r'!\[.*?\]\((.*?)\)', result["text"]):
            url = match.group(1)
            if url not in result["images"]:
                result["images"].append(url)
        for match in re.finditer(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', result["text"]):
            url = match.group(0)
            if url not in result["images"]:
                result["images"].append(url)
        # 裸 CDN 直链（generate_visualization 常只返回 URL）
        for url in extract_bare_image_urls(result["text"]):
            if url not in result["images"]:
                result["images"].append(url)

    # 正文已有 ![](url) 时不再填 images，避免工具卡片「Markdown 渲染 + 图片列表」同图两遍
    return drop_images_already_in_markdown_text(result)


def drop_images_already_in_markdown_text(result: dict) -> dict:
    """若 text 含 markdown 图片，从 images 去掉相同 URL（保留结构化独立图）。"""
    text = result.get("text") or ""
    images = list(result.get("images") or [])
    if not text or not images:
        return result
    md_urls = {
        m.group(1).strip()
        for m in re.finditer(r"!\[.*?\]\((.*?)\)", text)
        if m.group(1)
    }
    if not md_urls:
        return result
    # 规范化：去 query 后再比一次，兼容同图不同参数
    md_keys = {u.split("?", 1)[0] for u in md_urls}
    kept = []
    for u in images:
        su = str(u or "").strip()
        if su in md_urls or su.split("?", 1)[0] in md_keys:
            continue
        kept.append(u)
    result["images"] = kept
    return result


# 学术/通用图片托管直链白名单（含开源图床与学术资源站）。
# 历史版本是采购项目的 Alipay CDN host 列表，已替换为通用学术图片源。
_IMAGE_CDN_HOSTS = (
    "img.shields.io",
    "raw.githubusercontent.com",
    "user-images.githubusercontent.com",
    "objects.githubusercontent.com",
    "avatars.githubusercontent.com",
    "upload.wikimedia.org",
    "upload-os-bbs.hoyolab.com",
    "ars.els-cdn.com",
    "media.springernature.com",
    "ieeexplore.ieee.org",
    "cdn.pixabay.com",
    "images.unsplash.com",
)


def extract_bare_image_urls(text: str) -> list[str]:
    """从正文抽出图片托管直链（可无 .png 后缀）。"""
    if not text:
        return []
    urls: list[str] = []
    # 整行/整段就是 URL
    for m in re.finditer(
        r"(?:^|[\s\"'(])(https?://[^\s\"'<>\)]+)(?=$|[\s\"')])",
        text,
        flags=re.M,
    ):
        url = m.group(1).rstrip(".,;，。；")
        host_ok = any(h in url for h in _IMAGE_CDN_HOSTS)
        ext_ok = bool(re.search(r"\.(png|jpe?g|gif|webp|svg)(\?|$)", url, re.I))
        if host_ok or ext_ok:
            if url not in urls:
                urls.append(url)
    return urls


def strip_leaked_tool_meta(text: str) -> str:
    """去掉误展示给用户的工具/调试 JSON 尾巴。

    学术场景：清理 memory_update 的偏好 JSON 泄漏、工具返回的调试 JSON 等。
    注意：不要在这里做 Markdown 表格重整——流式每个 token 上重整会把
    未完成的多行报告拆毁。完整重整见 normalize_assistant_markdown()。
    """
    if not text:
        return text
    cleaned = text
    # 常见泄漏：尾部短 JSON（学术偏好 / 工具调试字段）
    cleaned = re.sub(
        r'\s*\{[^{}]*"(?:research_direction|cognitive_level|research_topics|papers_read|preferred_language|query|thread_id|tool_call_id)"[^{}]{0,400}\}\s*$',
        "",
        cleaned,
        flags=re.DOTALL,
    )
    # 正文中夹带的偏好 JSON 块（memory_update 泄漏）
    cleaned = re.sub(
        r'\s*\{\s*"research_direction"\s*:\s*"[^"]*"\s*(?:,\s*"[^"]+"\s*:\s*[^}]*)?\}\s*',
        "",
        cleaned,
    )
    return cleaned.rstrip()


def normalize_assistant_markdown(text: str) -> str:
    """流结束后对完整助手正文做一次 Markdown 重整（标题/表格/结语）。"""
    if not text:
        return text
    cleaned = strip_leaked_tool_meta(text)
    try:
        from api_view.markdown_tables import normalize_markdown

        cleaned = normalize_markdown(cleaned)
    except Exception:
        pass
    return cleaned


def finalize_display_assistant_messages(display_messages: list) -> list:
    """保存/下发前：强制工具 Markdown → 组装完整报告 → normalize → 补嵌孤儿图。

    根因级：凡工具返回 suggested_markdown，不以模型手抄为准；
    深度分析碎片化正文必须合成单一完整报告气泡。
    """
    from api_view.chart_embed import (
        collect_tool_chart_images,
        dedupe_markdown_images,
        embed_orphan_chart_images,
    )
    from api_view.report_assemble import assemble_deep_analysis_report
    from api_view.suggested_markdown_embed import apply_suggested_markdowns_to_display

    cleaned = [
        dm
        for dm in display_messages
        if not (dm.get("role") == "assistant" and not dm.get("content"))
    ]
    cleaned = apply_suggested_markdowns_to_display(cleaned)
    cleaned = assemble_deep_analysis_report(cleaned)

    for dm in cleaned:
        if dm.get("role") == "assistant" and isinstance(dm.get("content"), str):
            dm["content"] = normalize_assistant_markdown(dm["content"])
            dm["content"] = dedupe_markdown_images(dm["content"])

    charts = collect_tool_chart_images(cleaned)
    if not charts:
        return cleaned

    candidates = [
        dm
        for dm in cleaned
        if dm.get("role") == "assistant"
        and isinstance(dm.get("content"), str)
        and (
            len(dm["content"].strip()) >= 80
            or bool(re.search(r"^#{1,3}\s", dm["content"], re.M))
        )
    ]
    target = None
    for dm in reversed(candidates):
        c = dm["content"]
        if re.search(r"^#{1,3}\s", c, re.M) or "|" in c or "![" in c:
            target = dm
            break
    if target is None and candidates:
        target = candidates[-1]
    if target is not None:
        patched = embed_orphan_chart_images(target["content"], charts)
        patched = dedupe_markdown_images(patched)
        target["content"] = normalize_assistant_markdown(patched)
    return cleaned


def looks_like_analysis_report(text: str) -> bool:
    """判断文本是否为长篇科研报告（综述/透视/推演/审稿，用于去重展示）。"""
    if not text or len(text) < 200:
        return False
    markers = (
        "研究报告",
        "文献综述",
        "综述",
        "学者透视",
        "资产透视",
        "跨界推演",
        "审稿报告",
        "可行性",
        "## 一、",
        "## 摘要",
        "### 结论",
        "数据来源",
    )
    hits = sum(1 for m in markers if m in text)
    if "研究报告" in text and len(text) > 250:
        return True
    return hits >= 2 and len(text) > 400


def sanitize_tool_result_for_ui(tool_name: str, serialized: dict) -> dict:
    """
    委派子代理(task)的返回值往往是完整报告正文，
    而报告已通过子代理 token 流式展示 → 工具「结果」再渲染会造成头尾两份。

    注意：read_file 读到的 gold_sample / SKILL.md 也会像报告，
    **绝不能**标成「已生成分析报告」，否则用户以为报告已出、后面还在分析。

    emit_research_report：工具卡片只显示短回执，完整正文进 suggested_markdown
    供 finalize 写入唯一报告气泡。
    """
    name = (tool_name or "").strip().lower()
    text = serialized.get("text") or ""

    if "emit_research_report" in name:
        try:
            obj = json.loads(text) if isinstance(text, str) else None
        except (json.JSONDecodeError, TypeError):
            obj = None
        if isinstance(obj, dict) and obj.get("ok") and obj.get("suggested_markdown"):
            return {
                "text": str(obj.get("message") or "✅ 完整报告已生成，见下方正文。"),
                "images": serialized.get("images") or [],
                "suggested_markdown": obj["suggested_markdown"],
            }
        if isinstance(obj, dict) and obj.get("ok") is False:
            return {
                "text": f"❌ 报告发布失败：{obj.get('error') or '未知错误'}",
                "images": serialized.get("images") or [],
            }
        return serialized

    is_task = name == "task" or name.endswith("/task") or name.endswith(":task")
    if is_task and looks_like_analysis_report(text):
        return {
            "text": (
                "✅ 分析已完成。完整报告见下方对话，"
                "此处不再重复粘贴全文。"
            ),
            "images": serialized.get("images") or [],
        }
    # 其它工具：只有明确是「模型把整篇报告塞进工具返回」才截断；
    # 排除读技能/样例/图表参数等文件内容。
    if name in {
        "read_file",
        "write_file",
        "edit_file",
        "ls",
        "glob",
        "grep",
        "execute",
        "write_todos",
        "write_markdown_table",
        "generate_visualization",
        "emit_research_report",
    }:
        return serialized
    if looks_like_analysis_report(text) and len(text) > 2000:
        preview = text[:180].replace("\n", " ")
        return {
            "text": f"✅ 已生成分析报告（全文见下方对话）。预览：{preview}…",
            "images": serialized.get("images") or [],
        }
    return serialized


def create_sse_message(data: dict) -> str:
    """创建 SSE 格式的消息"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================================
# 中断恢复请求模型
# ============================================================

class ResumeRequest(BaseModel):
    """中断恢复请求体，resume 字段的格式取决于中断类型：
    - 数据补充中断: {"supplement": "用户自由文本输入"}
    - HITL 审批: {"decisions": [{"type": "approve"}]} 或 [{"type": "reject"}]
    """
    resume: dict
    workspace: str | None = None


# ============================================================
# 流式对话核心逻辑
# ============================================================

async def stream_chat_response(
    message: str = None,
    thread_id: str = None,
    resume_data: dict = None,
    user_id: str = None,
    username: str = None,
    workspace: str = None,
) -> AsyncIterator[str]:
    """
    流式生成对话响应，支持 Human-in-the-Loop 中断与恢复。

    两种调用模式：
    1. 初始对话 — 传入 message（用户消息）
    2. 中断恢复 — 传入 resume_data（Command.resume 的值）

    当 Agent 触发中断时（信息补充请求 / HITL 审批），
    流会发送 interrupt 事件后结束。前端收集用户决策后通过 /resume 端点恢复。

    同时累积完整的展示消息列表（包含子代理消息），在流结束后持久化。
    """
    from agent.settings import settings
    from agent.schema import ResearchContext

    uid = user_id or settings.default_user_id
    uname = username or settings.default_username
    # context_schema=ResearchContext；显式构造以确保字段齐全
    context = ResearchContext(
        user_id=uid,
        username=uname,
        thread_id=thread_id,
        workspace=workspace,
    )
    config = agent_loader.create_config(thread_id, user_id=uid)
    collected_content = ""
    # 工具调用栈，支持嵌套工具调用（主代理调 task → 子代理调 generate_chart）
    tool_call_stack = []
    # 子代理已流式输出长报告后，禁止主代理再整篇回显
    subagent_report_streamed = False
    skip_main_report_echo = False
    # emit_research_report：把 markdown 参数增量投影为 token
    emit_markdown_streamer: EmitMarkdownStreamer | None = None

    # ---- 根据模式构建 input 和 display_messages ----
    if resume_data is not None:
        # 恢复模式：加载已有展示消息，用 Command(resume=...) 恢复
        existing = await agent_loader.get_display_messages(thread_id) or []
        display_messages = existing
        current_input = Command(resume=resume_data)
    else:
        # 初始模式：新建展示消息，用普通消息作为 input
        current_input = {"messages": [{"role": "user", "content": message}]}
        display_messages = [
            {
                "id": f"user-{uuid.uuid4()}",
                "role": "user",
                "content": message
            }
        ]

    # 创建调试日志文件
    debug_log = get_debug_log_path(thread_id)

    def _last_display_is_assistant():
        return (display_messages and
                display_messages[-1]["role"] == "assistant")

    def _append_assistant_display(text: str, src: str) -> None:
        nonlocal collected_content
        if not text:
            return
        collected_content += text
        if _last_display_is_assistant():
            display_messages[-1]["content"] = strip_leaked_tool_meta(
                display_messages[-1]["content"] + text
            )
            display_messages[-1]["source"] = src
        else:
            display_messages.append(
                {
                    "id": f"assistant-{uuid.uuid4()}",
                    "role": "assistant",
                    "content": text,
                    "source": src,
                }
            )
    try:
        write_debug_log(debug_log, "STREAM_START", {
            "message": message,
            "thread_id": thread_id,
            "is_resume": resume_data is not None,
        })

        # 流式调用 agent.astream()
        # stream_mode=["messages", "values"] — messages 流显示 + values 流检测中断
        async for chunk in agent_loader.agent.astream(
            input=current_input,
            config=config,
            context=context,
            stream_mode=["messages", "values"],
            subgraphs=True, # 启用子代理流式输出
            version="v2",
        ):
            chunk_type = chunk.get("type")

            # ---- 值流（中断检测，必须在 messages 处理之前）----
            if chunk_type == "values" and chunk.get("interrupts"):
                interrupts = chunk["interrupts"]
                write_debug_log(debug_log, "INTERRUPT_DETECTED", {
                    "count": len(interrupts),
                })

                for interrupt in interrupts:
                    interrupt_value = interrupt.value

                    if "action_requests" in interrupt_value:
                        # ---- 第 2 层：HITL 审批中断（interrupt_on 配置）----
                        yield create_sse_message({
                            "type": "interrupt",
                            "interrupt_type": "hitl_approval",
                            "action_requests": interrupt_value["action_requests"],
                            "review_configs": interrupt_value.get("review_configs", []),
                            "thread_id": thread_id,
                        })
                        write_debug_log(debug_log, "INTERRUPT_HITL", {
                            "actions": [a["name"] for a in interrupt_value["action_requests"]],
                        })

                    elif interrupt_value.get("type") == "order_info_request":
                        # ---- 第 1 层：信息补充中断（通用：工具请求用户提供缺失字段）----
                        yield create_sse_message({
                            "type": "interrupt",
                            "interrupt_type": "info_supplement",
                            "missing_fields": interrupt_value["missing_fields"],
                            "collected_data": interrupt_value["collected_data"],
                            "thread_id": thread_id,
                        })
                        write_debug_log(debug_log, "INTERRUPT_SUPPLEMENT", {
                            "missing_fields": interrupt_value["missing_fields"],
                        })

                    else:
                        # 未知中断类型，透传原始值
                        yield create_sse_message({
                            "type": "interrupt",
                            "interrupt_type": "unknown",
                            "interrupt_value": str(interrupt_value)[:2000],
                            "thread_id": thread_id,
                        })

                # 兜底：将所有 calling 状态的工具标记为 done
                for dm in display_messages:
                    if dm["role"] == "tool" and dm["tool_status"] == "calling":
                        dm["tool_status"] = "done"

                # 清理空的 assistant 消息
                cleaned = [
                    dm for dm in display_messages
                    if not (dm["role"] == "assistant" and not dm.get("content"))
                ]
                cleaned = finalize_display_assistant_messages(cleaned)

                # 保存部分展示消息到 MongoDB（中断前的消息状态）
                # 注意：resume 模式下 display_messages 已含历史，保存时会覆盖旧记录
                await agent_loader.save_display_messages(thread_id, cleaned)
                write_debug_log(debug_log, "SAVE_DISPLAY_INTERRUPT", {
                    "thread_id": thread_id,
                    "message_count": len(cleaned),
                })

                # 发送 done 事件标记流结束（前端由此知道可以展示中断 UI）
                yield create_sse_message({
                    "type": "done",
                    "thread_id": thread_id,
                    "content": collected_content,
                    "interrupted": True,
                    "final_assistants": [
                        dm.get("content") or ""
                        for dm in cleaned
                        if dm.get("role") == "assistant"
                        and isinstance(dm.get("content"), str)
                    ],
                })
                return  # ← 结束本次流，等待前端 POST /resume

            # ---- 消息流（token / tool_call / tool_result）----
            if chunk_type != "messages":
                continue

            token, metadata = chunk["data"]
            namespace = chunk.get("ns", ())

            # 判断消息来源（raw 用于去重；source 对用户统一「助手」）
            is_subagent = any(
                isinstance(s, str) and s.startswith("tools:") for s in namespace
            )
            raw_source = extract_subagent_name(namespace) if is_subagent else "main"
            source = display_source_for_ui(raw_source)

            write_debug_log(debug_log, "RAW_CHUNK", {
                "ns": list(namespace),
                "raw_source": raw_source,
                "source": source,
                "is_subagent": is_subagent,
            }, raw_token=token)

            # 处理工具调用
            if hasattr(token, 'tool_call_chunks') and token.tool_call_chunks:
                for tool_chunk in token.tool_call_chunks:
                    # 工具开始调用
                    if tool_chunk.get('name'):
                        tool_id = str(uuid.uuid4())
                        tname = tool_chunk['name']
                        new_tool = {
                            "id": tool_id,
                            "name": tname,
                            "args": "",
                            "source": source
                        }
                        tool_call_stack.append(new_tool)
                        if is_emit_research_report_tool(tname):
                            emit_markdown_streamer = EmitMarkdownStreamer()

                        yield create_sse_message({
                            "type": "tool_start",
                            "tool_call_id": tool_id,
                            "tool_name": tname,
                            "source": source
                        })

                        # 添加到展示消息（emit 不存膨胀的 args JSON）
                        display_messages.append({
                            "id": tool_id,
                            "role": "tool",
                            "tool_name": tname,
                            "args": "",
                            "text": (
                                "正在生成完整报告…"
                                if is_emit_research_report_tool(tname)
                                else ""
                            ),
                            "images": [],
                            "source": source,
                            "tool_status": "calling",
                            "hide_args": is_emit_research_report_tool(tname),
                        })

                        write_debug_log(debug_log, "TOOL_START", {
                            "name": tname,
                            "source": source,
                            "stack_depth": len(tool_call_stack)
                        })

                    # 工具参数
                    if tool_chunk.get('args'):
                        args_str = tool_chunk['args']
                        current_tool_name = (
                            tool_call_stack[-1]["name"] if tool_call_stack else ""
                        )
                        is_emit = is_emit_research_report_tool(current_tool_name)
                        if tool_call_stack:
                            tool_call_stack[-1]["args"] += args_str

                        if is_emit:
                            # 不向 UI 推送膨胀 JSON；投影 markdown → token
                            if emit_markdown_streamer is None:
                                emit_markdown_streamer = EmitMarkdownStreamer()
                            md_delta = emit_markdown_streamer.feed(args_str)
                            if md_delta:
                                subagent_report_streamed = True
                                yield create_sse_message({
                                    "type": "token",
                                    "content": md_delta,
                                    "source": source,
                                })
                                _append_assistant_display(md_delta, source)
                                write_debug_log(debug_log, "EMIT_MARKDOWN_TOKEN", {
                                    "preview": md_delta[:200],
                                    "source": source,
                                })
                        else:
                            yield create_sse_message({
                                "type": "tool_args",
                                "args": args_str,
                                "source": source
                            })
                            for dm in reversed(display_messages):
                                if dm["role"] == "tool" and dm["tool_status"] == "calling":
                                    dm["args"] += args_str
                                    break

            # 处理工具执行结果
            if hasattr(token, 'type') and token.type == "tool":
                tool_name = getattr(token, 'name', '未知工具')
                result_content = getattr(token, 'content', '')

                # 序列化工具结果为结构化数据（委派结果去重，避免报告出现两份）
                serialized = sanitize_tool_result_for_ui(
                    tool_name, serialize_tool_result(result_content)
                )
                # 学术工具返回的结构化引用（供前端富卡片 + [n] 气泡渲染）
                refs = extract_references_from_tool_result(result_content)
                if refs:
                    serialized["references"] = refs

                # 从栈中弹出对应工具（栈顶即为当前完成的工具）
                finished_tool = tool_call_stack.pop() if tool_call_stack else None
                tool_id = finished_tool["id"] if finished_tool else ""
                if is_emit_research_report_tool(tool_name):
                    emit_markdown_streamer = None
                    subagent_report_streamed = True

                tool_result_payload = {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "tool_call_id": tool_id,
                    "text": serialized["text"],
                    "images": serialized["images"],
                    "source": source,
                }
                if refs:
                    tool_result_payload["references"] = refs
                yield create_sse_message(tool_result_payload)

                # 更新展示消息中对应工具的结果
                for idx, dm in enumerate(display_messages):
                    if dm["role"] == "tool" and dm["id"] == tool_id:
                        dm["text"] = serialized["text"]
                        dm["images"] = serialized["images"]
                        dm["tool_status"] = "done"
                        if refs:
                            dm["references"] = refs
                        if serialized.get("suggested_markdown"):
                            dm["suggested_markdown"] = serialized["suggested_markdown"]
                        # task 卡片创建得很早；完成后挪到末尾，避免历史里「先完成再分析」
                        is_task = (
                            tool_name == "task"
                            or str(tool_name).endswith("/task")
                            or str(tool_name).endswith(":task")
                        )
                        if is_task and idx < len(display_messages) - 1:
                            display_messages.append(display_messages.pop(idx))
                        break

                write_debug_log(debug_log, "TOOL_RESULT", {
                    "tool_name": tool_name,
                    "tool_id": tool_id,
                    "text_preview": serialized["text"][:300],
                    "images_count": len(serialized["images"]),
                    "source": source,
                    "stack_remaining": len(tool_call_stack)
                })

                # 发送 tool_end 事件，标记工具调用结束
                yield create_sse_message({
                    "type": "tool_end",
                    "tool_name": tool_name,
                    "tool_call_id": tool_id,
                    "source": source
                })

                # 确保展示消息中的工具标记为 done（兜底）
                for dm in reversed(display_messages):
                    if dm["role"] == "tool" and dm["id"] == tool_id and dm["tool_status"] == "calling":
                        dm["tool_status"] = "done"
                        break

            # 处理 AI 文本内容
            # 注意：ToolMessage（type == "tool"）的内容是工具执行结果，已在上面
            # tool_result 事件中处理。这里必须跳过，否则工具结果会被当作 AI 文本重复输出。
            content_text = extract_content_from_token(token)
            has_tool_calls = hasattr(token, 'tool_call_chunks') and token.tool_call_chunks
            is_tool_result = hasattr(token, 'type') and token.type == "tool"

            if content_text and not has_tool_calls and not is_tool_result:
                # 过滤系统上下文，避免泄漏到前端
                if "【系统上下文" in content_text:
                    continue

                content_text = strip_leaked_tool_meta(content_text)
                if not content_text:
                    continue

                # 标记：子代理已在流式输出分析报告（用 is_subagent，勿看 display source）
                if is_subagent and (
                    "研究报告" in content_text
                    or "分析报告" in content_text
                    or "综述报告" in content_text
                    or looks_like_analysis_report(
                        (display_messages[-1].get("content", "") if _last_display_is_assistant() else "")
                        + content_text
                    )
                ):
                    subagent_report_streamed = True

                # 主代理禁止再整篇粘贴报告（只允许短确认/下载询问）
                # 注意：子代理报告已以 source=main 落库，切勿把旧正文拼进 upcoming 误杀下载询问。
                if (not is_subagent) and subagent_report_streamed:
                    compact = content_text.strip()
                    is_download_ask = (
                        len(compact) <= 200
                        and ("下载" in compact or "保存" in compact)
                        and not looks_like_analysis_report(compact)
                    )
                    if skip_main_report_echo or (
                        looks_like_analysis_report(compact)
                        or (("研究报告" in compact or "分析报告" in compact) and len(compact) > 200)
                    ):
                        if is_download_ask:
                            skip_main_report_echo = False
                        else:
                            skip_main_report_echo = True
                            write_debug_log(debug_log, "SKIP_MAIN_REPORT_ECHO", {
                                "preview": content_text[:120]
                            })
                            continue
                    elif is_download_ask:
                        skip_main_report_echo = False

                # 子代理（如采购分析）正文也推前端，便于报告流式展示；
                # 主代理最终只需补充「是否下载」，勿再整篇粘贴（见 AGENTS.md）
                collected_content += content_text
                yield create_sse_message({
                    "type": "token",
                    "content": content_text,
                    "source": source
                })
                write_debug_log(debug_log, "TOKEN", {
                    "content": content_text[:200],
                    "source": source
                })

                # 更新展示消息：如果最后一条是 assistant 则追加，否则新建
                if _last_display_is_assistant():
                    display_messages[-1]["content"] = strip_leaked_tool_meta(
                        display_messages[-1]["content"] + content_text
                    )
                    display_messages[-1]["source"] = source
                else:
                    display_messages.append({
                        "id": f"assistant-{uuid.uuid4()}",
                        "role": "assistant",
                        "content": strip_leaked_tool_meta(content_text),
                        "source": source
                    })

        # ---- 流正常结束（无中断）----
        # 兜底：将所有 calling 状态的工具标记为 done
        for dm in display_messages:
            if dm["role"] == "tool" and dm["tool_status"] == "calling":
                dm["tool_status"] = "done"

        # 清理空的 assistant 消息 / 系统上下文泄漏
        display_messages = [
            dm for dm in display_messages
            if not (
                (dm["role"] == "assistant" and not dm.get("content"))
                or (
                    isinstance(dm.get("content"), str)
                    and (
                        "【系统上下文" in dm["content"]
                        or "勿向用户复述" in dm["content"]
                    )
                )
                or dm.get("role") == "system"
            )
        ]

        # 兜底：工具卡片中的长报告正文再清一次（防止历史/边界路径漏网）
        for dm in display_messages:
            if dm.get("role") == "tool" and looks_like_analysis_report(dm.get("text") or ""):
                name = (dm.get("tool_name") or "").lower()
                if name == "task" or "task" in name:
                    dm["text"] = (
                        "✅ 分析已完成。完整报告见下方对话，"
                        "此处不再重复粘贴全文。"
                    )

        # 流结束后：Markdown 重整 + 通用补嵌本轮工具孤儿图
        display_messages = finalize_display_assistant_messages(display_messages)

        # 保存完整展示消息到 MongoDB / 本地（包含子代理消息）
        # 多轮对话：追加到已有消息，而非覆盖（每轮调用 save 时 display_messages 仅含当前轮）
        if resume_data is None:
            # 初始对话：追加到已有历史
            existing = await agent_loader.get_display_messages(thread_id) or []
            all_messages = existing + display_messages
        else:
            # resume 模式：display_messages 已包含历史（load 时获取），直接保存
            all_messages = display_messages
        await agent_loader.save_display_messages(thread_id, all_messages)
        write_debug_log(debug_log, "SAVE_DISPLAY", {
            "thread_id": thread_id,
            "total_count": len(all_messages)
        })

        # 流结束，发送 done 事件（附带终审后的助手正文，供前端覆盖流式脏稿）
        write_debug_log(debug_log, "STREAM_DONE", {
            "thread_id": thread_id,
            "total_content_len": len(collected_content)
        })

        final_assistants = [
            dm.get("content") or ""
            for dm in display_messages
            if dm.get("role") == "assistant" and isinstance(dm.get("content"), str)
        ]
        yield create_sse_message({
            "type": "done",
            "thread_id": thread_id,
            "content": collected_content,
            "final_assistants": final_assistants,
        })

    except Exception as e:
        write_debug_log(debug_log, "STREAM_ERROR", {"error": str(e)})
        yield create_sse_message({
            "type": "error",
            "message": str(e)
        })


# ============================================================
# API 端点
# ============================================================

@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user: UserInfo = Depends(get_current_user),
):
    """
    流式对话接口

    接收用户消息，返回 SSE 流式响应
    支持实时显示 AI 生成的内容和工具调用信息
    检测到 Human-in-the-Loop 中断时会发送 interrupt 事件
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    if request.thread_id and not agent_loader.assert_session_owner(thread_id, user.user_id):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    if agent_loader._agent is None or not runtime_status.ready:
        detail = "；".join(runtime_status.warnings) if runtime_status.warnings else "Agent 仍在初始化或启动失败"
        raise HTTPException(
            status_code=503,
            detail=f"智能助手尚未就绪：{detail}",
        )
    agent_loader.bind_session_owner(thread_id, user.user_id, workspace=request.workspace)
    write_audit(
        "chat.stream",
        user_id=user.user_id,
        detail={"thread_id": thread_id, "message_len": len(request.message or "")},
    )

    return StreamingResponse(
        stream_chat_response(
            message=request.message,
            thread_id=thread_id,
            user_id=user.user_id,
            username=user.username,
            workspace=request.workspace,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/chat/{thread_id}/resume")
async def chat_resume(
    thread_id: str,
    request: ResumeRequest,
    user: UserInfo = Depends(get_current_user),
):
    """
    中断恢复接口

    当中断发生后，前端收集用户决策/补充数据，通过此端点恢复 Agent 执行。
    request.resume 的格式取决于中断类型：
    - 数据补充: {"supplement": "用户输入的补充信息"}
    - HITL 审批: {"decisions": [{"type": "approve"}]} 或 [{"type": "reject"}]
    """
    if not agent_loader.assert_session_owner(thread_id, user.user_id):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    if agent_loader._agent is None or not runtime_status.ready:
        raise HTTPException(status_code=503, detail="智能助手尚未就绪，请稍后重试")

    resume = request.resume or {}
    # HITL 审批载荷校验，防止前端误传空/非法 decision
    if "decisions" in resume:
        decisions = resume.get("decisions")
        if not isinstance(decisions, list) or not decisions:
            raise HTTPException(status_code=400, detail="审批 decisions 不能为空")
        allowed = {"approve", "reject", "edit"}
        for d in decisions:
            if not isinstance(d, dict) or d.get("type") not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"非法审批决策，允许: {sorted(allowed)}",
                )
        write_audit(
            "chat.resume.hitl",
            user_id=user.user_id,
            detail={
                "thread_id": thread_id,
                "decisions": [d.get("type") for d in decisions],
            },
        )
    elif "supplement" in resume:
        if not str(resume.get("supplement") or "").strip():
            raise HTTPException(status_code=400, detail="补充信息不能为空")
        write_audit(
            "chat.resume.supplement",
            user_id=user.user_id,
            detail={"thread_id": thread_id, "supplement_len": len(str(resume["supplement"]))},
        )
    else:
        write_audit(
            "chat.resume",
            user_id=user.user_id,
            detail={"thread_id": thread_id, "resume_keys": list(resume.keys())},
        )

    return StreamingResponse(
        stream_chat_response(
            thread_id=thread_id,
            resume_data=resume,
            user_id=user.user_id,
            username=user.username,
            workspace=request.workspace,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/chat/{thread_id}")
async def get_chat_state(
    thread_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """获取会话状态（兼容 LangChain Message 对象与 dict）"""
    if not agent_loader.assert_session_owner(thread_id, user.user_id):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    try:
        # 优先展示流式过程写入的完整消息（含工具/子代理）
        serialized = await agent_loader.get_display_messages(thread_id)
        if not serialized:
            from api_view.api.history import serialize_messages_from_checkpoint

            raw = await agent_loader.get_current_messages(thread_id)
            serialized = serialize_messages_from_checkpoint(raw)

        message_list = []
        for item in serialized:
            message = Message(
                id=item.get("id") or f"msg-{len(message_list)}",
                role=item.get("role", "assistant"),
                content=item.get("content", "") or item.get("text", "") or "",
                created_at=item.get("created_at", datetime.now()),
                tool_calls=item.get("tool_calls"),
                tool_call_id=item.get("tool_call_id"),
                tool_name=item.get("tool_name"),
                text=item.get("text"),
            )
            message_list.append(message)

        return ChatResponse(
            thread_id=thread_id,
            messages=message_list
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/{thread_id}/history")
async def get_chat_history(
    thread_id: str,
    limit: int = Query(50, ge=1, le=100),
    user: UserInfo = Depends(get_current_user),
):
    """获取会话历史状态列表"""
    if not agent_loader.assert_session_owner(thread_id, user.user_id):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    try:
        states = await agent_loader.get_state_history(thread_id, limit)

        return {
            "thread_id": thread_id,
            "states": [
                {
                    "config": state.config,
                    "values": state.values,
                    "created_at": state.created_at,
                    "parent_config": state.parent_config
                }
                for state in states
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
