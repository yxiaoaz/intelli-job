import os

from dotenv import load_dotenv

from sqlalchemy import create_engine, URL

from app.config import get_project_root

# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))

url_object = URL.create(
    os.getenv("RDS_DRIVERNAME"),
    username=os.getenv("RDS_USERNAME"),
    password=os.getenv("RDS_PASSWORD"),  # plain (unescaped) text
    host=os.getenv("RDS_HOST"),
    database=os.getenv("RDS_DB_NAME"),
)

engine = create_engine(url_object, echo=True)  # echo=True for logging SQL statements


