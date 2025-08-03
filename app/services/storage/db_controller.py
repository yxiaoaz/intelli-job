
import uuid

from typing import Union, Any, Dict, List

from sqlalchemy import insert, select, and_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from app.models.base import Base
from app.models.user import User, Resume, UserQueryPreference
from app.models.job import JobItem



class DBController:
    def __init__(self, engine: Engine):
        self.session_maker = sessionmaker(bind=engine)

    def insert_user(self, session: Session, user: Union[User, List[User]]):
        if isinstance(user, List):
            session.add_all(user)
        elif isinstance(user, User):
            session.add(user)
        else:
            raise TypeError(f"`user` parameter only supports a `User` or `List[User]` instance, but a type `{type(user)}` is passed in.")

    def get_user_by_uuid(self, session: Session, user_id: uuid):
        return session.scalars(
            select(User).where(User.id==user_id)
        ).one()


    def insert_resume(self, session: Session, resume: Resume):
        session.add(resume, Resume)
    
    def insert_user_query_pref(self, session: Session, user_preference: UserQueryPreference):
        session.add(user_preference, UserQueryPreference)

    def get_active_resume(self, session: Session, user_id: uuid):
        return session.scalars(
            select(Resume).where(
                and_(Resume.user_id == user_id, 
                     Resume.active_status == True)
                )
        ).all()
    

    def insert_job_item(self, session: Session, job_item: JobItem):
        session.add(job_item, JobItem)

    
    
    
