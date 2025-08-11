from scrapy import cmdline
from scrapy.crawler import CrawlerProcess

from job_crawler.pipelines import settings
from job_crawler.spiders.shixiseng_graduate_spider import ShixisengGraduateSpider
from job_crawler.spiders.shixiseng_intern_spider import ShixisengInternSpider
from job_crawler.spiders.zhilian_spider import ZhilianSpider
from init_db import init_sql_db, init_milvus

if __name__ == "__main__":

    init_sql_db()
    init_milvus(rewrite_if_exists=False)

    # cmdline.execute("scrapy crawl zhilian-spider".split())
    process = CrawlerProcess(settings)
    process.crawl(ShixisengGraduateSpider)
    process.crawl(ShixisengInternSpider)
    process.crawl(ZhilianSpider)
    process.start()  # the script will block here until all crawling jobs are finished
