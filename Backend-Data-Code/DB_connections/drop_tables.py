# DB_connections/drop_tables.py
from .db_connection import engine
from .db_schema import Base

def drop_all():
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped.")

def main():
    drop_all()

if __name__ == "__main__":
    main()