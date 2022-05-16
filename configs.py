from pydantic import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    SENTRY_DSN: str = ""
    SQLALCHEMY_DATABASE_URL: str = ""

    REDIS_URL: str = ""
    REDIS_DB: int = 0

    S3_BUCKET: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
