# db_connection.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings

# Expect env var DATABASE_URL like:
# postgresql+psycopg2://user:password@host:port/dbname
# DATABASE_URL = os.environ.get("DATABASE_URL")
# if not DATABASE_URL:
#     raise RuntimeError("Please set the DATABASE_URL environment variable")

# echo=True for SQL logging during development; set False for production
engine = create_engine(settings.DATABASE_URL, echo=False, future=True)

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)