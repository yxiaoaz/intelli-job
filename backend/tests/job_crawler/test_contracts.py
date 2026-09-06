"""job_crawler.contracts 单元测试。

覆盖（spec tasks 1.1）：
- norm 的 NFKC / 标点 / 空白 / casefold 用例
- 中英文公司名指纹一致性
- 指纹：同公司同岗同地不同 URL → 相同；任一字段不同 → 不同
"""
import pytest

from job_crawler.contracts import FetchState, NormalizedJob, compute_fingerprint, norm


# ── norm：NFKC ─────────────────────────────────────────────────────────────

class TestNormNfkc:
    def test_fullwidth_to_ascii(self):
        """全角字母/数字经 NFKC 折叠为半角。"""
        assert norm("Ｓｔｒｉｐｅ ２０２６") == norm("stripe 2026")

    def test_fullwidth_punct_collapses(self):
        """全角括号/冒号与半角等价。"""
        assert norm("（上海）") == norm("(上海)")
        assert norm("字节跳动：深圳") == norm("字节跳动:深圳")


# ── norm：标点与空白 ───────────────────────────────────────────────────────

class TestNormPunctWhitespace:
    @pytest.mark.parametrize("raw,expected", [
        ("Stripe, Inc.", "stripeinc"),
        ("Byte  Dance\t Ltd.", "bytedanceltd"),
        ("阿里-巴巴（中国）", "阿里巴巴中国"),
        ("A · B / C", "abc"),
    ])
    def test_punct_and_whitespace_removed(self, raw, expected):
        assert norm(raw) == expected

    def test_none_and_empty(self):
        assert norm(None) == ""
        assert norm("") == ""


# ── norm：casefold ─────────────────────────────────────────────────────────

class TestNormCasefold:
    def test_case_insensitive(self):
        assert norm("STRIPe") == norm("stripe")
        assert norm("McDonald's") == norm("mcdonalds")


# ── 指纹 ───────────────────────────────────────────────────────────────────

class TestComputeFingerprint:
    def test_same_job_different_url_same_fingerprint(self):
        """同公司同岗同地、URL 不同 → 指纹相同（跨源去重的核心）。"""
        fp1 = compute_fingerprint("Stripe, Inc.", "Software Engineer",
                                  "San Francisco")
        fp2 = compute_fingerprint("stripe inc", "software   engineer!",
                                  "san-francisco")
        assert fp1 == fp2

    def test_chinese_english_consistency(self):
        """中英文公司名在标点/空白/全半角差异下指纹一致。"""
        fp1 = compute_fingerprint("字节跳动（ByteDance）", "后端开发工程师", "北京")
        fp2 = compute_fingerprint("字节跳动 ByteDance", "后端开发工程师", "北京")
        assert fp1 == fp2

    def test_different_company_differs(self):
        assert compute_fingerprint("A", "T", "L") != compute_fingerprint("B", "T", "L")

    def test_different_title_differs(self):
        assert compute_fingerprint("A", "T1", "L") != compute_fingerprint("A", "T2", "L")

    def test_different_location_differs(self):
        assert compute_fingerprint("A", "T", "L1") != compute_fingerprint("A", "T", "L2")

    def test_sha1_hex_64chars(self):
        fp = compute_fingerprint("x", "y", "z")
        assert len(fp) == 40
        int(fp, 16)  # hex 可解析

    def test_empty_inputs_stable(self):
        assert compute_fingerprint(None, "", None) == compute_fingerprint("", " ", "")


# ── FetchState / NormalizedJob 基本契约 ────────────────────────────────────

class TestContractsBasics:
    def test_fetch_state_values(self):
        assert {s.value for s in FetchState} == {"ok", "no_board", "empty",
                                                 "fetch_failed"}

    def test_normalized_job_defaults(self):
        from app.models.constants import JobSource
        job = NormalizedJob(source=JobSource.ZHILIAN,
                            source_url="https://example.com/j/1")
        assert job.salary_min is None
        assert job.published_at is None
        assert job.recruitment_type.value.startswith("社招")
        assert job.min_academic_qualification.value == "不限"
