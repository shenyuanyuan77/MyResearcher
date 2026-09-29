"""
MyResearcher · 本地会话存储（JSON 文件兜底，无 Mongo 时的唯一存储）。

存储会话归属/标题/工作区/更新时间/展示消息，进程重启可保留。
结构：
  data/local_sessions/
    meta.json         全局归属/标题/工作区/更新时间索引
    messages/<tid>.json  单会话展示消息
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "local_sessions"
_MSG_DIR = _DATA_DIR / "messages"
_META_PATH = _DATA_DIR / "meta.json"


def _ensure_dirs() -> None:
    _MSG_DIR.mkdir(parents=True, exist_ok=True)


def _load_meta() -> Dict[str, Any]:
    _ensure_dirs()
    if not _META_PATH.exists():
        return {"sessions": {}}
    try:
        return json.loads(_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": {}}


def _save_meta(meta: Dict[str, Any]) -> None:
    _ensure_dirs()
    tmp = _META_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, _META_PATH)


def _safe_tid(tid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in tid)[:128]


def _msg_path(tid: str) -> Path:
    return _MSG_DIR / f"{_safe_tid(tid)}.json"


# ---------- 归属 / 标题 / 工作区 / 更新时间 ----------

def bind_owner(tid: str, user_id: str) -> None:
    meta = _load_meta()
    sess = meta["sessions"].setdefault(tid, {})
    if "user_id" not in sess:
        sess["user_id"] = user_id
    sess.setdefault("created_at", datetime.now().isoformat())
    sess["updated_at"] = datetime.now().isoformat()
    _save_meta(meta)


def get_owner(tid: str) -> Optional[str]:
    return _load_meta()["sessions"].get(tid, {}).get("user_id")


def set_workspace(tid: str, workspace: Optional[str]) -> None:
    if not workspace:
        return
    meta = _load_meta()
    meta["sessions"].setdefault(tid, {})["workspace"] = workspace
    _save_meta(meta)


def get_workspace(tid: str) -> Optional[str]:
    return _load_meta()["sessions"].get(tid, {}).get("workspace")


def set_title(tid: str, title: str) -> None:
    meta = _load_meta()
    meta["sessions"].setdefault(tid, {})["title"] = title
    _save_meta(meta)


def get_title(tid: str) -> Optional[str]:
    return _load_meta()["sessions"].get(tid, {}).get("title")


def set_updated_at(tid: str, ts: Optional[datetime] = None) -> None:
    meta = _load_meta()
    meta["sessions"].setdefault(tid, {})["updated_at"] = (
        ts or datetime.now()
    ).isoformat()
    _save_meta(meta)


def get_updated_at(tid: str) -> datetime:
    raw = _load_meta()["sessions"].get(tid, {}).get("updated_at")
    if not raw:
        return datetime.now()
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return datetime.now()


def thread_ids_for_user(user_id: str) -> List[str]:
    meta = _load_meta()
    return [tid for tid, s in meta["sessions"].items() if s.get("user_id") == user_id]


def all_thread_ids() -> List[str]:
    return list(_load_meta()["sessions"].keys())


def thread_exists(tid: str) -> bool:
    return tid in _load_meta()["sessions"]


def delete_session(tid: str) -> bool:
    meta = _load_meta()
    removed = meta["sessions"].pop(tid, None) is not None
    if removed:
        _save_meta(meta)
    try:
        p = _msg_path(tid)
        if p.exists():
            p.unlink()
    except Exception:
        pass
    return removed


# ---------- 展示消息 ----------

def save_messages(tid: str, messages: List[Dict[str, Any]]) -> bool:
    _ensure_dirs()
    try:
        p = _msg_path(tid)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(messages, ensure_ascii=False, default=str), encoding="utf-8"
        )
        os.replace(tmp, p)
        return True
    except Exception as e:
        print(f"[local_session_store] save_messages 失败: {e}")
        return False


def load_messages(tid: str) -> Optional[List[Dict[str, Any]]]:
    p = _msg_path(tid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[local_session_store] load_messages 失败: {e}")
        return None
