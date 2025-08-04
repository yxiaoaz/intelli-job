from scrapy import cmdline

from init_db import init_db

if __name__ == "__main__":

    init_db()
    cmdline.execute("scrapy crawl zhilian-spider".split())
