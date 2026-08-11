"""从 emit_research_report 的增量 tool_args JSON 中提取 markdown 正文。

模型边生成工具参数边推 SSE；本模块把 `"markdown": "..."` 字符串值
增量解码为可读 Markdown，供投影为 type=token 流式展示。
"""

from __future__ import annotations

import re
from typing import Optional

_MARKDOWN_KEY_RE = re.compile(r'"markdown"\s*:\s*"')


def is_emit_research_report_tool(name: str | None) -> bool:
    return "emit_research_report" in str(name or "").lower()


class EmitMarkdownStreamer:
    """有状态：feed(args_chunk) → 本帧新增的解码后 markdown 文本。"""

    def __init__(self) -> None:
        self._buf = ""
        self._pos = 0  # 尚未消费的 raw 字节位置（在 markdown 值内）
        self._value_start: Optional[int] = None
        self._escape = False
        self._unicode_buf = ""
        self._unicode_left = 0
        self._done = False

    @property
    def done(self) -> bool:
        return self._done

    def feed(self, chunk: str) -> str:
        if not chunk or self._done:
            return ""
        self._buf += chunk
        if self._value_start is None:
            m = _MARKDOWN_KEY_RE.search(self._buf)
            if not m:
                # 避免缓冲无限膨胀：只保留可能构成 key 的尾部
                if len(self._buf) > 64:
                    self._buf = self._buf[-64:]
                return ""
            self._value_start = m.end()
            self._pos = self._value_start

        out: list[str] = []
        i = self._pos
        buf = self._buf
        n = len(buf)

        while i < n:
            c = buf[i]
            if self._unicode_left > 0:
                self._unicode_buf += c
                self._unicode_left -= 1
                i += 1
                if self._unicode_left == 0:
                    try:
                        out.append(chr(int(self._unicode_buf, 16)))
                    except ValueError:
                        out.append("\\u" + self._unicode_buf)
                    self._unicode_buf = ""
                continue

            if self._escape:
                self._escape = False
                if c == "u":
                    self._unicode_left = 4
                    self._unicode_buf = ""
                    i += 1
                    continue
                esc = {
                    '"': '"',
                    "\\": "\\",
                    "/": "/",
                    "b": "\b",
                    "f": "\f",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                }.get(c)
                out.append(esc if esc is not None else c)
                i += 1
                continue

            if c == "\\":
                self._escape = True
                i += 1
                continue

            if c == '"':
                # 字符串结束（未转义的引号）
                self._done = True
                i += 1
                break

            out.append(c)
            i += 1

        self._pos = i
        # 已进入 markdown 值后可丢弃前缀，降低内存
        if self._value_start is not None and self._pos > 4096:
            keep_from = self._pos
            self._buf = self._buf[keep_from:]
            self._pos = 0
            self._value_start = 0
        return "".join(out)
