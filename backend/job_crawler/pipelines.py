# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"

import os
from typing import Any, List, Dict
import logging
import json
import uuid
import time
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
import threading


from dotenv import load_dotenv
import redis
import scrapy
from scrapy.exceptions import DropItem
from scrapy.utils.project import get_project_settings
import langid

from app.config import get_project_root
from app.models import JobItem, JobSourceHealth
from app.services.crawler_db_controller import CrawlerDBController
from app.services.crawler_embedding_service import CrawlerEmbeddingService
from app.services.vector_db_service import VectorDBService
from job_crawler.contracts import FetchState

# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))

# logger = logging.getLogger(__name__)
settings = get_project_settings()

# logging.basicConfig(filename=os.path.join(get_project_root(), "logs", "job_crawler.log"),
#                     filemode='a',
#                     format='%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s',
#                     datefmt='%Y-%m-%d %H:%M:%S',)

logger = logging.getLogger(__name__)

# logger = logging.getLogger(__name__)
settings = get_project_settings()

# logging.basicConfig(filename=os.path.join(get_project_root(), "logs", "job_crawler.log"),
#                     filemode='a',
#                     format='%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s',
#                     datefmt='%Y-%m-%d %H:%M:%S',)

logger = logging.getLogger(__name__)

parsed_url_redis_cache_key = "parsed_url"


