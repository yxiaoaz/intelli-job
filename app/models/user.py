from app.models.base import Base
from sqlalchemy import Boolean, Column, JSON, Text, String, ForeignKey, Uuid


class User(Base):
    __tablename__ = "user_db"

    id = Column(Uuid, primary_key=True)

    # login-info
    username = Column(String(32), nullable=True, default="none")
    password = Column(String(32), nullable=True, default="none")


class Resume(Base):
    __tablename__ = "resume_db"

    id = Column(Uuid, primary_key=True)

    user_id = Column(Uuid, ForeignKey("user_db.id"))

    active_status = Column(
        Boolean, default=True
    )  # there can be multiple active resumes
    resume_name = Column(String(32), default="my resume")
    source_file_blob = Column(Text)
    extracted_content = Column(JSON)


class UserQueryPreference(Base):
    __tablename__ = "user_query_db"

    id = Column(Uuid, primary_key=True)

    user_id = Column(Uuid, ForeignKey("user_db.id"))
    intended_company = Column(JSON, default=[])
    intended_company_type = Column(JSON, default=[])
    intended_location = Column(JSON, default=[])
    intended_industry = Column(JSON, default=[])
    intended_position = Column(JSON, default=[])
    job_type = Column(JSON, default=[])
