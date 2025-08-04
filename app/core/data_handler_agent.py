from app.models.base import Base
from app.services.storage.db_controller import DBController
from app.services.storage.utils import session_scope
from app.services.storage.engine import engine


class DataHandlerAgent:
    def __init__(self):
        self.db_controller = DBController(engine=engine)
