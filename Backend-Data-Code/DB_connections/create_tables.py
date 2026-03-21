# create_tables.py
from .db_connection import engine
from .db_schema import Base

def create_all():
    Base.metadata.create_all(bind=engine)
    print("Tables created / verified.")
def main():
    create_all()
if __name__ == "__main__":
    main()