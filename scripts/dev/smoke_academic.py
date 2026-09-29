"""学术工具冒烟测试：直接调用引擎层，验证三源连通、归一与**召回相关性**。

带已知答案断言（防回归）：历史版本只断言 count>0，返回无关高引垃圾也算 PASS，
导致 cited 排序摧毁相关性 / author_profile 全瘫 / 精读错配等缺陷长期漏网（2026-09-28）。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.tools.academic import (
    paper_search,
    paper_by_doi,
    paper_distill,
    topic_radar,
    author_profile,
    cross_search,
)


def _tokens(text):
    import re
    return {t.lower() for t in re.findall(r"[a-z]{3,}", (text or "").lower())}


async def main():
    print("=" * 60)
    print("[1] paper_search: retrieval augmented generation（相关性断言）")
    r = await paper_search("retrieval augmented generation", rows=5)
    print(f"  count={r['count']}  sources={r['sources_used']}")
    for p in r["papers"][:3]:
        print(f"   - {p['title'][:50]}  | doi={p['doi']}  | cite={p['cited_by_count']}")
    assert r["count"] > 0, "paper_search 未召回任何文献"
    q_tokens = _tokens("retrieval augmented generation")
    hits = sum(
        1 for p in r["papers"][:5]
        if len(q_tokens & _tokens(p.get("title"))) >= 2
    )
    assert hits >= 3, (
        f"paper_search 相关性守卫失败：top5 仅 {hits} 篇与查询词实质相关"
        f"（历史缺陷：cited 排序返回 DFT/BLAST 等无关高引论文）"
    )

    print("=" * 60)
    print("[2] paper_by_doi: 10.1038/s41586-021-03819-2")
    r2 = await paper_by_doi("10.1038/s41586-021-03819-2")
    print(f"  ok={r2.get('ok')}  title={r2.get('paper',{}).get('title','')[:60]}")
    assert r2.get("ok"), "paper_by_doi 未召回 AlphaFold"
    assert "protein structure prediction" in r2.get("paper", {}).get("title", "").lower(), \
        "paper_by_doi 返回的标题与 DOI 不匹配"

    print("=" * 60)
    print("[3] paper_distill: Chain-of-Thought Prompting（错配断言）")
    r3 = await paper_distill("Chain-of-Thought Prompting Elicits Reasoning in Large Language Models")
    if r3.get("ok"):
        d = r3.get("distill", {})
        title = d.get("title") or ""
        print(f"  ok=True  year={d.get('year')}  title={title[:60]}")
        assert "chain" in title.lower(), f"精读对象错配：{title[:60]}"
        assert (d.get("year") or 0) >= 2022, f"精读年份异常（历史缺陷：返回 1977 Sanger/lme4）：{d.get('year')}"
    else:
        # 相似度不足时允许诚实失败，但必须给候选而非错误论文
        cands = r3.get("candidates") or []
        print(f"  ok=False（诚实失败）  candidates={len(cands)}  msg={r3.get('message','')[:60]}")
        assert cands or "匹配" in r3.get("message", ""), "诚实失败时应返回候选列表"

    print("=" * 60)
    print("[4] topic_radar: large language model reasoning（代表作相关性断言）")
    r4 = await topic_radar("large language model reasoning")
    tr = r4["heat_trend"]["trend"]
    print(f"  trend={[(t['year'],t['count']) for t in tr]}  total3y={r4['heat_trend']['total_recent3y']}")
    print(f"  keywords={r4['suggested_keywords'][:5]}")
    for p in r4["top_cited_papers"][:3]:
        print(f"   - {p['title'][:50]}  | {p.get('year')}")
    q_tokens = _tokens("large language model reasoning")
    hits4 = sum(
        1 for p in r4["top_cited_papers"]
        if len(q_tokens & _tokens(p.get("title"))) >= 2
    )
    assert hits4 >= 3, (
        f"topic_radar 高引代表作相关性失败：{len(r4['top_cited_papers'])} 篇中仅 {hits4} 篇相关"
        f"（历史缺陷：返回 ImageNet 2009 / Akaike 1974 等噪声）"
    )

    print("=" * 60)
    print("[5] author_profile: Jason Wei（引擎③可用性断言）")
    r5 = await author_profile("Jason Wei")
    if r5.get("ok"):
        prof = r5["profile"]
        print(f"  h_index={prof.get('h_index')}  works={prof.get('works_count')}  cited={prof.get('cited_by_count')}")
        print(f"  top1={prof['top_papers'][0]['title'][:50] if prof.get('top_papers') else 'N/A'}")
        assert (prof.get("h_index") or 0) >= 5, f"h 指数异常：{prof.get('h_index')}"
        assert prof.get("top_papers"), "代表作列表为空"
        assert any(
            "chain-of-thought" in (p.get("title") or "").lower()
            or "reasoning" in (p.get("title") or "").lower()
            or "emergent" in (p.get("title") or "").lower()
            for p in prof["top_papers"][:8]
        ), "Jason Wei 代表作中未见其标志论文（可能消歧错误）"
    else:
        raise AssertionError(f"author_profile 引擎③不可用：{r5.get('message')}（历史缺陷：非法 select 字段 400）")

    print("=" * 60)
    print("[6] cross_search: large language model x quantum computing（相关性断言）")
    r6 = await cross_search("large language model", "quantum computing", limit=5)
    print(f"  count={r6['count']}  score={r6['feasibility']['score']}")
    for p in r6["papers"][:3]:
        print(f"   - {p['title'][:50]}  | doi={p['doi']}")
    q6 = _tokens("large language model quantum computing")
    for p in r6["papers"]:
        overlap = len(q6 & _tokens(p.get("title")))
        assert overlap >= 1, f"cross_search 返回与两域无关的文献：{p.get('title','')[:60]}"
    f6 = r6["feasibility"]
    if r6["count"] == 0:
        assert f6["score"] <= 5, "无交叉文献时可行性评分不应偏高"
        assert any("过滤" in x or "未检索到" in x or "无交叉" in x for x in f6["reasons"]), \
            "零交叉文献时应给出诚实说明"

    print("=" * 60)
    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
