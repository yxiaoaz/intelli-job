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
        #ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
        #print('当前 UA : ' + ua)
        request.headers.setdefault("User-Agent", ua)
