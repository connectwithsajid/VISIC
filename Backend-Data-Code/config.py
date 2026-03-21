# config.py
import os
from dotenv import load_dotenv

# This loads variables from .env into environment
load_dotenv()

class Settings:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    BASE_URL= os.getenv("BASE_URL")
    PAGE_URL= os.getenv("PAGE_URL")
    USER_AGENT = os.getenv("USER_AGENT")

    @property
    def DATABASE_URL(self):
        return (
            f"postgresql+psycopg2://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

settings = Settings()

#print("DATABASE URL:", settings.DATABASE_URL) 