"""
MyResearcher · 个人文献库 API。

跨会话知识沉淀：用户可收藏检索到的好论文，标记阅读状态，加笔记。
数据持久化到 data/library.sqlite。

端点：
  GET    /api/library              列出当前用户收藏（支持 status/tags 筛选）
  POST   /api/library              收藏一篇论文（去重 by doi）
  GET    /api/library/{doi}        取单篇收藏详情
  PATCH  /api/library/{doi}        更新状态/笔记/标签
  DELETE /api/library/{doi}        取消收藏
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api_view.auth import UserInfo, get_current_user, require_permission
from api_view.observability import write_audit

router = APIRouter()

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "library.sqlite"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_db_lock = threading.Lock()


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


_db = _get_db()


def _init_db() -> None:
    with _db_lock:
        _db.execute("""
            CREATE TABLE IF NOT EXISTS saved_papers (
                user_id TEXT NOT NULL,
                doi TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                authors TEXT NOT NULL DEFAULT '[]',
                year INTEGER,
                venue TEXT NOT NULL DEFAULT '',
                cited_by_count INTEGER,
                doi_url TEXT NOT NULL DEFAULT '',
                abstract TEXT NOT NULL DEFAULT '',
                pub_type TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'unread',
                tags TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                saved_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, doi)
            )
        """)
        _db.execute("CREATE INDEX IF NOT EXISTS idx_lib_user ON saved_papers(user_id)")
        _db.execute("CREATE INDEX IF NOT EXISTS idx_lib_status ON saved_papers(user_id, status)")
        _db.commit()


_init_db()


# ---- 模型 ----

class SavePaperRequest(BaseModel):
    doi: str = Field(..., description="论文 DOI")
    title: str = Field("", description="标题")
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: str = Field("")
    cited_by_count: Optional[int] = None
    doi_url: str = Field("")
    abstract: str = Field("")
    pub_type: str = Field("")
    tags: List[str] = Field(default_factory=list)
    notes: str = Field("")


class UpdatePaperRequest(BaseModel):
    status: Optional[str] = Field(None, description="unread / reading / read")
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


# ---- 辅助 ----

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["authors"] = json.loads(d.get("authors") or "[]")
    d["tags"] = json.loads(d.get("tags") or "[]")
    return d


def _normalize_doi(doi: str) -> str:
    import re
    d = (doi or "").strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    return d.lower()


# ---- 端点 ----

@router.get("/library")
async def list_library(
    status: Optional[str] = Query(None, description="按状态筛选：unread/reading/read"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    user: UserInfo = Depends(get_current_user),
):
    """列出当前用户的文献库（支持状态/标签筛选）。"""
    with _db_lock:
        sql = "SELECT * FROM saved_papers WHERE user_id = ?"
        params: list = [user.user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"
        rows = _db.execute(sql, params).fetchall()
    papers = [_row_to_dict(r) for r in rows]
    if tag:
        papers = [p for p in papers if tag in p.get("tags", [])]
    return {
        "count": len(papers),
        "papers": papers,
        "stats": {
            "total": len(papers),
            "unread": sum(1 for p in papers if p["status"] == "unread"),
            "reading": sum(1 for p in papers if p["status"] == "reading"),
            "read": sum(1 for p in papers if p["status"] == "read"),
        },
    }


@router.post("/library")
async def save_paper(
    body: SavePaperRequest,
    user: UserInfo = Depends(get_current_user),
):
    """收藏一篇论文（按 DOI 去重，已存在则更新元数据）。"""
    doi = _normalize_doi(body.doi)
    if not doi:
        raise HTTPException(status_code=400, detail={"code": "INVALID_DOI", "message": "DOI 不能为空"})
    now = datetime.utcnow().isoformat()
    with _db_lock:
        existing = _db.execute(
            "SELECT tags, notes, status FROM saved_papers WHERE user_id=? AND doi=?",
            (user.user_id, doi),
        ).fetchone()
        # 保留已有的 tags/notes/status（不覆盖用户标注）
        prev_tags = json.loads(existing["tags"]) if existing else []
        prev_notes = existing["notes"] if existing else ""
        prev_status = existing["status"] if existing else "unread"
        merged_tags = list(dict.fromkeys((body.tags or []) + prev_tags))[:20]
        _db.execute("""
            INSERT INTO saved_papers
                (user_id, doi, title, authors, year, venue, cited_by_count,
                 doi_url, abstract, pub_type, status, tags, notes, saved_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, doi) DO UPDATE SET
                title=excluded.title, authors=excluded.authors, year=excluded.year,
                venue=excluded.venue, cited_by_count=excluded.cited_by_count,
                doi_url=excluded.doi_url, abstract=excluded.abstract,
                pub_type=excluded.pub_type, tags=excluded.tags, updated_at=excluded.updated_at
        """, (
            user.user_id, doi, body.title,
            json.dumps(body.authors, ensure_ascii=False),
            body.year, body.venue, body.cited_by_count,
            body.doi_url or f"https://doi.org/{doi}",
            body.abstract, body.pub_type,
            prev_status, json.dumps(merged_tags, ensure_ascii=False),
            prev_notes, now, now,
        ))
        _db.commit()
    write_audit("library.save", user_id=user.user_id, tool="library",
                detail={"doi": doi, "title": body.title[:60]})
    return {"ok": True, "doi": doi, "message": "已收藏"}


@router.get("/library/{doi}")
async def get_paper(doi: str, user: UserInfo = Depends(get_current_user)):
    """取单篇收藏详情。"""
    d = _normalize_doi(doi)
    with _db_lock:
        row = _db.execute(
            "SELECT * FROM saved_papers WHERE user_id=? AND doi=?",
            (user.user_id, d),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "未收藏该论文"})
    return _row_to_dict(row)


@router.patch("/library/{doi}")
async def update_paper(
    doi: str,
    body: UpdatePaperRequest,
    user: UserInfo = Depends(get_current_user),
):
    """更新阅读状态/标签/笔记。"""
    d = _normalize_doi(doi)
    now = datetime.utcnow().isoformat()
    with _db_lock:
        row = _db.execute(
            "SELECT * FROM saved_papers WHERE user_id=? AND doi=?",
            (user.user_id, d),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "未收藏该论文"})
        new_status = body.status or row["status"]
        if new_status not in ("unread", "reading", "read"):
            raise HTTPException(status_code=400, detail={"code": "INVALID_STATUS", "message": "status 须为 unread/reading/read"})
        new_tags = json.dumps(body.tags, ensure_ascii=False) if body.tags is not None else row["tags"]
        new_notes = body.notes if body.notes is not None else row["notes"]
        _db.execute(
            "UPDATE saved_papers SET status=?, tags=?, notes=?, updated_at=? WHERE user_id=? AND doi=?",
            (new_status, new_tags, new_notes, now, user.user_id, d),
        )
        _db.commit()
    write_audit("library.update", user_id=user.user_id, detail={"doi": d, "status": new_status})
    return {"ok": True, "doi": d, "status": new_status}


@router.delete("/library/{doi}")
async def delete_paper(doi: str, user: UserInfo = Depends(get_current_user)):
    """取消收藏。"""
    d = _normalize_doi(doi)
    with _db_lock:
        cur = _db.execute(
            "DELETE FROM saved_papers WHERE user_id=? AND doi=?",
            (user.user_id, d),
        )
        _db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "未收藏该论文"})
    write_audit("library.delete", user_id=user.user_id, detail={"doi": d})
    return {"ok": True, "message": "已取消收藏"}
