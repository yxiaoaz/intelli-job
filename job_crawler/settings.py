# -*- coding: utf-8 -*-


BOT_NAME = "job_crawler"

SPIDER_MODULES = ["job_crawler.spiders"]
# NEWSPIDER_MODULE = 'job_crawler.spiders'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# USER_AGENT = 'job_crawler (+http://www.yourdomain.com)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 32


# Disable cookies (enabled by default)
COOKIES_ENABLED = False


# Enable or disable downloader middlewares
# See https://doc.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "job_crawler.random_user_agent.RandomUserAgent": 543,
}

# Configure item pipelines
# See https://doc.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "job_crawler.pipelines.JobCrawlerPipeline": 300,
}
