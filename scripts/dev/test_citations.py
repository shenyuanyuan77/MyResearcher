"""引用格式化器单测：GB/T 7714 / APA / IEEE golden 用例。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp_server.tools.unified import Paper
from mcp_server.tools.citations import (
    format_paper,
    papers_to_references,
    style_label,
)


def make_sample_paper() -> Paper:
    """构造一篇典型期刊文章（含全部引用字段）。"""
    return Paper(
        title="Highly accurate protein structure prediction with AlphaFold",
        authors=["John Jumper", "Richard Evans", "Alexander Pritzel", "Tim Green"],
        year=2021,
        venue="Nature",
        cited_by_count=20000,
        doi="10.1038/s41586-021-03819-2",
        doi_url="https://doi.org/10.1038/s41586-021-03819-2",
        abstract="",
        source="crossref",
        pub_type="article",
        publisher="Springer",
        volume="596",
        issue="7873",
        page="583-589",
        raw_authors=[
            {"family": "Jumper", "given": "John"},
            {"family": "Evans", "given": "Richard"},
            {"family": "Pritzel", "given": "Alexander"},
            {"family": "Green", "given": "Tim"},
        ],
    )


def test_gbt7714():
    p = make_sample_paper()
    out = format_paper(p, "gbt7714", idx=1)
    print("[GB/T 7714]")
    print(" ", out)
    assert "[1]" in out, "缺编号"
    assert "[J]" in out, "缺文献类型标识 [J]"
    assert "JUMPER" in out, "GB/T 7714 作者姓应大写"
    assert "Nature" in out
    assert "596(7873)" in out, "缺 卷(期)"
    assert "583-589" in out, "缺页码"
    assert "10.1038/s41586-021-03819-2" in out, "缺 DOI"
    print("  ✅ PASSED\n")


def test_apa():
    p = make_sample_paper()
    out = format_paper(p, "apa", idx=2)
    print("[APA]")
    print(" ", out)
    assert "[2]" in out
    assert "(2021)" in out, "APA 年份应在括号内"
    assert "&" in out, "APA 多作者应用 & 连接最后一位"
    assert "Jumper, J." in out, "APA 作者应 Family, Initials."
    assert "*Nature*" in out, "APA 期刊应斜体"
    assert "https://doi.org/10.1038/s41586-021-03819-2" in out, "APA 应带 doi_url"
    print("  ✅ PASSED\n")


def test_ieee():
    p = make_sample_paper()
    out = format_paper(p, "ieee", idx=3)
    print("[IEEE]")
    print(" ", out)
    assert "[3]" in out
    assert "J. Jumper" in out, "IEEE 作者应 Initials. Family"
    assert '"Highly accurate' in out, "IEEE 标题应双引号"
    assert "and" in out, "IEEE 多作者应用 and 连接"
    assert "vol. 596" in out, "IEEE 缺 vol."
    assert "no. 7873" in out, "IEEE 缺 no."
    assert "pp. 583-589" in out, "IEEE 缺 pp."
    print("  ✅ PASSED\n")


def test_references_list():
    p = make_sample_paper()
    p2 = Paper(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        year=2017,
        venue="NeurIPS",
        doi="10.48550/arxiv.1706.03762",
        doi_url="https://doi.org/10.48550/arxiv.1706.03762",
        pub_type="conference",
        raw_authors=[{"family": "Vaswani", "given": "Ashish"}],
    )
    out = papers_to_references([p, p2], "gbt7714")
    print("[References List]")
    print(out)
    assert out.startswith("## 参考文献")
    assert "[1]" in out and "[2]" in out
    assert "[C]" in out, "会议论文应有 [C] 标识"
    print("  ✅ PASSED\n")


def test_style_label():
    assert style_label("gbt7714") == "GB/T 7714-2015"
    assert style_label("apa") == "APA 第7版"
    assert style_label("ieee") == "IEEE"
    print("[style_label] ✅ PASSED\n")


if __name__ == "__main__":
    test_gbt7714()
    test_apa()
    test_ieee()
    test_references_list()
    test_style_label()
    print("=" * 50)
    print("ALL CITATION TESTS PASSED ✅✅✅")
