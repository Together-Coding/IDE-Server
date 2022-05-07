import importlib

import aioredis
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

from configs import settings
from server import models, routers

app = FastAPI()

origins = ["https://together-coding.com"]
if settings.DEBUG:
    origins.extend(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["Authorization"]
)

for router_mod in routers.__all__:
    router = importlib.import_module(f".routers.{router_mod}", package=__name__)
    app.include_router(router.router)


for model_mod in models.__all__:
    model = importlib.import_module(f".models.{model_mod}", package=__name__)


@app.on_event("startup")
async def startup():
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    FastAPICache.init(RedisBackend(redis), prefix="ide-server")
