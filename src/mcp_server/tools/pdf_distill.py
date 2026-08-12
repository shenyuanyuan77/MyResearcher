"""
PDF 全文精读：从 OA PDF 链接下载 → 抽取全文 → 分段 → 结构化精读。

依赖：pymupdf（fitz，已在环境）。无 PDF 链接时回退到摘要精读。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MAX_PAGES = 40  # 最多解析 40 页（避免超大文档 OOM）
_MAX_CHARS = 60_000  # 全文上限（送 LLM 的安全边界）


async def fetch_pdf_text(oa_url: str) -> Optional[str]:
    """下载 OA PDF 并抽取全文文本。失败返回 None。"""
    if not oa_url:
        return None
    try:
        import httpx
        import fitz  # pymupdf
    except ImportError:
        logger.warning("pymupdf(fitz) 或 httpx 未安装，PDF 全文精读不可用")
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(oa_url, headers={"User-Agent": "YanJiuZhiTan/1.0"})
            if resp.status_code != 200:
                return None
            pdf_bytes = resp.content
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            if i >= _MAX_PAGES:
                break
            pages.append(page.get_text("text"))
        doc.close()
        text = "\n\n".join(pages).strip()
        if len(text) < 100:
            return None  # 可能是扫描件，无文本
        return text[:_MAX_CHARS]
    except Exception as e:
        logger.warning("PDF 全文抽取失败：%s", e)
        return None


def split_sections(full_text: str) -> dict[str, str]:
    """粗分段：按常见学术论文章节标题切分。

    返回 {section_name: content}，不命中的归入 'body'。
    """
    if not full_text:
        return {}
    import re
    sections = {
        "abstract": "",
        "introduction": "",
        "method": "",
        "methods": "",
        "experiment": "",
        "results": "",
        "conclusion": "",
        "body": "",
    }
    # 匹配章节标题（1. Abstract / II. Introduction / ## Method 等）
    header_re = re.compile(
        r"^\s*(?:#{1,3}\s*)?(?:\d+\.?\s*|I+V?\.?\s*|)"
        r"(Abstract|Introduction|Background|Related\s+Work|Method(?:s)?|"
        r"Approach|Experiment(?:s)?|Evaluation|Results?|Discussion|"
        r"Conclusion(?:s)?|References?)\s*:?\s*$",
        re.I | re.M,
    )
    matches = list(header_re.finditer(full_text))
    if not matches:
        sections["body"] = full_text
        return sections
    for i, m in enumerate(matches):
        name = m.group(1).lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        content = full_text[start:end].strip()
        key = name if name in sections else "body"
        if sections[key]:
            sections[key] += "\n\n" + content
        else:
            sections[key] = content
    return sections


def extract_key_sentences(full_text: str, max_n: int = 8) -> list[str]:
    """提取可能可引用的关键句（启发式：含定量结果的句子）。

    优先提取含数字/百分比/F1/accuracy 的句子（实验结论句）。
    """
    if not full_text:
        return []
    import re
    sentences = re.split(r"(?<=[.!?])\s+", full_text)
    candidates = []
    for s in sentences:
        s = s.strip()
        if len(s) < 20 or len(s) > 300:
            continue
        # 含定量指标
        if re.search(r"\d+\.?\d*\s*%|accuracy|F1|precision|recall|BLEU|ROUGE|p\s*<\s*0\.\d+", s, re.I):
            candidates.append(s)
        if len(candidates) >= max_n:
            break
    return candidates


async def distill_with_full_text(
    oa_url: str, abstract: str, model=None
) -> dict[str, Any]:
    """用 PDF 全文做深度精读。

    返回结构化精读要点。model 为 None 时只返回分段/关键句（不调 LLM）。
    """
    full_text = await fetch_pdf_text(oa_url)
    if not full_text:
        return {"available": False, "reason": "无可用 OA 全文或 PDF 解析失败"}
    sections = split_sections(full_text)
    key_sentences = extract_key_sentences(full_text)

    result = {
        "available": True,
        "full_text_chars": len(full_text),
        "sections": {k: v[:2000] for k, v in sections.items() if v},  # 每段截断
        "quotable_sentences": key_sentences,
        "note": "全文来自 OA PDF（pymupdf 抽取）；quotable_sentences 为含定量结果的可引用句。",
    }

    # 可选：调 LLM 做创新点/方法/局限提炼（需传 model）
    if model is not None:
        try:
            prompt = _build_distill_prompt(sections, abstract)
            resp = await model.ainvoke(prompt)
            text = resp.content if hasattr(resp, "content") else str(resp)
            if isinstance(text, list):
                text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
            result["llm_distill"] = str(text)[:4000]
        except Exception as e:
            result["llm_distill_error"] = str(e)[:200]

    return result


def _build_distill_prompt(sections: dict[str, str], abstract: str) -> str:
    """构建全文精读 LLM prompt。"""
    method = sections.get("method") or sections.get("methods") or ""
    results = sections.get("results") or sections.get("experiment") or ""
    conclusion = sections.get("conclusion") or ""
    return f"""请基于以下论文全文片段，提炼结构化精读要点。严格基于原文，不编造。

【摘要】
{abstract[:800]}

【方法】
{method[:2000]}

【结果】
{results[:2000]}

【结论】
{conclusion[:1500]}

请输出（用 markdown）：
1. **研究问题**：一句话概括论文解决的核心问题。
2. **创新点**：列出 2-3 个主要创新（与现有工作的差异）。
3. **方法**：核心方法/模型/算法（不超过 150 字）。
4. **实验结论**：主要数据集/指标/结果。
5. **局限**：作者承认或可推断的局限。
6. **可引用句**：1-2 句原文可直接引用的关键结论。"""
