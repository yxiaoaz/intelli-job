from datetime import datetime
import json
import uuid
import logging

from bs4 import BeautifulSoup
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from app.models.constant import JobSource, RecruitmentType, AcademicQualification
from job_crawler.items import JobItemScrapy
from job_crawler.utils import ZHILIAN_JOB_TYPE_ITEMS_URL_MAP

DEFAULT_VAL = "未知"


class WelcomeToTheJungleSpider(CrawlSpider):
    name = "jungle-spider"


    start_urls = [f'https://www.welcometothejungle.com/en/jobs?page={page}&aroundQuery=worldwide&sortBy=mostRecent' for page in range(1, 51)]

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

        app_ld_json_script = soup.find("script", type="application/ld+json")
        if app_ld_json_script:
            content_dict = json.loads(app_ld_json_script.string)

            job_title = content_dict.get("title", DEFAULT_VAL)
            

            """
            something like 
            'jobLocation': [{'@type': 'Place',
                                        'address': {'@type': 'PostalAddress',
                                            'addressLocality': 'Lescar',
                                            'postalCode': '64230',
                                            'streetAddress': 'Lescar, Nouvelle-Aquitaine, France',
                                            'addressRegion': 'Pyrénées-Atlantiques',
                                            'addressCountry': 'FR'}}],
            """
            try:
                location_dict = content_dict["jobLocation"][0]['address']
                location = location_dict.get("streetAddress", "") + location_dict.get("addressLocality", "") + location_dict.get("addressCountry", "")
            except:
                location = DEFAULT_VAL
            
            try:
                min_academic_qualification_str = content_dict['educationRequirements']['credentialCategory'].lower()
                
                if "postgraduate" in min_academic_qualification_str:
                    min_academic_qualification = AcademicQualification.MASTERS
                if 
            except:


        # create JobItemScrapy object
        job_item_scrapy = JobItemScrapy(
            id=id,
            source=JobSource.ZHILIAN,
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
