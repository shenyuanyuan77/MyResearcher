"""
研途智探AI · 文件上传 API。

支持 PDF / Word 上传：
  - PDF：走 pdf_distill 抽全文，返回精读结构（创新点/方法/可引用句）
  - Word：抽文本（待 python-docx 扩展；当前返回原文本）
  - 图片：占位（OCR 待 Phase 2）

端点：POST /api/upload（multipart/form-data）
"""

from __future__ import annotations

import io
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from api_view.auth import UserInfo, get_current_user
from api_view.observability import write_audit

logger = logging.getLogger(__name__)
router = APIRouter()

# 限制：单文件 20MB；允许类型
_MAX_SIZE = 20 * 1024 * 1024
_ALLOWED_PDF = "application/pdf"
_ALLOWED_EXT = {".pdf", ".docx", ".doc", ".txt"}


class UploadDistillResponse(BaseModel):
    ok: bool
    filename: str
    file_type: str
    full_text_chars: int
    sections: dict[str, str] = {}
    quotable_sentences: list[str] = []
    abstract_hint: str = ""
    note: str = ""


async def _extract_pdf_text(data: bytes) -> Optional[str]:
    """从 PDF bytes 抽全文。"""
    try:
        import fitz  # pymupdf
    except ImportError:
        return None
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            if i >= 40:
                break
            pages.append(page.get_text("text"))
        doc.close()
        text = "\n\n".join(pages).strip()
        return text if len(text) >= 100 else None
    except Exception as e:
        logger.warning("上传 PDF 抽取失败：%s", e)
        return None


async def _extract_docx_text(data: bytes) -> Optional[str]:
    """从 docx 抽文本。"""
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        logger.warning("上传 docx 抽取失败：%s", e)
        return None


@router.post("/upload", response_model=UploadDistillResponse)
async def upload_file(
    file: UploadFile = File(...),
    user: UserInfo = Depends(get_current_user),
):
    """上传文件（PDF/Word）并返回结构化精读。

    - PDF：pymupdf 抽全文 → 分段 + 关键句
    - docx：python-docx 抽文本
    - 其他：返回错误
    限 20MB；权限：任何登录用户。
    """
    # 校验大小
    data = await file.read()
    if len(data) > _MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": f"文件超限（最大 {_MAX_SIZE // 1024 // 1024}MB）"},
        )
    filename = (file.filename or "upload").lower()
    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_TYPE", "message": f"不支持的文件类型 {ext}（允许 PDF/Word/TXT）"},
        )

    # 抽取文本
    full_text: Optional[str] = None
    file_type = "unknown"
    if ext == ".pdf" or file.content_type == _ALLOWED_PDF:
        full_text = await _extract_pdf_text(data)
        file_type = "pdf"
    elif ext in (".docx", ".doc"):
        full_text = await _extract_docx_text(data)
        file_type = "docx"
    elif ext == ".txt":
        full_text = data.decode("utf-8", errors="ignore")
        file_type = "txt"

    if not full_text:
        raise HTTPException(
            status_code=422,
            detail={"code": "EXTRACT_FAILED", "message": "无法从文件抽取文本（可能为扫描件 PDF，暂不支持 OCR）"},
        )

    # 结构化精读（复用 pdf_distill 的分段/关键句）
    from mcp_server.tools.pdf_distill import split_sections, extract_key_sentences
    full_text = full_text[:60000]  # 安全上限
    sections = {k: v[:2000] for k, v in split_sections(full_text).items() if v}
    quotable = extract_key_sentences(full_text)

    write_audit(
        "upload.file", user_id=user.user_id,
        detail={"filename": file.filename, "type": file_type, "chars": len(full_text)},
    )

    return UploadDistillResponse(
        ok=True,
        filename=file.filename or "upload",
        file_type=file_type,
        full_text_chars=len(full_text),
        sections=sections,
        quotable_sentences=quotable,
        abstract_hint=sections.get("abstract", "")[:500],
        note=f"已从{file_type}抽取 {len(full_text)} 字。可基于此精读/审稿。扫描件 PDF 需 OCR（Phase 2）。",
    )
