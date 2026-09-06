# job_crawler 采集层指南

统一的岗位采集层：所有源（HTML 爬虫型与 JSON API 型）继承 `BaseJobSpider`，
四态判别、跨源指纹、落库冲突容错、健康度统计全部收敛在基类与 pipeline。

## 新增一个数据源的步骤（共 4 处）

1. **实现 spider**（唯一必写方法是 `normalize`）：

   ```python
   # job_crawler/spiders/xxx_spider.py
   from scrapy import Request
   from job_crawler.base_spider import BaseJobSpider
   from job_crawler.contracts import FetchState, NormalizedJob
   from app.models.constants import JobSource

   class XxxSpider(BaseJobSpider):   # HTML 型源写 (CrawlSpider, BaseJobSpider)
       name = "xxx-spider"
       job_source = JobSource.GREENHOUSE   # 必须声明，健康度统计依赖

       def start_requests(self):
           yield Request(api_url, callback=self.parse_board,
                         errback=self.on_fetch_error)

       def parse_board(self, response):
           state, data = self.fetch_json(response)   # 四态判别统一实现
           if state is not FetchState.OK:
               return
           count = 0
           for raw in data:
               yield self._to_item(self.normalize(raw))
               count += 1
           self.fetch_state = self.classify_response(response, parsed_count=count)

       def normalize(self, raw) -> NormalizedJob:
           # 原始记录 → 归一化结果；HTML 源的 raw 是 response，
           # 回调里直接 `yield from self.emit_items(response)` 即可
           ...
   ```

   - `FetchState` 四态：`OK / NO_BOARD(404) / EMPTY(200 但 0 条) / FETCH_FAILED`，
     **禁止** `resp.json().get("jobs", [])` 式的一把梭（会把后三种折叠成"零岗位"）。
   - 裸数组响应（如 Lever）由 `fetch_json` 原样返回 list，判断 `isinstance(list)`。
   - 长延迟源用 per-spider `custom_settings={"DOWNLOAD_TIMEOUT": 120}` 覆盖。

2. **加枚举**：`app/models/constants.py` 的 `JobSource` 加枚举值，并在
   `backend/scripts/fix_enum_types.py` 的 `enum_definitions` 登记
   （PG 原生 ENUM 需 `ALTER TYPE ... ADD VALUE`，跑一次该脚本）。

3. **注册调度**：`run_crawler.py` 的 crawl 列表加入新 spider
   （健康度 DISABLED 的源会被自动跳过，7 天后自动放行复检）。

4. **测试**：解析器单测放 `backend/tests/job_crawler/`，
   真实响应样本放 `job_crawler/fixtures/<source>/`（不要伪造数据），
   离线驱动，不联网。

## 各层职责

| 层 | 职责 |
|---|---|
| `contracts.py` | `FetchState` 四态、`NormalizedJob`、`norm()`/`compute_fingerprint()`（sha1(company\|title\|location)） |
| `base_spider.py` | 四态判别（`fetch_json`/`classify_response`）、`normalize` 契约、`_to_item` 统一算指纹 |
| `pipelines.JobCrawlerPipeline` | Redis URL 去重（效率层）、过期过滤、批量落库（`ON CONFLICT DO NOTHING`，跨源同岗由 DB 唯一约束兜底）、embedding batch + Milvus |
| `pipelines.JobSourceHealthPipeline` | 源健康度：仅 FETCH_FAILED 计失败，EMPTY 不计，NO_BOARD 连续 3 次联动注册表 DEAD；DISABLED 7 天自愈复检 |
| `settings.py` | AUTOTHROTTLE / 重试（含 403/429）/ per-domain 并发 / 代理插槽（`CRAWLER_HTTP_PROXY`） |

## 历史指纹回填

指纹算法变更后执行一次（幂等）：

```bash
python scripts/backfill_fingerprint.py --dry-run   # 先出报告，人工确认
python scripts/backfill_fingerprint.py --apply     # 确认后执行（先删 Milvus 再删 SQL）
```
