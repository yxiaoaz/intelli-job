from sqlalchemy import create_engine

DATABASE_URL =  "sqlite:///test.db"  # Or your specific database URL
engine = create_engine(DATABASE_URL, echo=True) # echo=True for logging SQL statements