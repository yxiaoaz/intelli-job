import sys
from pathlib import Path
from scrapy import cmdline
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from job_crawler import settings
from job_crawler.spiders.shixiseng_graduate_spider import ShixisengGraduateSpider
from job_crawler.spiders.shixiseng_intern_spider import ShixisengInternSpider
from job_crawler.spiders.zhilian_spider import ZhilianSpider
from job_crawler.spiders.welcome_to_the_jungle_spider import WelcomeToTheJungleSpider
from job_crawler.spiders.ct_goodjob_hk_spider import CTGoodJobSpider
from init_db import init_db, init_vector_db

if __name__ == "__main__":
    # 初始化 SQL 数据库
    import asyncio
    asyncio.run(init_db())
    
    # 初始化向量数据库（如果不存在则创建）
    init_vector_db(rewrite_if_exists=False)
    
    print("✅ 数据库初始化完成")

    # 启动爬虫
    # cmdline.execute("scrapy crawl zhilian-spider".split())
    crawler_settings = Settings()
    crawler_settings.setmodule(settings)
    process = CrawlerProcess(crawler_settings)
    process.crawl(ShixisengGraduateSpider)
    process.crawl(ShixisengInternSpider)
    process.crawl(ZhilianSpider)
    #process.crawl(WelcomeToTheJungleSpider)
    #process.crawl(CTGoodJobSpider)
    process.start()  # the script will block here until all crawling jobs are finished
