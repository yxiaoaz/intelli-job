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
        self.parsed_job_items: List[JobItem] = []
        self.batch_job_files: List[str] = []

        self._embed_buffer: List[JobItem] = []
        self._batch_size = 2000  # number of parsed items needed for a batch embedding generation request
        self._last_flush_time = time.time()
        self._buffer_lock = threading.Lock()

        self._flush_thread = threading.Thread(
            target=self._auto_flush_buffer, daemon=True
        )
        self._flush_thread.start()

    # def open_spider(self, spider):
    #     """
    #     This method is called upon the creation of a spider. Initialize the db connections and embedding service.
    #     """
    #     logging.getLogger("scrapy").setLevel(logging.ERROR)  # Or logging.ERROR, logging.FATAL

    def close_spider(self, spider):

        # self.redis_db.bgsave()

        # clear out SQL items pending insertion
        # if self.parsed_job_items:
        #     with session_scope(self.db_controller.session_maker) as session:
        #         self.db_controller.insert_job_item(session, self.parsed_job_items)

        # bulk insert into vector db
        # self.update_vector_db()

        # 强制刷新剩余缓冲项
        with self._buffer_lock:
            if self._embed_buffer:
                self._flush_embed_buffer()

    def update_vector_db(self):
        if self.batch_job_files:
            for idx, batch_job_file in enumerate(self.batch_job_files):
                embeddings: List[Dict[str, Any]] = (
                    self.embedding_service.get_embedding_batch(
                        input_file_path=batch_job_file,
                        output_file_path=os.path.join(
                            get_project_root(), "files", f"batch_job_{idx}_output.jsonl"
                        ),
                    )
                )
                self.vector_db_controller.insert_job_items(embeddings)

                # update embedding status in SQL db
                with session_scope(self.db_controller.session_maker) as session:
                    self.db_controller.update_job_item_embedding_status_bulk(
                        session, [uuid.UUID(e["id"]) for e in embeddings], True
                    )

    def _auto_flush_buffer(self):
        """
        Check regularly whether there are enough `JobItem` instances accumulated.
        If so, issue a batch embedding generation request.
        """
        while True:
            time.sleep(10)  # 每10秒检查一次
            do_flushing = False
            current_buffer_elements: List[JobItem] = []
            # logger.info("Checking embed buffer for flushing...")
            with self._buffer_lock:
                # logger.info("_auto_flush_buffer acquired lock..")
                if len(self._embed_buffer) >= self._batch_size:
                    logger.info("Bathch size reached, flushing buffer...")
                    do_flushing = True
                    current_buffer_elements = list(self._embed_buffer)  # hard copy
                    self._embed_buffer = []  # clear the buffer

            # release lock before flushing
            if do_flushing:
                self._flush_embed_buffer(current_buffer_elements)
                logger.info("_auto_flush_buffer released lock and starts flushing..")
                do_flushing = False

    def _flush_embed_buffer(self, current_buffer_elements: List[JobItem] = []):
        """generate embedding request for a batch of `JobItem`"""
        self._last_flush_time = time.time()

        logger.info(f"Flushing {len(current_buffer_elements)} items...")

        # generate a batch file
        batch_dir = os.path.join(get_project_root(), "files", "embed_batches")
        os.makedirs(batch_dir, exist_ok=True)
        batch_file = os.path.join(
            batch_dir, f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        )

        id_job_item_content_map: Dict[str, str] = (
            {}
        )  # temporarily stores mapping from uuid to job item content
        with open(batch_file, "w", encoding="utf-8") as f:
            for item in current_buffer_elements:
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

        with session_scope(self.db_controller.session_maker) as session:
            self.db_controller.insert_job_item(session, current_buffer_elements)
        logger.info(
            f"Uploaded {len(current_buffer_elements)} items to SQL db, but pending embedding processing."
        )

        # process the batch
        self._process_batch_file(batch_file, id_job_item_content_map)

    def _process_batch_file(self, batch_file, id_job_item_content_map):
        """
        Generate embedding for a batch of file.
        This method is ran on a different thread from the crawler.
        """
        logger.info(f"Processing batch file: {batch_file}")
        embeddings = self.embedding_service.get_embedding_batch(
            input_file_path=batch_file, output_file_path=batch_file + ".output.jsonl"
        )
        logger.info(f"Generated embeddings for batch file: {batch_file}")

        # `embeddings` is of the form [{"id": str(uuid), "embedding": List[float]}]
        # needs to add keys "content" and "language" to each dict element
        # "sparse_vector"  will be generated automatically by BM25 function of Zillis
        for item_dict in embeddings:
            item_dict["content"] = id_job_item_content_map[item_dict["id"]]
            item_dict["language"] = langid.classify(item_dict["content"])[0]

        self.vector_db_controller.insert_job_items(embeddings)
        logger.info(f"Uploaded embeddings to vector db for batch file: {batch_file}")

        # update embedding generation status
        with session_scope(self.db_controller.session_maker) as session:
            self.db_controller.update_job_item_embedding_status_bulk(
                session, [uuid.UUID(e["id"]) for e in embeddings], True
            )

        logger.info(f"Updated embedding status in SQL db for batch file: {batch_file}")

    def process_item(self, item: scrapy.Item, spider):
        """
        This method is called on each `scrapy.Item` generated by spider.parse()
        """

        if self.redis_db.hexists(parsed_url_redis_cache_key, str(item["id"])):
            logger.info(f"Duplicate item found: {item['url']}")
            return item
        self.num_items_parsed += 1
        if self.num_items_parsed % 100 == 0:
            logger.info(f"Processed {self.num_items_parsed} items so far...")
        try:
            # 添加到内存缓冲区
            with self._buffer_lock:
                # logger.info("process_item acquired lock..")
                self._embed_buffer.append(JobItem.from_scrapy_item(item))
            # logger.info("process_item released lock..")
            # record crawled url at redis
            self.redis_db.hset(parsed_url_redis_cache_key, str(item["id"]), 0)
        except Exception as e:
            logger.error(
                f"Exception occured when parsing job item {item['id']} from url {item['url']}",
                exc_info=True,
            )
        finally:
            return item
