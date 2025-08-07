# -*- coding: utf-8 -*-
__author__ = "yicong.xiao"

import logging
import random

from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware

from job_crawler.utils import USER_AGENT_LIST

# logger = logging.getLogger(__name__)


class RandomUserAgent(UserAgentMiddleware):
    """
    随机选取 UA
    """

    def process_request(self, request, spider):
        ua = random.choice(USER_AGENT_LIST)
        # logger.info('当前 UA : ' + ua)
        request.headers.setdefault("User-Agent", ua)
