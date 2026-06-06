from datetime import datetime
import json
import uuid
import logging

from bs4 import BeautifulSoup
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from app.models.constants import JobSource, RecruitmentType, AcademicQualification
from job_crawler.items import JobItemScrapy
from job_crawler.utils import ZHILIAN_JOB_TYPE_ITEMS_URL_MAP

DEFAULT_VAL = "未知"


class ZhilianSpider(CrawlSpider):
    name = "zhilian-spider"

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

        soup = BeautifulSoup(response.text, features="lxml")

        # extract the bs4 elements
        summary_plane_title = soup.find_all(
            class_="summary-plane__title"
        )  # includes the job title
        summary_plane_info = soup.find_all(
            class_="summary-plane__info"
        )  # includes the location, recruitment type
        summary_plane_salary = soup.find_all(
            class_="summary-plane__salary"
        )  # includes the salary
        description_plane = soup.find_all(class_="describtion__detail-content")

        # parse info
        ### default values
        url = response.url
        id = uuid.uuid3(uuid.NAMESPACE_URL, url)
        job_title: str = DEFAULT_VAL
        location: str = DEFAULT_VAL
        recruitment_type = RecruitmentType.EXPERIENCED
        min_academic_qualification = AcademicQualification.ALL
        salary: str = DEFAULT_VAL
        description: str = DEFAULT_VAL
        company_name: str = DEFAULT_VAL
        update_time = datetime.now()

        ### extract info from bs4 elements
        if summary_plane_title:
            job_title = summary_plane_title[0].text

        if summary_plane_info:
            tag_keywords = list(
                summary_plane_info[0].stripped_strings
            )  # e.g. ['北京', '丰台区', '无经验', '硕士', '校园', '招1人']
            if tag_keywords:

                # the city is typically the first element
                location = tag_keywords[0]

                # the index of other elements are not fixed, so instead check for existence
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
                    f"Failed to parse date from JSON-LD script in {url}",
                    exc_info=True,
                )

        # create JobItemScrapy object
        job_item_scrapy = JobItemScrapy(
            id=id,
            source=JobSource.ZHILIAN,
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
