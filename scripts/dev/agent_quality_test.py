"""全功能 Agent 输入输出测试 + 质量评估数据采集。

覆盖：五大引擎 + 3 子 Agent + 技能库 + 记忆 + 闲聊分流。
每例采集：事件流 / 工具调用 / 全文 / 时延 / DOI 提取，落盘 JSON 供质量评估。
用法：python scripts/dev/agent_quality_test.py [case_id ...]（不传则全量）
"""
import concurrent.futures as cf
import json
import re
import socket
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[2] / "data" / "quality_reports"
OUT.mkdir(parents=True, exist_ok=True)

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\)\"'<>，。；]+", re.I)

CASES = [
    # id, 名称, 输入, 预期工具(子串), 是否应有 DOI, 超时秒
    dict(id="E2-search", name="引擎②文献检索",
         msg="帮我检索 5 篇关于 retrieval augmented generation 的高被引论文，用表格列出标题/作者/年份/被引次数/DOI链接。",
         expect_tools=["paper_search"], expect_doi=True, timeout=300),
    dict(id="E2-doi", name="引擎②DOI溯源",
         msg="帮我查 DOI 为 10.1038/s41586-021-03819-2 的论文，给出标题、作者、期刊和摘要要点。",
         expect_tools=["paper_by_doi"], expect_doi=True, timeout=240),
    dict(id="E2-distill", name="引擎②论文精读",
         msg="帮我精读这篇论文：Chain-of-Thought Prompting Elicits Reasoning in Large Language Models，给出核心贡献、方法、局限。",
         expect_tools=["paper_distill"], expect_doi=True, timeout=300),
    dict(id="E1-radar", name="引擎①方向构建",
         msg="用雷达扫描 large language model agents 方向的研究热点与趋势，我想评估这个方向适不适合作为硕士研究课题。",
         expect_tools=["topic_radar"], expect_doi=True, timeout=300),
    dict(id="E3-author", name="引擎③学者透视",
         msg="帮我做学者 Jason Wei 的深度画像：h 指数、代表作 Top3（带 DOI）、研究主题分布。",
         expect_tools=["author_profile"], expect_doi=True, timeout=300),
    dict(id="E4-cross", name="引擎④跨界推演",
         msg="我想把 attention mechanism 跨界迁移到 protein structure prediction，检索一下两个领域已有的交叉工作（带 DOI），然后评估融合可行性。",
         expect_tools=["cross_search"], expect_doi=True, timeout=300),
    dict(id="SA-review", name="综述子Agent",
         msg="请输出一份关于 tool use in large language models 的小型文献综述（8 篇左右，表格 + 聚类分析 + 参考文献）。",
         expect_tools=["paper_search", "emit_research_report"], expect_doi=True, timeout=420),
    dict(id="SE-review", name="审稿子Agent+引用核验",
         msg="帮我审稿这段摘要，并核验其中的引用是否真实存在：\n\nAbstract: Large language models frequently hallucinate references [1]. Prior work [2] showed retrieval augmentation mitigates this. We propose FakeCite, a novel framework achieving 99% accuracy on all benchmarks.\n\nReferences:\n[1] Smith, J. et al. (2023). Hallucination in LLMs. DOI: 10.5555/fake-doi-12345\n[2] Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. DOI: 10.5555/3442188.3442407",
         expect_tools=["paper_by_doi"], expect_doi=True, timeout=420),
    dict(id="SP-polish", name="润色子Agent",
         msg="帮我润色这段英文摘要：We use a new method to make the model better. Our method is very good and the experiment results is very good too. We get 95% accuracy on the dataset, this prove our method is useful.",
         expect_tools=["write_markdown_table"], expect_doi=False, timeout=240),
    dict(id="SK-load", name="技能库加载",
         msg="我要写一篇论文的 Introduction，请给我一套完整的写作方法论，包括结构和常见错误。",
         expect_tools=["load_research_skill"], expect_doi=False, timeout=240),
    dict(id="MEM-context", name="记忆/研究上下文",
         msg="我的研究方向是大模型推理优化，请记住它，并推荐 2 篇和我方向相关的入门综述（带 DOI）。",
         expect_tools=["paper_search"], expect_doi=True, timeout=300),
    dict(id="CHAT-smalltalk", name="闲聊分流",
         msg="你好，简单介绍一下你能帮我做什么？",
         expect_tools=[], expect_doi=False, timeout=180),
]


