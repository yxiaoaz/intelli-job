# -*- coding: utf-8 -*-
"""NowcoderSpider 单元测试（nowcoder-spider tasks 3.3）。

fixtures 为探活真实响应切片（job_crawler/fixtures/nowcoder/）。
覆盖：
- 公司枚举：翻页续抓、枚举完成才发岗位请求（决策 6 无半轮数据）
- 枚举失败中止（HTTP 错误 / success:false → CloseSpider + FETCH_FAILED）
- 逐公司岗位：翻页、status 非 open 跳过、EMPTY 公司、success:false 仅跳过
- 单公司失败不触碰 fetch_state（决策 5 收口语义）
- 字段映射：薪资 ×1000、publishedAt 时区、description 剥标签、
  source_url 冻结拼法与确定性、recruitment_type 显式赋值
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import scrapy

from app.models.constants import JobSource, RecruitmentType
from job_crawler.contracts import FetchState
from job_crawler.spiders.nowcoder_spider import (
    JOB_LIST_URL, NowcoderSpider, recruitment_type_from_title)

FIXTURES = Path(__file__).resolve().parents[2] / "job_crawler" / "fixtures" / "nowcoder"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def split_outs(outs):
    """回调产出分流：_to_item 产出的是 JobItemScrapy（非 dict），请求为 scrapy.Request。"""
    items = [o for o in outs if not isinstance(o, scrapy.Request)]
    reqs = [o for o in outs if isinstance(o, scrapy.Request)]
    return items, reqs


class FakeResponse:
    def __init__(self, status: int = 200, text: str = "",
                 url: str = "https://gw-c.nowcoder.com/api/sparta/test"):
        self.status = status
        self.text = text
        self.url = url


class FakeFailure:
    """errback 兜底用替身（镜像 test_base_spider.FakeFailure）。"""

    def __init__(self, url="https://gw-c.nowcoder.com/api/sparta/x"):
        self.type = TimeoutError
        self.request = scrapy.Request(url)


@pytest.fixture()
def spider():
    return NowcoderSpider()


@pytest.fixture()
def company_resp():
    return FakeResponse(text=load_fixture("company_list_p1.json"),
                        url=f"https://gw-c.nowcoder.com/api/sparta/one-delivery-company/list?page=1")


@pytest.fixture()
def job_resp():
    return FakeResponse(text=load_fixture("job_list_kingsoft_p1.json"),
                        url=f"{JOB_LIST_URL}?companyId=1003&page=1&pageSize=10")


# ── 公司枚举 ─────────────────────────────────────────────────────────────────

class TestParseCompanies:
    def test_parses_records_and_requests_next_page(self, spider, company_resp):
        outs = list(spider.parse_companies(company_resp, page=1))
        # 未枚举完：只发下一页枚举请求，不发岗位请求（决策 6 无半轮数据）
        assert spider.fetch_state is FetchState.OK
        assert len(spider._companies) == 5
        assert all(cid and name for cid, name in spider._companies)
        assert len(outs) == 1
        req = outs[0]
        assert "page=2" in req.url and "one-delivery-company/list" in req.url
        assert req.cb_kwargs["page"] == 2
        assert req.errback == spider.on_enumeration_error

    def test_last_page_emits_job_requests(self, spider, company_resp):
        """totalPage=1 的场景：枚举完立即产出岗位请求。"""
        body = json.loads(load_fixture("company_list_p1.json"))
        body["data"]["totalPage"] = 1
        resp = FakeResponse(text=json.dumps(body, ensure_ascii=False))
        outs = list(spider.parse_companies(resp, page=1))
        assert len(spider._companies) == 5
        assert len(outs) == 5  # 每家一个 job-list 请求
        first = outs[0]
        assert "one-delivery-job/job-list" in first.url
        assert first.cb_kwargs["company_id"] == spider._companies[0][0]
        assert first.cb_kwargs["company_name"] == spider._companies[0][1]

    def test_company_limit_truncates(self):
        spider = NowcoderSpider(company_limit="3")
        requests_out = list(spider._request_job_list(
            [(i, f"c{i}") for i in range(10)]))
        assert len(requests_out) == 3

    @pytest.mark.parametrize("status", [403, 429, 500])
    def test_http_error_aborts_round(self, spider, status):
        with pytest.raises(scrapy.exceptions.CloseSpider):
            list(spider.parse_companies(
                FakeResponse(status=status, text="blocked"), page=1))
        assert spider.fetch_state is FetchState.FETCH_FAILED

    def test_success_false_aborts_round(self, spider):
        body = json.dumps({"success": False, "code": 1, "msg": "err",
                           "data": None}, ensure_ascii=False)
        with pytest.raises(scrapy.exceptions.CloseSpider):
            list(spider.parse_companies(FakeResponse(text=body), page=1))
        assert spider.fetch_state is FetchState.FETCH_FAILED

    def test_non_json_aborts_round(self, spider):
        with pytest.raises(scrapy.exceptions.CloseSpider):
            list(spider.parse_companies(
                FakeResponse(status=200, text="<html>waf</html>"), page=1))


# ── 逐公司岗位 ───────────────────────────────────────────────────────────────

class TestParseJobList:
    def test_parses_jobs_and_requests_next_page(self, spider, job_resp):
        items, reqs = split_outs(
            list(spider.parse_job_list(job_resp, 1003, "金山云", page=1)))
        # fixture：10 条记录、totalPage=3 → 10 item + 1 翻页请求
        assert len(items) == 10
        assert spider.fetch_state is FetchState.OK
        assert len(reqs) == 1
        assert "companyId=1003" in reqs[0].url and "page=2" in reqs[0].url

    def test_source_url_frozen_template_and_determinism(self, spider, job_resp):
        items, _ = split_outs(
            list(spider.parse_job_list(job_resp, 1003, "金山云", page=1)))
        raw0 = json.loads(job_resp.text)["data"]["records"][0]
        first = next(i for i in items if raw0["jobId"] in i["url"])
        # 决策 4b 冻结拼法：job-detail API，companyId+jobId
        assert first["url"] == (
            "https://gw-c.nowcoder.com/api/sparta/one-delivery-job"
            "/job-detail?companyId=1003&jobId=" + raw0["jobId"])
        # 确定性：同 raw 重爬 → 同 URL → 同 uuid3 主键（残留项的代码侧保证）
        job = spider.normalize(raw0, 1003, "金山云")
        item_again = spider._to_item(job)
        assert item_again["id"] == first["id"]
        assert first["id"] == uuid.uuid3(uuid.NAMESPACE_URL, first["url"])

    def test_salary_conversion_k_to_yuan(self, spider, job_resp):
        items, _ = split_outs(
            list(spider.parse_job_list(job_resp, 1003, "金山云", page=1)))
        raw = json.loads(job_resp.text)["data"]["records"][0]
        item = next(i for i in items if raw["jobId"] in i["url"])
        if raw.get("minSalary") is not None:
            assert item["salary_min"] == round(float(raw["minSalary"]) * 1000)
        if raw.get("maxSalary") is not None:
            assert item["salary_max"] == round(float(raw["maxSalary"]) * 1000)
        # salary 展示文本直存（决策 3）
        if raw.get("salary"):
            assert item["salary"] == raw["salary"]

    def test_published_at_tz_aware_utc(self, spider, job_resp):
        items, _ = split_outs(
            list(spider.parse_job_list(job_resp, 1003, "金山云", page=1)))
        raw = json.loads(job_resp.text)["data"]["records"][0]
        item = next(i for i in items if raw["jobId"] in i["url"])
        assert item["published_at"].tzinfo is timezone.utc

    def test_description_html_stripped(self, spider, job_resp):
        items, _ = split_outs(
            list(spider.parse_job_list(job_resp, 1003, "金山云", page=1)))
        raw = json.loads(job_resp.text)["data"]["records"][0]
        item = next(i for i in items if raw["jobId"] in i["url"])
        assert "<" not in item["description"][:100] or "&" in item["description"]
        assert item["description"].strip() != ""

    def test_status_non_open_skipped(self, spider, job_resp):
        """status 非 open 的记录不入库（决策 4）。"""
        body = json.loads(load_fixture("job_list_kingsoft_p1.json"))
        body["data"]["records"][0]["status"] = "closed"
        resp = FakeResponse(text=json.dumps(body, ensure_ascii=False),
                            url=job_resp.url)
        items, _ = split_outs(list(spider.parse_job_list(resp, 1003, "金山云", page=1)))
        assert len(items) == 9
        skipped_job_id = body["data"]["records"][0]["jobId"]
        assert all(skipped_job_id not in i["url"] for i in items)

    def test_empty_company_is_empty_state(self, spider):
        """200 + records 空 → EMPTY（不计 fail，决策 5）。"""
        body = {"success": True, "data": {"current": 1, "size": 10, "total": 0,
                                          "totalPage": 1, "records": []}}
        outs = list(spider.parse_job_list(FakeResponse(text=json.dumps(body)),
                                          999, "空公司", page=1))
        assert outs == []
        assert spider.fetch_state is FetchState.EMPTY

    def test_success_false_skips_without_state_change(self, spider):
        """success:false → 仅 warning 跳过，不触碰 fetch_state（决策 5）。"""
        spider.fetch_state = FetchState.OK  # 模拟此前已有公司成功
        body = {"success": False, "code": 1, "msg": "err", "data": None}
        outs = list(spider.parse_job_list(FakeResponse(text=json.dumps(body)),
                                          1004, "坏公司", page=1))
        assert outs == []
        assert spider.fetch_state is FetchState.OK

    def test_http_error_skips_without_state_change(self, spider):
        spider.fetch_state = FetchState.OK
        outs = list(spider.parse_job_list(
            FakeResponse(status=403, text="blocked"), 1005, "被拦公司", page=1))
        assert outs == []
        assert spider.fetch_state is FetchState.OK

    def test_non_json_skips_without_state_change(self, spider):
        spider.fetch_state = FetchState.OK
        outs = list(spider.parse_job_list(
            FakeResponse(status=200, text="<html>waf</html>"), 1006, "壳公司",
            page=1))
        assert outs == []
        assert spider.fetch_state is FetchState.OK

    def test_on_job_error_only_warns(self, spider):
        """errback 兜底：不降级 OK（决策 5 单公司失败不进健康度）。"""
        spider.fetch_state = FetchState.OK
        spider.on_job_error(FakeFailure())
        assert spider.fetch_state is FetchState.OK


# ── 字段映射辅助函数 ─────────────────────────────────────────────────────────

class TestRecruitmentType:
    @pytest.mark.parametrize("title,expected", [
        ("25届实习-后端开发", RecruitmentType.INTERN),
        ("Backend Intern", RecruitmentType.INTERN),
        ("暑期实习生计划", RecruitmentType.INTERN),
        ("25届校招-运维工程师", RecruitmentType.GRADUATE),
        ("算法研究员", RecruitmentType.GRADUATE),
        ("", RecruitmentType.GRADUATE),
        (None, RecruitmentType.GRADUATE),
    ])
    def test_title_inference(self, title, expected):
        assert recruitment_type_from_title(title) is expected

    def test_spider_uses_explicit_type_not_default(self, spider, job_resp):
        """contracts 默认 EXPERIENCED，牛客必须显式 GRADUATE/INTERN（决策 4）。"""
        raw = json.loads(job_resp.text)["data"]["records"][0]
        job = spider.normalize(raw, 1003, "金山云")
        assert job.recruitment_type is recruitment_type_from_title(raw["title"])
        assert job.recruitment_type is not RecruitmentType.EXPERIENCED


class TestSource:
    def test_enum_value_and_spider_binding(self):
        assert JobSource.NOWCODER.value == "Nowcoder | 牛客网"
        assert NowcoderSpider.job_source is JobSource.NOWCODER
        assert NowcoderSpider.name == "nowcoder-spider"
