"""P3/P5 升级验证：引擎② 文献检索 → 校验 references 字段 + 参考文献 + 导出。"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def login():
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"username": "yanjiu", "password": "yanjiu123"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


def stream(message, token, timeout=120):
    req = urllib.request.Request(
        f"{BASE}/api/chat/stream",
        data=json.dumps({"message": message, "workspace": "assistant"}).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {token}",
        },
    )
    import socket

    refs = None
    full_text = ""
    thread_id = None
    tool_names = []
    r = urllib.request.urlopen(req, timeout=timeout)
    buf = b""
    while True:
        chunk = r.read(1024)
        if not chunk:
            break
        buf += chunk
        while b"\n\n" in buf:
            block, buf = buf.split(b"\n\n", 1)
            for line in block.split(b"\n"):
                if line.startswith(b"data:"):
                    try:
                        d = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    t = d.get("type")
                    if t == "token":
                        full_text += d.get("content", "")
                    elif t == "tool_start":
                        tool_names.append(d.get("tool_name"))
                    elif t == "tool_result" and d.get("references"):
                        refs = d["references"]
                    elif t == "done":
                        thread_id = d.get("thread_id")
                        full_text += d.get("content") or ""
    r.close()
    return {"text": full_text, "refs": refs, "tools": tool_names, "thread_id": thread_id}


def main():
    token = login()
    print("=== 引擎② 文献检索（验证 references + 参考文献）===")
    msg = "检索 retrieval augmented generation 的3篇高引文献，出表，正文用[n]角标，文末出参考文献（GB/T 7714）。"
    res = stream(msg, token)
    print("  tools:", res["tools"])
    print(f"  refs field: {'✅ 有' + str(len(res['refs'])) + '篇' if res['refs'] else '❌ 无'}")
    if res["refs"]:
        r0 = res["refs"][0]
        print(f"  ref[1] idx={r0.get('idx')} title={r0.get('title','')[:40]} doi={r0.get('doi','')}")
        print(f"  ref[1] citation_gbt7714: {r0.get('citation_gbt7714','')[:80]}")
    has_refs_section = "参考文献" in res["text"]
    has_doi = "doi.org" in res["text"].lower() or "DOI:" in res["text"]
    print(f"  正文含「参考文献」章节: {'✅' if has_refs_section else '⚠️'}")
    print(f"  正文含 DOI: {'✅' if has_doi else '⚠️'}")
    print(f"  thread_id: {res['thread_id']}")

    if not res["thread_id"]:
        print("  ⚠️ 无 thread_id，跳过导出测试")
        return

    print("\n=== 导出测试（DOCX）===")
    req = urllib.request.Request(
        f"{BASE}/api/report/export",
        data=json.dumps({"thread_id": res["thread_id"], "format": "docx"}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ct = resp.headers.get("content-type", "")
            cd = resp.headers.get("content-disposition", "")
            print(f"  docx 导出: {len(body)} bytes, type={ct}, disposition={cd}")
            assert "wordprocessingml" in ct or len(body) > 5000, "docx 内容异常"
            print("  ✅ DOCX 导出成功")
    except Exception as e:
        print(f"  ❌ 导出失败: {e}")

    print("\n=== 导出测试（PDF）===")
    req2 = urllib.request.Request(
        f"{BASE}/api/report/export",
        data=json.dumps({"thread_id": res["thread_id"], "format": "pdf"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req2, timeout=30) as resp:
            body = resp.read()
            print(f"  pdf 导出: {len(body)} bytes, type={resp.headers.get('content-type','')}")
            assert body[:4] == b"%PDF", "PDF 头部异常"
            print("  ✅ PDF 导出成功")
    except Exception as e:
        print(f"  ❌ PDF 导出失败: {e}")


if __name__ == "__main__":
    main()
