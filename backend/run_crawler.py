import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
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
from job_crawler.spiders.lever_spider import LeverSpider
from job_crawler.spiders.greenhouse_spider import GreenhouseSpider
from job_crawler.spiders.ashby_spider import AshbySpider
from init_db import init_db, init_vector_db

# DISABLED 源自愈复检窗口（job-source-adapter-refactor 决策 5）
RECHECK_INTERVAL_DAYS = 7


def filter_disabled_sources(spider_classes):
    """调度层消费健康度表：DISABLED 源默认跳过，

    但 last_run_at 距今 ≥7 天时放行一次复检（自愈路径，依据 last_run_at
    判断，不新增状态列）；DEGRADED 源打印告警但仍调度。
    """
    from app.models import JobSourceHealth
    from app.services.crawler_db_controller import CrawlerDBController

    controller = CrawlerDBController()
    allowed = []
    for cls in spider_classes:
        source = getattr(cls, "job_source", None)
        if source is None:
            print(f"[skip-check] {cls.name}: 未声明 job_source，默认放行")
            allowed.append(cls)
            continue

        with controller.session_maker() as session:
            row = session.get(JobSourceHealth, source)

        if row is None or row.status == "ACTIVE":
            allowed.append(cls)
        elif row.status == "DEGRADED":
            print(f"⚠️  {source.name} DEGRADED（连续失败 {row.consecutive_fail}），继续调度")
            allowed.append(cls)
        else:  # DISABLED
            last_run = row.last_run_at
            if last_run and (datetime.utcnow() - last_run) < timedelta(
                    days=RECHECK_INTERVAL_DAYS):
                print(f"🚫 跳过 DISABLED 源 {source.name} "
                      f"（复检窗口未到，last_run_at={last_run}）")
            else:
                print(f"♻️  DISABLED 源 {source.name} 到达 {RECHECK_INTERVAL_DAYS} 天"
                      f"复检窗口，放行一次复检")
                allowed.append(cls)
    return allowed


def _source_key(spider_cls) -> str:
    source = getattr(spider_cls, "job_source", None)
    return source.name.lower() if source else ""


def select_spider_classes():
    """按 CRAWLER_SOURCE_FILTER（逗号分隔 JobSource 名，如 lever,zhilian）

    过滤本次运行的源；未设置则跑全部启用源。
    """
    all_sources = [LeverSpider, GreenhouseSpider, AshbySpider,
                   ShixisengGraduateSpider, ShixisengInternSpider, ZhilianSpider,
                   WelcomeToTheJungleSpider, CTGoodJobSpider]
    filter_env = os.getenv("CRAWLER_SOURCE_FILTER", "").strip().lower()
    if not filter_env:
        return all_sources
    keys = {k.strip() for k in filter_env.split(",") if k.strip()}
    return [c for c in all_sources if _source_key(c) in keys]


if __name__ == "__main__":
    # 初始化 SQL 数据库
    import asyncio
    asyncio.run(init_db())
    
    # 初始化向量数据库（如果不存在则创建）
    init_vector_db(rewrite_if_exists=False)
    
    print("✅ 数据库初始化完成")

    # 启动爬虫（DISABLED 源跳过，7 天自愈复检）
    # 顺序：Lever 优先（长延迟 55~61s，避免拖垮整体），Greenhouse/Ashby 随后；
    # GH Actions 用 CRAWLER_SOURCE_FILTER 拆分 step（Lever 独立限时）
    crawler_settings = Settings()
    crawler_settings.setmodule(settings)
    process = CrawlerProcess(crawler_settings)
    disabled_sources = (WelcomeToTheJungleSpider, CTGoodJobSpider)
    for spider_cls in filter_disabled_sources(select_spider_classes()):
        if spider_cls in disabled_sources:
            continue  # 停用源不参与调度（迁移后保持停用）
        process.crawl(spider_cls)
    process.start()  # the script will block here until all crawling jobs are finished
