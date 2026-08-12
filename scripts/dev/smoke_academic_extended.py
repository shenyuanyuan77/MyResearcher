"""Wave 3-7 新增能力冒烟测试：过滤器/撤稿/cited_by/批量DOI/6格式/中文/文献库。

用法：PYTHONPATH=src python scripts/dev/smoke_academic_extended.py
（部分用例需要网络访问真实学术 API）
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


async def test_filters_and_retraction():
    """测试 paper_search 新过滤器 + 撤稿过滤。"""
    from mcp_server.tools.academic import paper_search
    print("[1] paper_search 带过滤器（year_from + sort + pub_type）")
    r = await paper_search("transformer", rows=3, year_from=2023, sort="newest", pub_type="article")
    print(f"  count={r['count']}  meta.sources_tried={r['meta']['sources_tried']}")
    print(f"  meta.filters={r['meta']['filters']}")
    assert r["count"] > 0, "带过滤器检索未召回"
    for p in r["papers"]:
        assert not p.get("is_retracted"), f"撤稿论文未被过滤: {p['title']}"
    print("  ✓ 撤稿论文已过滤")


async def test_doi_normalization():
    """测试 DOI 容错（各种前缀）。"""
    from mcp_server.tools.crossref_tools import _normalize_doi
    print("[2] DOI 容错")
    cases = [
        ("10.1038/xxx", "10.1038/xxx"),
        ("https://doi.org/10.1038/xxx", "10.1038/xxx"),
        ("http://dx.doi.org/10.1038/xxx", "10.1038/xxx"),
        ("doi: 10.1038/xxx", "10.1038/xxx"),
    ]
    for raw, expected in cases:
        got = _normalize_doi(raw)
        assert got == expected, f"DOI 容错失败: {raw} → {got} (期望 {expected})"
        print(f"  ✓ {raw} → {got}")


async def test_batch_doi():
    """测试批量 DOI 核验。"""
    from mcp_server.tools.academic import paper_by_dois
    print("[3] 批量 DOI 核验")
    r = await paper_by_dois(["10.1038/s41586-021-03819-2", "10.1145/3571730"])
    print(f"  requested={r['requested']} found={r['found']}")
    assert r["ok"]


async def test_cited_by():
    """测试施引文献（需真实 OpenAlex ID 解析）。"""
    from mcp_server.tools.academic import paper_cited_by
    print("[4] 施引文献")
    r = await paper_cited_by("10.1038/s41586-021-03819-2", rows=3)
    print(f"  ok={r.get('ok')} count={r.get('count')}")


async def test_citation_styles():
    """测试 6 种引用格式。"""
    from mcp_server.tools.citations import format_paper, supported_styles
    from mcp_server.tools.unified import Paper
    print("[5] 6 种引用格式")
    p = Paper(
        title="Test Paper", authors=["Zhang San"],
        raw_authors=[{"family": "Zhang", "given": "San"}],
        year=2024, venue="Nature", volume="1", issue="2", page="3-4",
        doi="10.1038/test", doi_url="https://doi.org/10.1038/test",
        pub_type="article",
    )
    styles = supported_styles()
    assert len(styles) == 6, f"应有 6 种格式，实际 {len(styles)}"
    for s in styles:
        out = format_paper(p, s, idx=1)
        assert "Test Paper" in out, f"{s} 格式无标题"
        print(f"  ✓ {s}: {out[:70]}...")


async def test_library_crud():
    """测试个人文献库 CRUD。"""
    print("[6] 个人文献库 CRUD")
    from api_view.api.library import (
        SavePaperRequest, UpdatePaperRequest, save_paper, list_library,
        update_paper, delete_paper,
    )

    class MockUser:
        user_id = "smoke_test_user"
        username = "smoke"

    u = MockUser()
    # 清理可能的残留
    try:
        await delete_paper("10.1038/smoketest", u)
    except Exception:
        pass

    # 收藏
    req = SavePaperRequest(
        doi="10.1038/smoketest", title="Smoke Test Paper",
        authors=["Tester"], year=2024,
    )
    r = await save_paper(req, u)
    assert r["ok"], "收藏失败"

    # 列表
    lst = await list_library(None, None, u)
    assert any(p["doi"] == "10.1038/smoketest" for p in lst["papers"]), "列表无收藏"

    # 更新状态
    upd = await update_paper("10.1038/smoketest", UpdatePaperRequest(status="read"), u)
    assert upd["status"] == "read", "状态更新失败"

    # 删除
    await delete_paper("10.1038/smoketest", u)
    lst2 = await list_library(None, None, u)
    assert not any(p["doi"] == "10.1038/smoketest" for p in lst2["papers"]), "删除失败"
    print("  ✓ 收藏→列表→更新状态→删除 全流程通过")


async def test_pdf_distill_helpers():
    """测试 PDF 分段/关键句（不下载真实 PDF）。"""
    from mcp_server.tools.pdf_distill import split_sections, extract_key_sentences
    print("[7] PDF 分段与关键句")
    text = "Abstract\nA novel method.\n\n1. Method\nWe achieve 95.3% accuracy.\n\n2. Results\nF1=0.92."
    secs = split_sections(text)
    assert secs.get("abstract"), "分段缺 abstract"
    assert secs.get("method"), "分段缺 method"
    sents = extract_key_sentences(text)
    assert any("95.3%" in s or "0.92" in s for s in sents), "关键句未提取"
    print(f"  ✓ sections={list(k for k,v in secs.items() if v)}")
    print(f"  ✓ key_sentences={len(sents)} 条")


async def test_cn_tokenizer():
    """测试中文分词。"""
    from mcp_server.tools.academic import _tokenize_topic
    print("[8] 中文分词（jieba）")
    toks = _tokenize_topic("联邦学习在医疗影像的应用")
    assert len(toks) >= 2, f"分词数过少: {toks}"
    print(f"  ✓ tokens={toks}")


async def main():
    tests = [
        ("过滤器+撤稿", test_filters_and_retraction),
        ("DOI 容错", test_doi_normalization),
        ("批量 DOI", test_batch_doi),
        ("施引文献", test_cited_by),
        ("6 种引用格式", test_citation_styles),
        ("个人文献库", test_library_crud),
        ("PDF 分段", test_pdf_distill_helpers),
        ("中文分词", test_cn_tokenizer),
    ]
    results = []
    for name, fn in tests:
        print("\n" + "=" * 60)
        try:
            await fn()
            results.append((name, "PASS"))
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            results.append((name, f"FAIL: {e}"))

    print("\n" + "=" * 60)
    print("汇总：")
    for name, status in results:
        mark = "✓" if status == "PASS" else "✗"
        print(f"  {mark} {name}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
