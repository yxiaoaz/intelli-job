import scrapy


class JobItemScrapy(scrapy.Item):

    id = scrapy.Field()

    # tracing info
    source = scrapy.Field()
    url = scrapy.Field()
    fingerprint = scrapy.Field()

    # embedding
    embedding_generated = scrapy.Field()

    # basic info
    job_title = scrapy.Field()
    update_time = scrapy.Field()
    location = scrapy.Field()
    recruitment_type = scrapy.Field()
    min_academic_qualification = scrapy.Field()
    salary = scrapy.Field()
    salary_min = scrapy.Field()   # 结构化薪资下限（新增列，可空）
    salary_max = scrapy.Field()   # 结构化薪资上限（新增列，可空）
    published_at = scrapy.Field()  # 发布时间（新增列，TIMESTAMPTZ，可空）
    description = scrapy.Field()

    # company info
    company_name = scrapy.Field()
