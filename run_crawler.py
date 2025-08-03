from scrapy.crawler import CrawlerProcess

from app.crawler.zhilian import ZhilianSpider
from app.crawler.utils import USER_AGENT_LIST
from app.models.base import Base
from app.services.storage.engine import engine



if __name__ == "__main__":

    Base.metadata.create_all(engine)

    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/5.0 (compatible; Baiduspider-render/2.0; +http://www.baidu.com/search/spider.html)'
    })

    process.crawl(ZhilianSpider)
    process.start()

