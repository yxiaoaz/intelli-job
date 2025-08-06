from sqlalchemy import create_engine, URL

DATABASE_URL = "sqlite:///test.db"  # Or your specific database URL
DATABASE_URL = "postgresql+psycopg2://postgres:HelloWorld20010401@localhost:5432/intelli_job_db" # "postgresql+psycopg2://user:password@hostname:port/database_name"
engine = create_engine(DATABASE_URL, echo=True)  # echo=True for logging SQL statements
