from datetime import datetime
import json
import uuid
import logging
import string

from bs4 import BeautifulSoup
from scrapy import Request
from scrapy.http import TextResponse
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from app.models.constant import JobSource, RecruitmentType, AcademicQualification
from job_crawler.items import JobItemScrapy
from job_crawler.utils import UNDERGRADUATE_EXPRESSIONS

DEFAULT_VAL = "NA"


class WelcomeToTheJungleSpider(CrawlSpider):
    name = "jungle-spider"

    allowed_domains = ['welcometothejungle.com']
    start_urls = [f'https://www.welcometothejungle.com/en/directory/{company_name_first_letter}' for company_name_first_letter in list(string.ascii_lowercase) + ['other'] ]

    rules = (
        Rule(
            LinkExtractor(allow = r'\/en\/companies\/[^/]+$'),  # "/en/companies/google", enter the company info page
            follow = True, # 
        ),
        Rule(
            LinkExtractor(allow = r'\/en\/companies\/[^/]+\/jobs+$'), # "/en/companies/google/jobs", enter the job info page of a single company
            callback = "extend_company_job_page",  # add pagination and sort-by-date parameter to url, resend request
        ),
        Rule(
            LinkExtractor(allow = r'\/en\/companies\/[^/]+\/jobs\/[^/]+$'),  # single job item page
            callback = "parse", # 
        )
    )

    custom_settings = {
        'DOWNLOAD_DELAY': 3.0,
    }

    def extend_company_job_page(self, response: TextResponse):
        for page in range(1, 31):
            yield Request(response.url + f'?sortBy=mostRecent&page={page}')

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
            company_name = content_dict.get('hiringOrganization', {}).get("name", "")
            update_time = datetime.strptime(
                    content_dict["datePosted"],
                    "%Y-%m-%dT%H:%M:%SZ",
                ) # UTC time

            try:
                description = BeautifulSoup(content_dict['description'], 'html.parser').get_text(strip = True, separator = "\n")
            except:
                description = DEFAULT_VAL
            
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

                # this is a bit tricky, they seem to group undergraduate degrees into "associate" as well
                min_academic_qualification_str = content_dict['educationRequirements']['credentialCategory'].lower()
                
                if "postgraduate" in min_academic_qualification_str:
                    min_academic_qualification = AcademicQualification.MASTERS
                elif "associate" in min_academic_qualification_str:
                    if qualifications_str:=content_dict.get("qualifications", ""):
                        qualifications_str = qualifications_str.lower()
                        
                        if any(undergraduate_term in qualifications_str for undergraduate_term in UNDERGRADUATE_EXPRESSIONS):
                            min_academic_qualification = AcademicQualification.UNDERGRADUATE
                    else:
                        min_academic_qualification = AcademicQualification.ASSOCIATE
                
            except:
                min_academic_qualification = AcademicQualification.ALL
            
            try:
                recruitment_type_str = content_dict['employmentType'].lower()
                if "intern" in recruitment_type_str:
                    # they don't seem to have a lot of specific fresh-grad hiring
                    # and they are grouped into "intern" as well
                    # detect the word "graduate" in job title should be ok for now 
                    if "graduate" in job_title or "graduate" in description:
                        recruitment_type = RecruitmentType.GRADUATE
                    else:
                        recruitment_type = RecruitmentType.INTERN
            except:
                recruitment_type = RecruitmentType.EXPERIENCED


            try:
                salary_dict = content_dict['baseSalary']
                salary = salary_dict.get("currency", "(unknown currency)") + " " + salary_dict.get("value", {}).get("minValue", "0") + salary_dict.get("value", {}).get("maxValue", "unknown upper limit") + " " + salary_dict.get("value", {}).get("unitText", "") 
            except:
                salary = DEFAULT_VAL
            

        # create JobItemScrapy object
        job_item_scrapy = JobItemScrapy(
            id=id,
            source=JobSource.WELCOME_TO_THE_JUNGLE,
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