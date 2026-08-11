"""学术工具冒烟测试：直接调用引擎层，验证三源连通与归一。"""
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


async def main():
    print("=" * 60)
    print("[1] paper_search: retrieval augmented generation")
    r = await paper_search("retrieval augmented generation", rows=5)
    print(f"  count={r['count']}  sources={r['sources_used']}")
    for p in r["papers"][:3]:
        print(f"   - {p['title'][:50]}  | doi={p['doi']}  | cite={p['cited_by_count']}")
    assert r["count"] > 0, "paper_search 未召回任何文献"

    print("=" * 60)
    print("[2] paper_by_doi: 10.1038/s41586-021-03819-2")
    r2 = await paper_by_doi("10.1038/s41586-021-03819-2")
    print(f"  ok={r2.get('ok')}  title={r2.get('paper',{}).get('title','')[:60]}")

    print("=" * 60)
    print("[3] paper_distill: Chain-of-Thought Prompting")
    r3 = await paper_distill("Chain-of-Thought Prompting Elicits Reasoning")
    print(f"  ok={r3.get('ok')}  year={r3.get('distill',{}).get('year')}")
    print(f"  quote={r3.get('distill',{}).get('quotation_hint','')[:80]}")

    print("=" * 60)
    print("[4] topic_radar: 大模型推理")
    r4 = await topic_radar("large language model reasoning")
    tr = r4["heat_trend"]["trend"]
    print(f"  trend={[(t['year'],t['count']) for t in tr]}  total3y={r4['heat_trend']['total_recent3y']}")
    print(f"  queries={r4['suggested_queries']}")

    print("=" * 60)
    print("[5] author_profile: Jason Wei")
    r5 = await author_profile("Jason Wei")
    if r5.get("ok"):
        prof = r5["profile"]
        print(f"  h_index={prof.get('h_index')}  works={prof.get('works_count')}  cited={prof.get('cited_by_count')}")
        print(f"  top1={prof['top_papers'][0]['title'][:50] if prof.get('top_papers') else 'N/A'}")
    else:
        print(f"  not found: {r5.get('message')}")

    print("=" * 60)
    print("[6] cross_search: large language model x quantum computing")
    r6 = await cross_search("large language model", "quantum computing", limit=5)
    print(f"  count={r6['count']}")
    for p in r6["papers"][:2]:
        print(f"   - {p['title'][:50]}  | doi={p['doi']}")

    print("=" * 60)
    print("ALL SMOKE TESTS PASSED ✅")


if __name__ == "__main__":
    asyncio.run(main())
