from datetime import datetime
import json
import uuid
import logging
import re

from bs4 import BeautifulSoup
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from app.models.constant import JobSource, RecruitmentType, AcademicQualification
from job_crawler.items import JobItemScrapy

DEFAULT_VAL = "未知"


class ShixisengInternSpider(CrawlSpider):
    name = "shixiseng-intern-spider"

    start_urls = [
        "https://www.shixiseng.com/interns?type=intern&sortType=zj" + f"&page={page}"
        for page in range(1, 201)
    ]

    rules = (
        Rule(
            LinkExtractor(allow=(r"shixiseng\.com\/intern\/")), callback="parse"
        ),  # single job item page
    )

    def parse(self, response: TextResponse):

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
            description = job_detail_span.get_text(strip=True)

        # job locations
        address_span = soup.find("span", class_=r"com_position")
        if address_span:
            location = address_span.get_text(strip=True)

        # company name
        company_name_tag = soup.find("a", class_="com-name")
        if company_name_tag:
            company_name = company_name_tag.get_text(strip=True)

        # create JobItemScrapy object
        job_item_scrapy = JobItemScrapy(
            id=id,
            source=JobSource.SHIXISENG,
            url=url,
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
