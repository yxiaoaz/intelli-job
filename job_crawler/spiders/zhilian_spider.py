from datetime import datetime
import json
import uuid
import logging

from bs4 import BeautifulSoup
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from app.models.constant import JobSource, RecruitmentType
from job_crawler.items import JobItemScrapy

DEFAULT_VAL = "未知"


class ZhilianSpider(CrawlSpider):
    name = "zhilian-spider"

    start_urls = [
        "https://www.zhaopin.com/jobs",
    ]

    rules = (
        Rule(LinkExtractor(allow=(r"zhaopin\.com\/sou\/")), follow=True),
        Rule(
            LinkExtractor(allow=(r"zhaopin\.com\/sou\/.*\/p([1-9]|10)\/?/")),
            follow=True,
        ),  # pagination: only get new job postings from pages 1-10
        Rule(
            LinkExtractor(allow=(r"zhaopin\.com\/jobdetail\/")), callback="parse"
        ),  # single job item page
    )

    def parse(self, response: TextResponse):

        logger = logging.getLogger("scrapy")
        original_level = logger.level
        logger.setLevel(logging.CRITICAL)  # Or logging.ERROR, logging.FATAL

        try:
            soup = BeautifulSoup(response.text, features="lxml")

            # extract the bs4 elements
            summary_plane_title = soup.find_all(
                class_="summary-plane__title"
            )  # includes the job title
            summary_plane_info = soup.find_all(
                class_="summary-plane__info"
            )  # includes the location, recruitment type
            description_plane = soup.find_all(class_="describtion__detail-content")

            # parse info
            ### default values
            url = response.url
            id = uuid.uuid3(uuid.NAMESPACE_URL, url)
            job_title: str = DEFAULT_VAL
            location: str = DEFAULT_VAL
            recruitment_type = RecruitmentType.EXPERIENCED
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
                location = tag_keywords[0]

                if "校园" in tag_keywords:
                    recruitment_type = RecruitmentType.GRADUATE
                elif "实习" in tag_keywords:
                    recruitment_type = RecruitmentType.INTERN

            description = (
                description_plane[0].text if description_plane else DEFAULT_VAL
            )

            company_info = soup.find_all("a", class_="company__title")
            company_name = company_info[0].text

            if app_ld_json_script := soup.find("script", type="application/ld+json"):
                update_time = datetime.strptime(
                    json.loads(app_ld_json_script.string)["pubDate"],
                    "%Y-%m-%dT%H:%M:%S",
                )

            # create JobItemScrapy object
            job_item_scrapy = JobItemScrapy(
                id=id,
                source=JobSource.ZHILIAN,
                url=url,
                job_title=job_title,
                location=location,
                recruitment_type=recruitment_type,
                update_time=update_time,
                description=description,
                company_name=company_name,
            )

            yield job_item_scrapy

        finally:
            logger.setLevel(original_level)
