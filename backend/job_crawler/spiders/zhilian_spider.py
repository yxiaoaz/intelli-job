from datetime import datetime
import json
import logging

from bs4 import BeautifulSoup
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from app.models.constants import JobSource, RecruitmentType, AcademicQualification
from job_crawler.base_spider import BaseJobSpider
from job_crawler.contracts import NormalizedJob
from job_crawler.utils import ZHILIAN_JOB_TYPE_ITEMS_URL_MAP, parse_zhilian_initial_state

DEFAULT_VAL = "未知"

logger = logging.getLogger(__name__)


class ZhilianSpider(CrawlSpider, BaseJobSpider):
    name = "zhilian-spider"
    job_source = JobSource.ZHILIAN

    # `et` corresponds to different job types:
    #     - `et = 1`: all
    #     - `et = 2`: full time
    #     - `et = 3`: contract/part time
    #     - `et = 4`: intern
    #     - `et = 5`: graduate
    # Prioritize graduate jobs, then intern, then full time

    start_urls = (
        [base_url + "?et=5" for base_url in ZHILIAN_JOB_TYPE_ITEMS_URL_MAP.values()]
        + [base_url + "?et=4" for base_url in ZHILIAN_JOB_TYPE_ITEMS_URL_MAP.values()]
        + [base_url + "?et=2" for base_url in ZHILIAN_JOB_TYPE_ITEMS_URL_MAP.values()]
    )

    rules = (
        Rule(
            LinkExtractor(
                allow=(r"zhaopin\.com\/sou\/.*\/p([1-9])\/?/"),
                deny=(r"zhaopin\.com\/sou\/.*\/p\d{2,}\/?"),
            ),
            follow=True,
        ),  # pagination: only get new job postings from pages 1-9
        Rule(
            LinkExtractor(allow=(r"zhaopin\.com\/jobdetail\/")), callback="parse"
        ),  # single job item page
    )

    def parse(self, response: TextResponse):
        yield from self.emit_items(response)

    def normalize(self, raw) -> NormalizedJob:
        """单个岗位详情页 → NormalizedJob（解析失败时保留默认值，由 pipeline 丢弃）。"""
        response: TextResponse = raw
        soup = BeautifulSoup(response.text, features="lxml")

        # default values
        job_title: str = DEFAULT_VAL
        location: str = DEFAULT_VAL
        recruitment_type = RecruitmentType.EXPERIENCED
        min_academic_qualification = AcademicQualification.ALL
        salary: str = DEFAULT_VAL
        description: str = DEFAULT_VAL
        company_name: str = DEFAULT_VAL
        update_time = datetime.now()

        # Primary: try __INITIAL_STATE__ JSON extraction (works on new Zhilian pages)
        state_data = parse_zhilian_initial_state(response.text)
        state_success = state_data.get("job_title") is not None

        if state_success:
            job_title = state_data["job_title"]
            company_name = state_data["company_name"] or DEFAULT_VAL
            salary = state_data["salary"] or DEFAULT_VAL
            description = state_data["description"] or DEFAULT_VAL
            location = state_data["location"] or DEFAULT_VAL

            # education → AcademicQualification
            degree_str = state_data.get("degree")
            if degree_str:
                if "大专" in degree_str:
                    min_academic_qualification = AcademicQualification.ASSOCIATE
                elif "本科" in degree_str:
                    min_academic_qualification = AcademicQualification.UNDERGRADUATE
                elif "硕士" in degree_str:
                    min_academic_qualification = AcademicQualification.MASTERS
                elif "博士" in degree_str:
                    min_academic_qualification = AcademicQualification.DOCTOR

            # work_type → RecruitmentType
            work_type_str = state_data.get("work_type")
            if work_type_str:
                if "实习" in work_type_str:
                    recruitment_type = RecruitmentType.INTERN
                elif "校园" in work_type_str:
                    recruitment_type = RecruitmentType.GRADUATE
                else:
                    recruitment_type = RecruitmentType.EXPERIENCED

            # update_time
            if state_data.get("update_time"):
                try:
                    update_time = datetime.strptime(
                        state_data["update_time"], "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    pass

        # Fallback: old CSS selectors (website redesign has invalidated most of these,
        # kept as safety net in case old structure returns)
        if not state_success:
            summary_plane_title = soup.find_all(class_="summary-plane__title")
            summary_plane_info = soup.find_all(class_="summary-plane__info")
            summary_plane_salary = soup.find_all(class_="summary-plane__salary")
            description_plane = soup.find_all(class_="describtion__detail-content")

            if summary_plane_title:
                job_title = summary_plane_title[0].text

            if summary_plane_info:
                tag_keywords = list(summary_plane_info[0].stripped_strings)
                if tag_keywords:
                    location = tag_keywords[0]
                    tag_keywords = set(tag_keywords)
                    if "校园" in tag_keywords:
                        recruitment_type = RecruitmentType.GRADUATE
                    elif "实习" in tag_keywords:
                        recruitment_type = RecruitmentType.INTERN

                    if "大专" in tag_keywords:
                        min_academic_qualification = AcademicQualification.ASSOCIATE
                    elif "本科" in tag_keywords:
                        min_academic_qualification = AcademicQualification.UNDERGRADUATE
                    elif "硕士" in tag_keywords:
                        min_academic_qualification = AcademicQualification.MASTERS
                    elif "博士" in tag_keywords:
                        min_academic_qualification = AcademicQualification.DOCTOR

            salary = summary_plane_salary[0].text if summary_plane_salary else DEFAULT_VAL
            description = description_plane[0].text if description_plane else DEFAULT_VAL

            company_info = soup.find_all("a", class_="company__title")
            if company_info:
                company_name = company_info[0].text

            if app_ld_json_script := soup.find("script", type="application/ld+json"):
                try:
                    update_time = datetime.strptime(
                        json.loads(app_ld_json_script.string)["pubDate"],
                        "%Y-%m-%dT%H:%M:%S",
                    )
                except json.decoder.JSONDecodeError:
                    logging.error(
                        f"Failed to parse date from JSON-LD script in {response.url}",
                        exc_info=True,
                    )

        # 调试日志: 如果两种方法都失败, 记录 warning 便于排查
        if job_title == DEFAULT_VAL and company_name == DEFAULT_VAL:
            logger.warning(
                f"[{self.name}] Failed to parse item from {response.url} "
                f"(both __INITIAL_STATE__ and CSS fallback failed). "
                f"Response preview: {response.text[:200]}"
            )

        yield NormalizedJob(
            source=JobSource.ZHILIAN,
            source_url=response.url,
            job_title=job_title,
            location=location,
            recruitment_type=recruitment_type,
            min_academic_qualification=min_academic_qualification,
            salary=salary,
            update_time=update_time,
            description=description,
            company_name=company_name,
        )
