# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"


BOT_NAME = "job_crawler"

SPIDER_MODULES = ["job_crawler.spiders"]
# NEWSPIDER_MODULE = 'job_crawler.spiders'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# USER_AGENT = 'job_crawler (+http://www.yourdomain.com)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 16
DOWNLOAD_DELAY = 2
# 反爬收紧（job-source-adapter-refactor 决策 6）：唯一的行为性收紧，
# 探活显示多数失败模式与突发并发相关
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# AUTOTHROTTLE：起始延迟 2s，最大 10s，自适应调整
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10

# 重试：403/429 入重试并指数退避（探活实测 403 是常态而非例外）
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 403, 429]

# 代理插槽：读取 CRAWLER_HTTP_PROXY 环境变量，为空则直连。
# HttpProxyMiddleware 原生支持（默认启用）：设置 env var 后请求即走代理，
# 不强制采购，但国内线上线前必须填（GitHub Actions 数据中心 IP 易被封）。
# 仅需设置环境变量，无代码改动。

# Disable cookies (enabled by default)
COOKIES_ENABLED = False


# Enable or disable downloader middlewares
# See https://doc.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "job_crawler.random_user_agent.RandomUserAgent": 1,
}

# Configure item pipelines
# See https://doc.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "job_crawler.pipelines.JobCrawlerPipeline": 300,
    # 源健康度统计（job-source-adapter-refactor 决策 5）：后于落库 pipeline 执行
    "job_crawler.pipelines.JobSourceHealthPipeline": 400,
}

CLOSESPIDER_ITEMCOUNT = 10000

 
