from scrapy import cmdline
from scrapy.crawler import CrawlerProcess

from job_crawler.pipelines import settings
from job_crawler.spiders.shixiseng_graduate_spider import ShixisengGraduateSpider
from job_crawler.spiders.shixiseng_intern_spider import ShixisengInternSpider
from job_crawler.spiders.zhilian_spider import ZhilianSpider
from job_crawler.spiders.welcome_to_the_jungle_spider import WelcomeToTheJungleSpider
from job_crawler.spiders.ct_goodjob_hk_spider import CTGoodJobSpider
from init_db import init_sql_db, init_milvus

if __name__ == "__main__":

    init_sql_db()
    init_milvus(rewrite_if_exists=False)

    # cmdline.execute("scrapy crawl zhilian-spider".split())
    process = CrawlerProcess(settings)
    process.crawl(ShixisengGraduateSpider)
    process.crawl(ShixisengInternSpider)
    process.crawl(ZhilianSpider)
    process.crawl(WelcomeToTheJungleSpider)
    process.crawl(CTGoodJobSpider)
    process.start()  # the script will block here until all crawling jobs are finished
