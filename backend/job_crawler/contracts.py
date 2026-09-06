# -*- coding: utf-8 -*-
"""采集层统一契约：四态判别、归一化结果、跨源指纹。

参见 openspec/changes/job-source-adapter-refactor/design.md（决策 2/3）：
- 四态语义以探活实测为准（docs/data-sources/probe-report-2026-09-06.md）
- 指纹 = sha1(norm(company)|norm(title)|norm(location))，不参与向量内容
"""
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from app.models.constants import AcademicQualification, JobSource, RecruitmentType


class FetchState(Enum):
    OK = "ok"                                  # 200 且有数据
    NO_BOARD = "no_board"                      # 404：该公司/源不存在
    EMPTY = "empty"                            # 200 但 0 条（≠ no_board！）
    FETCH_FAILED = "fetch_failed"              # 超时/5xx/反爬拦截


# 空白与常见标点统一按"非词语字符"移除（unicode 感知，保留中英文与数字）
_NON_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)


def norm(s: Optional[str]) -> str:
    """指纹归一化：NFKC -> 移除所有空白与常见标点 -> casefold。"""
    if s is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(s))
    normalized = _NON_WORD_RE.sub("", normalized)
    return normalized.casefold()


def compute_fingerprint(company: Optional[str], title: Optional[str],
                        location: Optional[str]) -> str:
    """跨源指纹：sha1(f"{norm(company)}|{norm(title)}|{norm(location)}")。

    同公司同岗同地不同 URL → 相同；任一字段不同 → 不同。
    """
    key = f"{norm(company)}|{norm(title)}|{norm(location)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


@dataclass
class NormalizedJob:
    """各源 normalize() 的统一产出，由基类 _to_item 转 JobItemScrapy。"""

    source: JobSource
    source_url: str
    external_id: str = ""
    company_name: str = ""
    job_title: str = ""
    location: str = ""
    salary: Optional[str] = None              # 展示文本
    salary_min: Optional[int] = None          # 结构化（新增列）
    salary_max: Optional[int] = None
    recruitment_type: RecruitmentType = RecruitmentType.EXPERIENCED
    min_academic_qualification: AcademicQualification = AcademicQualification.ALL
    published_at: Optional[datetime] = None   # 新增列（TIMESTAMPTZ，aware datetime）
    update_time: Optional[datetime] = None    # 存量语义：naive datetime
    description: str = ""                     # 纯文本（HTML 剥离后）
