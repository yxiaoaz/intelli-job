import uuid

from typing import Union, Any, Dict, List

from sqlalchemy import insert, select, and_, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from app.models.job import JobItem
from app.models.constant import RecruitmentType


class DBController:
    def __init__(self, engine: Engine):
        self.session_maker = sessionmaker(bind=engine)

    def insert_job_item(
        self, session: Session, job_item: Union[JobItem, List[JobItem]]
    ):
        if (
            isinstance(job_item, List)
            and len(job_item) > 0
            and all([isinstance(j, JobItem) for j in job_item])
        ):
            if len(job_item) > 10:
                # if number of job items exceeds 10, use bulk insert
                session.execute(insert(JobItem), [j.to_dict() for j in job_item])
            else:
                session.add_all(job_item)
        elif isinstance(job_item, JobItem):
            session.add(job_item)

    def update_job_item_embedding_status_bulk(
        self, session: Session, job_item_ids: List[uuid], status: bool
    ):
        """
        Update the embedding_generated status of multiple job items in bulk.
        """
        session.execute(
            update(JobItem),
            [
                {"id": job_item_id, "embedding_generated": status}
                for job_item_id in job_item_ids
            ],
        )

    def filter_job_item_recruitment_type(
        self, session: Session, recruitment_type: List[RecruitmentType]
    ) -> List[JobItem]:
        """
        Filter job items by recruitment type.
        """
        if not isinstance(recruitment_type, list):
            raise TypeError(
                f"`recruitment_type` parameter should be a list of `RecruitmentType`, but got {type(recruitment_type)}."
            )

        query = select(JobItem).where(
            and_(
                JobItem.recruitment_type.in_(recruitment_type),
                JobItem.embedding_generated.is_(True),
            )
        )

        return session.execute(query).scalars().all()
