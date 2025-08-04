from app.models.base import Base
from app.models.user import *
from app.models.job import *
from app.services.storage.engine import engine

def init_db():
    Base.metadata.create_all(bind=engine)

