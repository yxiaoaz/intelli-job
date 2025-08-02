from sqlalchemy import Boolean, Column, Enum, JSON, Text, Time, String, ForeignKey, Uuid

from app.models.base import Base
from app.models.constant import JobSource, RecruitmentType

class JobItem(Base):
    __tablename__ = 'job_item_db'

    id = Column(Uuid, primary_key=True)

    # tracing info
    source = Column(Enum(JobSource))  # from which job platform
    url = Column(String)
    
    # basic info
    job_title = Column(String)
    update_time = Column(Time, nullable=True)
    location = Column(String) # or a Enum?
    recruitment_type = Column(Enum(RecruitmentType))
    description = Column(Text) # responsibilities and duties

    # company info
    company_name = Column(String)



