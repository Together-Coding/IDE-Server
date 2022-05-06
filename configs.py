import os
from typing import Union

from pydantic import BaseSettings


class GlobalSettings(BaseSettings):
    DEBUG: bool = False


global_settings = GlobalSettings()


class Settings(BaseSettings):
    SQLALCHEMY_DATABASE_URL: str = ""
    pass


settings = Settings()