class JobCrawlerPipeline(object):
    def __init__(self):
        logging.getLogger("scrapy").setLevel(
            logging.ERROR
        )  # Or logging.ERROR, logging.FATAL

        self.redis_db = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=10771,
            decode_responses=True,
            username="default",
            password=os.getenv("REDIS_PASSWORD"),
        )

        self.num_batch_jobs = 0
        self.num_items_parsed = 0
        self.num_items_dropped = 0

        # 初始化数据库控制器（同步版本）
        self.db_controller = CrawlerDBController()
        
        # 初始化 embedding 服务
        self.embedding_service = CrawlerEmbeddingService(
            api_url=os.getenv("LLM_EMBEDDING_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            api_key=os.getenv("LLM_EMBEDDING_API_KEY"),
        )
        
        # 初始化向量数据库服务
        self.vector_db_service = VectorDBService()

        self._embed_buffer: List[JobItem] = []
        self._batch_size = 100  # number of parsed items needed for a batch embedding generation request
        self._buffer_lock = threading.Lock()

        self._flush_thread = threading.Thread(
            target=self._auto_flush_buffer, daemon=True
        )
        self.closing = False
        self._flush_thread.start()
        self.spider_name = None

    def open_spider(self, spider):
        """
        This method is called upon the creation of a spider
        """
        self.spider_name = spider.name

        if self.spider_name == "jungle-spider":
            self._batch_size = 100
        logger.info(f"Initializing spider: {self.spider_name} on pipeline {self}")

    def close_spider(self, spider):

        logger.info(f"{spider.name} finished")

        self.closing = True
        self._flush_thread.join()

        # flush the remaining
        if self._embed_buffer:
            logger.info(
                f"[{self.spider_name}] Sweeping off {len(self._embed_buffer)} remaining elements"
            )
            self._flush_embed_buffer(self._embed_buffer)

    def _auto_flush_buffer(self):
        """
        Check regularly whether there are enough `JobItem` instances accumulated.
        If so, issue a batch embedding generation request.
        """
        while not self.closing:
            time.sleep(10)  # 每10秒检查一次
            do_flushing = False
            current_buffer_elements: List[JobItem] = []
            # logger.info("Checking embed buffer for flushing...")
            with self._buffer_lock:
                # logger.info("_auto_flush_buffer acquired lock..")
                if len(self._embed_buffer) >= self._batch_size:
                    logger.info(
                        f"[{self.spider_name}] Batch size reached, flushing buffer..."
                    )
                    do_flushing = True
                    current_buffer_elements = list(self._embed_buffer)  # hard copy
                    self._embed_buffer = []  # clear the buffer

            # release lock before flushing
            if do_flushing:
                logger.info("_auto_flush_buffer released lock and starts flushing..")
                self._flush_embed_buffer(current_buffer_elements)
                do_flushing = False

    def _flush_embed_buffer(self, current_buffer_elements: List[JobItem] = []):
        """generate embedding request for a batch of `JobItem`

        落库采用 ON CONFLICT DO NOTHING（design 决策 8）：仅对实际插入的行
        生成 embedding batch 与写 Milvus，冲突行静默跳过、不整批回滚。
        """

        logger.info(
            f"[{self.spider_name}] Flushing {len(current_buffer_elements)} items..."
        )

        # 1. 先落库，拿实际插入的 id（冲突行被 DB 静默跳过）
        with self.db_controller.session_maker() as session:
            try:
                inserted_ids = self.db_controller.insert_job_item(
                    session, current_buffer_elements
                )
                session.commit()
            except Exception as e:
                logger.error(f"Failed to insert job items: {e}")
                session.rollback()
                raise

        if not inserted_ids:
            logger.info(
                f"[{self.spider_name}] All {len(current_buffer_elements)} items "
                f"were conflicts (url/fingerprint), nothing to embed."
            )
            return

        inserted_id_set = {str(i) for i in inserted_ids}

        # generate a batch file
        batch_dir = os.path.join(get_project_root(), "files", "embed_batches")
        os.makedirs(batch_dir, exist_ok=True)
        batch_file = os.path.join(
            batch_dir,
            f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.spider_name}.jsonl",
        )

        id_job_item_content_map: Dict[str, str] = (
            {}
        )  # temporarily stores mapping from uuid to job item content
        with open(batch_file, "w", encoding="utf-8") as f:
            for item in current_buffer_elements:
                # 未插入的冲突条目不得进入 embedding batch 与 Milvus
                if str(item.id) not in inserted_id_set:
                    continue
                try:
                    json.dump(
                        {
                            "custom_id": str(item.id),
                            "method": "POST",
                            "url": "/v1/embeddings",
                            "body": {
                                "model": "text-embedding-v4",
                                "input": str(item),
                                "encoding_format": "float",
                            },
                        },
                        f,
                        ensure_ascii=False,
                    )
                    id_job_item_content_map[str(item.id)] = str(item)
                    f.write("\n")
                except:
                    continue

        logger.info(
            f"[{self.spider_name}] Uploaded {len(id_job_item_content_map)} items "
            f"to SQL db ({len(current_buffer_elements) - len(id_job_item_content_map)} "
            f"conflicts skipped), but pending embedding processing."
        )

        # process the batch
        self._process_batch_file(batch_file, id_job_item_content_map)

    def _process_batch_file(self, batch_file, id_job_item_content_map):
        """
        Generate embedding for a batch of file.
        This method is ran on a different thread from the crawler.
        """
        logger.info(f"[{self.spider_name}] Processing batch file: {batch_file}")
        embeddings = self.embedding_service.get_embedding_batch(
            input_file_path=batch_file, output_file_path=batch_file + ".output.jsonl"
        )
        logger.info(
            f"[{self.spider_name}] Generated embeddings for batch file: {batch_file}"
        )

        # `embeddings` is of the form [{"id": str(uuid), "embedding": List[float]}]
        # needs to add keys "content" and "language" to each dict element
        # "sparse_vector"  will be generated automatically by BM25 function of Zillis
        for item_dict in embeddings:
            item_dict["content"] = id_job_item_content_map[item_dict["id"]]
            item_dict["language"] = langid.classify(item_dict["content"])[0]

        self.vector_db_service.insert_embeddings(embeddings)
        logger.info(
            f"[{self.spider_name}] Uploaded embeddings to vector db for batch file: {batch_file}"
        )

        # update embedding generation status
        with self.db_controller.session_maker() as session:
            try:
                self.db_controller.update_job_item_embedding_status_bulk(
                    session, [uuid.UUID(e["id"]) for e in embeddings], True
                )
                session.commit()
            except Exception as e:
                logger.error(f"Failed to update embedding status: {e}")
                session.rollback()
                raise

        logger.info(
            f"[{self.spider_name}] Updated embedding status in SQL db for batch file: {batch_file}"
        )

    def process_item(self, item: scrapy.Item, spider):
        """
        This method is called on each `scrapy.Item` generated by spider.parse()
        """
        # 过滤爬取失败的记录：岗位名称和公司名称都未知
        if str(item.get("job_title")) == "未知" and str(item.get("company_name")) == "未知":
            self.num_items_dropped += 1
            if self.num_items_dropped % 100 == 0:
                logger.info(f"[{self.spider_name}] Dropped {self.num_items_dropped} invalid items (both job_title and company_name unknown).")
            raise DropItem(f"[{self.spider_name}] Incomplete item (job_title and company_name both unknown): {item['url']}")

        if self.redis_db.hexists(parsed_url_redis_cache_key, str(item["id"])):
            #logger.info(f"[{self.spider_name}] Duplicate item found: {item['url']}")
            raise DropItem(f"[{self.spider_name}] Duplicate item found: {item['url']}")
        
        # ignore outdated items (posted more than 2 months ago)
        if item['update_time'].replace(tzinfo=None) < datetime.now(tz=None) - relativedelta(months = 2):
            raise DropItem(f"[{self.spider_name}] Found item that is outdated: {item['url']}")

        # append to buffer, update on redis cache
        with self._buffer_lock:
            self._embed_buffer.append(JobItem.from_scrapy_item(item))
            self.redis_db.hset(parsed_url_redis_cache_key, str(item["id"]), 0)

        # log some statistics
        self.num_items_parsed += 1

        if self.num_items_parsed % 100 == 0:
            logger.info(f"[{self.spider_name}] Crawled {self.num_items_parsed} items.")

        return item