def login():
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"username": "yanjiu", "password": "yanjiu123"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def stream(message, token, timeout):
    req = urllib.request.Request(
        f"{BASE}/api/chat/stream",
        data=json.dumps({"message": message, "workspace": "assistant"}).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream",
                 "Authorization": f"Bearer {token}"},
    )
    types, tool_names, tool_results = [], [], []
    full_text, errors = "", []
    try:
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
                    if not line.startswith(b"data:"):
                        continue
                    try:
                        d = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    t = d.get("type")
                    types.append(t)
                    if t == "token":
                        full_text += d.get("content", "")
                    elif t == "tool_start":
                        tool_names.append(d.get("tool_name"))
                    elif t == "tool_result":
                        tool_results.append(str(d.get("content", ""))[:500])
                    elif t == "error":
                        errors.append(d.get("message"))
                        return types, tool_names, tool_results, full_text, errors
                    elif t == "done":
                        # done.content 为后端全量权威文本（前端语义：替换而非追加）
                        full_text = d.get("content") or full_text
                        return types, tool_names, tool_results, full_text, errors
        r.close()
    except (socket.timeout, Exception) as e:
        errors.append(f"{type(e).__name__}: {e}")
    return types, tool_names, tool_results, full_text, errors


def run_case(case, token):
    t0 = time.time()
    types, tools, tool_results, text, errors = stream(case["msg"], token, case["timeout"])
    dt = time.time() - t0
    dois = sorted(set(m.rstrip(".,;").rstrip("/") for m in DOI_RE.findall(text)))
    from collections import Counter
    rec = dict(
        id=case["id"], name=case["name"], input=case["msg"],
        latency_s=round(dt, 1), events=dict(Counter(types)),
        tools_called=tools, tool_results_preview=tool_results[:4],
        output=text, errors=errors, dois_found=dois,
    )
    # 判定
    checks = {}
    tools_l = [str(t).lower() for t in tools]
    checks["no_error"] = not errors
    checks["expected_tools"] = all(
        any(e.lower() in t for t in tools_l) for e in case["expect_tools"]
    ) if case["expect_tools"] else len(tools_l) == 0
    checks["doi_anchored"] = bool(dois) == case["expect_doi"] and (dois or not case["expect_doi"])
    checks["substantial"] = len(text) > (200 if case["expect_doi"] else 50)
    rec["checks"] = checks
    rec["pass"] = all(checks.values())
    return rec


def main():
    only = set(sys.argv[1:])
    cases = [c for c in CASES if not only or c["id"] in only]
    token = login()
    results = []
    for case in cases:
        print("=" * 70)
        print(f"[{case['id']}] {case['name']}  ::  {case['msg'][:60].replace(chr(10), ' ')}...")
        rec = run_case(case, token)
        results.append(rec)
        flag = "✅ PASS" if rec["pass"] else "❌ FAIL"
        print(f"  {flag}  latency={rec['latency_s']}s  tools={rec['tools_called'][:6]}  "
              f"len={len(rec['output'])}  dois={len(rec['dois_found'])}  errors={rec['errors'][:1]}")
        if not rec["pass"]:
            print(f"  checks={rec['checks']}")
        out_path = OUT / f"case_{case['id']}.json"
        out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 70)
    npass = sum(r["pass"] for r in results)
    print(f"SUMMARY: {npass}/{len(results)} passed")
    (OUT / "run_summary.json").write_text(
        json.dumps([{k: r[k] for k in ("id", "name", "latency_s", "tools_called",
                                        "checks", "pass", "dois_found", "errors")}
                    for r in results], ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
