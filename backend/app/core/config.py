import os
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file at project root or backend dir
load_dotenv()

class Settings(BaseSettings):
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "project_atlas")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    @property
    def database_url(self) -> str:
        """Construct the SQLAlchemy connection URL with safely encoded password."""
        encoded_password = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{self.DB_USER}:{encoded_password}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def safe_database_url(self) -> str:
        """Return database URL with password masked for safe logging and output."""
        return (
            f"mysql+pymysql://{self.DB_USER}:****@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
