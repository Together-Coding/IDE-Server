import importlib

import aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

from configs import settings
from server import models, routers, websockets
from server.helpers.sentry import init_sentry
from server.websockets import create_websocket

if settings.DEBUG:
    cors_allow_origins = "*"
else:
    cors_allow_origins = ["https://together-coding.com"]


app = FastAPI()
init_sentry(app)
sio, sio_app = create_websocket(app, cors_allow_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization"],
)

for router_mod in routers.__all__:
    router = importlib.import_module(f".routers.{router_mod}", package=__name__)
    app.include_router(router.router)


for model_mod in models.__all__:
    model = importlib.import_module(f".models.{model_mod}", package=__name__)

for ws_mod in websockets.__all__:
    ws = importlib.import_module(f".websockets.{ws_mod}", package=__name__)


@app.on_event("startup")
async def startup():
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    FastAPICache.init(RedisBackend(redis), prefix="ide-server")
