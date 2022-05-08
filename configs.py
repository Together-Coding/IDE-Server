from pydantic import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    SQLALCHEMY_DATABASE_URL: str = ""

    REDIS_URL: str = ""
    REDIS_DB: int = 0


settings = Settings()
