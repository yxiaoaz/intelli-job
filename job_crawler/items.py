# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"

import scrapy


class JobItemScrapy(scrapy.Item):

    id = scrapy.Field()

    # tracing info
    source = scrapy.Field()
    url = scrapy.Field()

    # embedding
    embedding_generated = scrapy.Field()

    # basic info
    job_title = scrapy.Field()
    update_time = scrapy.Field()
    location = scrapy.Field()
    recruitment_type = scrapy.Field()
    min_academic_qualification = scrapy.Field()
    salary = scrapy.Field()
    description = scrapy.Field()

    # company info
    company_name = scrapy.Field()
