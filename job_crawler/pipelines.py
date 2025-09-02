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
from app.models.job import JobItem
from app.services.storage.db_controller import DBController
from app.services.storage.engine import engine
from app.services.storage.utils import session_scope
from app.services.language_modeling.open_ai_service_provider import (
    OpenAIServiceProvider,
)
from app.services.storage.zilliz_controller import ZillizController

# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))

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

        self.db_controller = DBController(engine)
        self.embedding_service = OpenAIServiceProvider(
            api_url=os.getenv("LLM_EMBEDDING_API_URL"),
            api_key=os.getenv("LLM_EMBEDDING_API_KEY"),
        )
        self.vector_db_controller = ZillizController(
            uri=os.getenv("ZILLIZ_URI"), token=os.getenv("ZILLIZ_TOKEN")
        )

        self._embed_buffer: List[JobItem] = []
        self._batch_size = 1000  # number of parsed items needed for a batch embedding generation request
        self._last_flush_time = time.time()
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
        """generate embedding request for a batch of `JobItem`"""
        self._last_flush_time = time.time()

        logger.info(
            f"[{self.spider_name}] Flushing {len(current_buffer_elements)} items..."
        )

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

        with session_scope(self.db_controller.session_maker) as session:
            self.db_controller.insert_job_item(session, current_buffer_elements)

        logger.info(
            f"[{self.spider_name}] Uploaded {len(current_buffer_elements)} items to SQL db, but pending embedding processing."
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

        self.vector_db_controller.insert_job_items(embeddings)
        logger.info(
            f"[{self.spider_name}] Uploaded embeddings to vector db for batch file: {batch_file}"
        )

        # update embedding generation status
        with session_scope(self.db_controller.session_maker) as session:
            self.db_controller.update_job_item_embedding_status_bulk(
                session, [uuid.UUID(e["id"]) for e in embeddings], True
            )

        logger.info(
            f"[{self.spider_name}] Updated embedding status in SQL db for batch file: {batch_file}"
        )

    def process_item(self, item: scrapy.Item, spider):
        """
        This method is called on each `scrapy.Item` generated by spider.parse()
        """
        if self.redis_db.hexists(parsed_url_redis_cache_key, str(item["id"])):
            # logger.info(f"[{self.spider_name}] Duplicate item found: {item['url']}")
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
