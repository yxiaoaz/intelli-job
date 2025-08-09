from scrapy import cmdline

from init_db import init_sql_db, init_milvus

if __name__ == "__main__":

    init_sql_db()
    init_milvus(rewrite_if_exists=False)
    
    cmdline.execute("scrapy crawl zhilian-spider".split())
