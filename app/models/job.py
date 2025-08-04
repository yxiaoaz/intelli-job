import uuid

import scrapy
from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    JSON,
    Text,
    DateTime,
    String,
    ForeignKey,
    Uuid,
)

from app.models.base import Base
from app.models.constant import JobSource, RecruitmentType


class JobItem(Base):
    __tablename__ = "job_item_db"

    id = Column(Uuid, primary_key=True)

    # tracing info
    source = Column(Enum(JobSource))  # from which job platform
    url = Column(String)

    # basic info
    job_title = Column(String)
    update_time = Column(DateTime, nullable=True)
    location = Column(String)  # or a Enum?
    recruitment_type = Column(Enum(RecruitmentType))
    description = Column(Text)  # responsibilities and duties

    # company info
    company_name = Column(String)

    @staticmethod
    def from_scrapy_item(scrapy_job_item: scrapy.Item):
        return JobItem(
            id=scrapy_job_item["id"],
            source=scrapy_job_item["source"],
            url=scrapy_job_item["url"],
            job_title=scrapy_job_item["job_title"],
            update_time=scrapy_job_item["update_time"],
            location=scrapy_job_item["location"],
            recruitment_type=scrapy_job_item["recruitment_type"],
            description=scrapy_job_item["description"],
            company_name=scrapy_job_item["company_name"],
        )
