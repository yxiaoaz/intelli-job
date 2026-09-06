from datetime import datetime
import json
import logging

from bs4 import BeautifulSoup
from scrapy import Request
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule

from app.models.constants import JobSource, RecruitmentType, AcademicQualification
from job_crawler.base_spider import BaseJobSpider
from job_crawler.contracts import NormalizedJob
from job_crawler.utils import UNDERGRADUATE_EXPRESSIONS, MASTERS_EXPRESSIONS, DOCTOR_EXPRESSIONS

DEFAULT_VAL = "未知"


class CTGoodJobSpider(CrawlSpider, BaseJobSpider):
    name = "ctgoodjob-hk-spider"
    job_source = JobSource.CT_GOOD_JOBS_HK

    start_urls = [
        "https://jobs.ctgoodjobs.hk/jobs?job_type=501,504&channel=graduate" + f"&page={page}"
        for page in range(1, 301)
    ]

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
    }

    def parse_start_url(self, response: TextResponse):
        '''
        The navigation page includes a json script that lists links to all jobs on this page
        '''
        soup = BeautifulSoup(response.text, features="lxml")

        app_ld_json_script = soup.find("script", type="application/ld+json")

        if app_ld_json_script:
            page_elements = json.loads(app_ld_json_script.string)['itemListElement']

            for pe in page_elements:
                if pe['@type'] == 'ListItem':
                    yield Request(pe['url'], callback=self.parse_job_item_page)

    def parse_job_item_page(self, response: TextResponse):
        yield from self.emit_items(response)

    def normalize(self, raw) -> NormalizedJob:
        """单个岗位详情页 → NormalizedJob（同一岗位可产出多个招聘类型）。"""
        response: TextResponse = raw
        soup = BeautifulSoup(response.text, features="lxml")

        # parse info
        ### default values
        job_title: str = DEFAULT_VAL
        location: str = DEFAULT_VAL
        #recruitment_type = RecruitmentType.EXPERIENCED  # a job posting may belong to >1 recruitment typs on CT
        recruitment_type_enum_list = [RecruitmentType.EXPERIENCED, RecruitmentType.GRADUATE]
        min_academic_qualification = AcademicQualification.ALL
        salary: str = DEFAULT_VAL
        description: str = DEFAULT_VAL
        company_name: str = DEFAULT_VAL
        update_time = datetime.now()

        app_ld_json_script = soup.find("script", type="application/ld+json")
        if app_ld_json_script:
            content_dict = json.loads(app_ld_json_script.string)

            job_title = content_dict.get("title", DEFAULT_VAL)
            company_name = content_dict.get('hiringOrganization', {}).get("name", "")
            update_time = datetime.fromisoformat(content_dict["datePosted"]) # UTC time

            try:
                description = BeautifulSoup(content_dict['description'], 'html.parser').get_text(strip = True, separator = "\n")
            except:
                description = DEFAULT_VAL

            """
            something like
            'jobLocation': [{'@type': 'Place',
                    'address': {'@type': 'PostalAddress',
                        'streetAddress': 'Kwai Chung',
                        'addressLocality': 'Kwai Chung',
                        'addressRegion': 'Hong Kong',
                        'addressCountry': 'HK',
                        'postalCode': '999077'},
                    'geo': {'@type': 'GeoCoordinates',
                        'latitude': 22.3626,
                        'longitude': 114.1343}}],
            """
            try:
                location_dict = content_dict["jobLocation"][0]['address']
                location = location_dict.get("streetAddress", "") + " " + location_dict.get("addressCountry", "")
            except:
                location = 'Hong Kong 香港'

            try:

                # they don't put education requirements in to the script data
                # parse from description by best effort
                if any(undergraduate_term in description.lower().strip() for undergraduate_term in UNDERGRADUATE_EXPRESSIONS):
                    min_academic_qualification = AcademicQualification.UNDERGRADUATE
                if any(master_term in description.lower().strip() for master_term in MASTERS_EXPRESSIONS):
                    min_academic_qualification = AcademicQualification.MASTERS
                if any(doctor_term in description.lower().strip() for doctor_term in DOCTOR_EXPRESSIONS):
                    min_academic_qualification = AcademicQualification.DOCTOR

            except:
                min_academic_qualification = AcademicQualification.ALL

            recruitment_type_enum_list = []
            try:
                # Note that content_dict['employmentType'] is a list OR a string 'N/A' for this website.
                # Since a single JobItem class can only have a single employment type,
                # we generate a single instance for each valid employment type

                # first scan the job title, may include expressions like "internship", "fresh grads"
                if 'intern' in job_title.lower().strip():
                    recruitment_type_enum_list.append(RecruitmentType.INTERN)
                if any(graduate_term in job_title.lower().strip() for graduate_term in ['grads', 'grad']):
                    recruitment_type_enum_list.append(RecruitmentType.GRADUATE)

                # then check the script data
                if isinstance(recruitment_type_str_list:=content_dict['employmentType'], str):
                    recruitment_type_str_list = content_dict['employmentType']
                    for recruitment_type_str in recruitment_type_str_list:
                        if recruitment_type_str.lower().strip() == 'full_time':
                            recruitment_type_enum_list.append(RecruitmentType.EXPERIENCED)
                        elif recruitment_type_str.lower().strip() == 'intern':
                            recruitment_type_enum_list.append(RecruitmentType.INTERN)

            except:
                recruitment_type_enum_list = [RecruitmentType.EXPERIENCED, RecruitmentType.GRADUATE]

            try:
                salary_dict = content_dict['baseSalary']
                salary = salary_dict.get("currency", "(unknown currency)") + " " + salary_dict.get("value", {}).get("minValue", "0") + salary_dict.get("value", {}).get("maxValue", "N/A") + " " + salary_dict.get("value", {}).get("unitText", "")
            except:
                salary = DEFAULT_VAL

            # 同一岗位可归属多个招聘类型：每类型产出一条（DB 侧按指纹/URL 去重收敛）
            for recruitment_type in recruitment_type_enum_list:
                yield NormalizedJob(
                    source=JobSource.CT_GOOD_JOBS_HK,
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
        else:
            print(f'Cannot find script in {response.url}')