class JobSourceHealthPipeline(object):
    """源健康度统计（job-source-adapter-refactor 决策 5）。

    item 级只累加内存计数，spider 关闭时按源一次 upsert（每批次结束收口）。
    计数语义：仅 FETCH_FAILED 计入 consecutive_fail；EMPTY 不计 ok/fail；
    NO_BOARD 独立计数，连续 ≥3 联动注册表标 DEAD（若已建，仅标记 404 的 slug）。
    """

    def __init__(self):
        self.db_controller = CrawlerDBController()
        self._ok_count = 0
        self.spider_name = None

    def open_spider(self, spider):
        self.spider_name = spider.name
        self._ok_count = 0

    def process_item(self, item, spider):
        self._ok_count += 1
        return item

    def close_spider(self, spider):
        source = getattr(spider, "job_source", None)
        if source is None:
            logger.warning(
                f"[{self.spider_name}] spider 未声明 job_source，跳过健康度记录"
            )
            return

        state = getattr(spider, "fetch_state", FetchState.FETCH_FAILED)
        with self.db_controller.session_maker() as session:
            row = session.get(JobSourceHealth, source)
            created = row is None
            if row is None:
                row = JobSourceHealth(source=source)

            now = datetime.utcnow()
            row.last_run_at = now
            note = ""

            if state is FetchState.OK and not spider.no_board_slugs:
                row.ok_count = (row.ok_count or 0) + self._ok_count
                row.last_ok_at = now
                row.consecutive_fail = 0
                row.consecutive_no_board = 0
                # 复检 OK 即复位（DISABLED 自愈路径）
                row.status = "ACTIVE"
                note = "ok"
            elif state is FetchState.EMPTY:
                # 合法空板（招聘冻结期是常态）：仅更新 last_run_at，状态不变
                note = "empty board"
            elif state is FetchState.NO_BOARD or spider.no_board_slugs:
                # NO_BOARD 计数看“本轮是否有 404 的 board”：
                # 多 board 源整体为 OK 但个别 board 404 时也要累计，
                # 连续 ≥3 轮出现同一批 404 slug → 联动注册表标 DEAD
                if state is FetchState.OK:
                    # 混合轮次：健康 board 的产出照常计入 ok
                    row.ok_count = (row.ok_count or 0) + self._ok_count
                    row.last_ok_at = now
                row.consecutive_no_board = (row.consecutive_no_board or 0) + 1
                n = row.consecutive_no_board
                if n >= 3:
                    self._mark_registry_dead(spider, session)
                    note = f"no_board x{n} (registry DEAD linkage applied)"
                else:
                    note = f"no_board x{n}"
            else:  # FETCH_FAILED：唯一真正的系统级失败
                row.fail_count = (row.fail_count or 0) + 1
                row.consecutive_fail = (row.consecutive_fail or 0) + 1
                cf = row.consecutive_fail
                if cf >= 10:
                    row.status = "DISABLED"
                    logger.error(
                        f"[{self.spider_name}] source {source.name} DISABLED "
                        f"(consecutive_fail={cf})"
                    )
                elif cf >= 3 and row.status != "DISABLED":
                    row.status = "DEGRADED"
                    logger.warning(
                        f"[{self.spider_name}] source {source.name} DEGRADED "
                        f"(consecutive_fail={cf})"
                    )
                note = f"fetch_failed x{cf}"

            row.note = note[:512]
            session.add(row)
            session.commit()
            logger.info(
                f"[{self.spider_name}] health upsert: source={source.name} "
                f"state={state.value} status={row.status} created={created}"
            )

    @staticmethod
    def _mark_registry_dead(spider, session):
        """NO_BOARD 连续≥3：联动 company_ats_registry 标 DEAD（若已建）。

        仅标记 spider.no_board_slugs 指定的脏条目，不殃及同源其他 board；
        注册表未建（ats-job-source-integration 之前）时仅记日志。
        """
        slugs = getattr(spider, "no_board_slugs", set())
        source = getattr(spider, "job_source", None)
        if not slugs or source is None:
            logger.info(f"[{getattr(spider, 'name', '?')}] no no_board_slugs "
                        f"recorded, registry linkage skipped")
            return
        try:
            from app.models import JobAtsRegistry  # 注册表未建时 ImportError

            updated = (
                session.query(JobAtsRegistry)
                .filter(
                    JobAtsRegistry.ats_type == source.name.lower(),
                    JobAtsRegistry.board_slug.in_(slugs),
                )
                .update({"status": "DEAD"}, synchronize_session=False)
            )
            logger.warning(
                f"[{getattr(spider, 'name', '?')}] registry rows marked DEAD: "
                f"{sorted(slugs)} (updated={updated})"
            )
        except Exception as e:
            logger.info(
                f"[{getattr(spider, 'name', '?')}] registry DEAD linkage "
                f"skipped: {e}"
            )
