import json
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
from app.models.constant import JobSource, RecruitmentType, AcademicQualification


class JobItem(Base):
    __tablename__ = "job_item_db"

    id = Column(Uuid, primary_key=True)

    # tracing info
    source = Column(Enum(JobSource))  # from which job platform
    url = Column(String)

    # embedding info
    embedding_generated = Column(Boolean, default=False)

    # basic info
    job_title = Column(String)
    update_time = Column(DateTime, nullable=True)
    location = Column(String)  # or a Enum?
    recruitment_type = Column(Enum(RecruitmentType))
    min_academic_qualification = Column(Enum(AcademicQualification), default = AcademicQualification.ALL)
    salary = Column(String, default = "NA")
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
            min_academic_qualification = scrapy_job_item["min_academic_qualification"],
            salary = scrapy_job_item["salary"],
            description=scrapy_job_item["description"],
            company_name=scrapy_job_item["company_name"],
        )

    def __str__(self):
        return json.dumps({"岗位名称":self.job_title, "公司名称": self.company_name, "工作描述":self.description}, ensure_ascii=False, )

    def to_dict(self):
        return {
            "id":self.id,
            "source":self.source, 
            "url":self.url,
            "embedding_generated":self.embedding_generated,
            "job_title":self.job_title,
            "update_time":self.update_time,
            "location":self.location,
            "recruitment_type":self.recruitment_type,
            "min_academic_qualification": self.min_academic_qualification,
            "salary": self.salary,
            "description":self.description,
            "company_name":self.company_name,
        }