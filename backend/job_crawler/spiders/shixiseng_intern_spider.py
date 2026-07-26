from datetime import datetime
import json
import uuid
import logging
import re

from bs4 import BeautifulSoup
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from app.models.constants import JobSource, RecruitmentType, AcademicQualification
from job_crawler.items import JobItemScrapy
from job_crawler.utils import parse_nuxt_job_data

DEFAULT_VAL = "未知"

logger = logging.getLogger(__name__)


class ShixisengInternSpider(CrawlSpider):
    name = "shixiseng-intern-spider"

    start_urls = [
        "https://www.shixiseng.com/interns?type=intern&sortType=zj" + f"&page={page}"
        for page in range(1, 2001)
    ]
    
    rules = (
        Rule(
            LinkExtractor(
                allow=(r"shixiseng\.com\/intern\/"),
                deny=(r"wap\.shixiseng\.com"),
            ),
            callback="parse_item",
        ),  # single job item page (only www, skip wap)
    )

    def parse_item(self, response):
        soup = BeautifulSoup(response.text, features="lxml")

        # parse info
        ### default values
        url = response.url
        id = uuid.uuid3(uuid.NAMESPACE_URL, url)
        job_title: str = DEFAULT_VAL
        location: str = DEFAULT_VAL
        recruitment_type = RecruitmentType.INTERN
        min_academic_qualification = AcademicQualification.ALL
        salary: str = DEFAULT_VAL
        description: str = DEFAULT_VAL
        company_name: str = DEFAULT_VAL
        update_time = datetime.now()

        # job title
        job_title_span = soup.find("div", class_=r"new_job_name")
        if job_title_span:
            job_title = job_title_span.get_text(strip=True)

        # posting date
        time_span = soup.find("span", class_=r"cutom_font")
        if time_span:
            update_time = time_span.get_text(strip=True)  # e.g. '2025-08-08 18:06:26'
            update_time = datetime.strptime(
                re.sub(r"\s+", " ", update_time.strip()), "%Y-%m-%d %H:%M:%S"
            )

        # salary, job location, min academic qualifictaion
        job_msg = soup.find("div", class_="job_msg")
        if job_msg:

            salary_span = job_msg.find("span", class_=r"job_money")
            if salary_span:
                salary = salary_span.get_text(strip=True)

            location_span = job_msg.find("span", class_=r"job_position")
            if location_span:
                location = location_span.get_text(strip=True)

            academic_span = job_msg.find("span", class_=r"job_academic")
            if academic_span:
                min_academic_qualification_str = academic_span.get_text(strip=True)
                if "大专" in min_academic_qualification_str:
                    min_academic_qualification = AcademicQualification.ASSOCIATE
                elif "本科" in min_academic_qualification_str:
                    min_academic_qualification = AcademicQualification.UNDERGRADUATE
                elif "硕士" in min_academic_qualification_str:
                    min_academic_qualification = AcademicQualification.MASTERS
                elif "博士" in min_academic_qualification_str:
                    min_academic_qualification = AcademicQualification.DOCTOR

        # job details
        job_detail_span = soup.find("div", class_=r"job_detail")
        if job_detail_span:
            description = job_detail_span.get_text(strip=True, separator="\n")

        # job locations
        address_span = soup.find("span", class_=r"com_position")
        if address_span:
            location = address_span.get_text(strip=True)

        # company name
        company_name_tag = soup.find("a", class_="com-name")
        if company_name_tag:
            company_name = company_name_tag.get_text(strip=True)

        # Fallback: 如果 CSS 选择器被反爬拦截导致 job_title 和 company_name 都为默认值,
        # 尝试从 window.__NUXT__ 结构化数据中提取 (SSR 数据通常更稳定)
        if job_title == DEFAULT_VAL and company_name == DEFAULT_VAL:
            nuxt_data = parse_nuxt_job_data(response.text)
            if nuxt_data.get("job_title"):
                job_title = nuxt_data["job_title"]
            if nuxt_data.get("company_name"):
                company_name = nuxt_data["company_name"]
            if nuxt_data.get("salary") and salary == DEFAULT_VAL:
                salary = nuxt_data["salary"]
            if nuxt_data.get("description") and description == DEFAULT_VAL:
                description = nuxt_data["description"]
            if nuxt_data.get("address") and location == DEFAULT_VAL:
                location = nuxt_data["address"]
            if nuxt_data.get("update_time"):
                try:
                    update_time = datetime.strptime(
                        nuxt_data["update_time"], "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    pass
            if nuxt_data.get("degree"):
                degree_str = nuxt_data["degree"]
                if "大专" in degree_str:
                    min_academic_qualification = AcademicQualification.ASSOCIATE
                elif "本科" in degree_str:
                    min_academic_qualification = AcademicQualification.UNDERGRADUATE
                elif "硕士" in degree_str:
                    min_academic_qualification = AcademicQualification.MASTERS
                elif "博士" in degree_str:
                    min_academic_qualification = AcademicQualification.DOCTOR

        # 调试日志: 如果两种方法都失败, 记录 warning 便于排查
        if job_title == DEFAULT_VAL and company_name == DEFAULT_VAL:
            logger.warning(
                f"[{self.name}] Failed to parse item from {url} "
                f"(both CSS and NUXT fallback failed). "
                f"Response preview: {response.text[:200]}"
            )

        # create JobItemScrapy object
        job_item_scrapy = JobItemScrapy(
            id=id,
            source=JobSource.SHIXISENG,
            url=url,
            fingerprint=str(id),  # 使用 ID 作为指纹
            job_title=job_title,
            location=location,
            recruitment_type=recruitment_type,
            update_time=update_time,
            min_academic_qualification=min_academic_qualification,
            salary=salary,
            description=description,
            company_name=company_name,
        )

        yield job_item_scrapy

