import importlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from configs import settings
from server import models, routers, websockets
from server.helpers.sentry import init_sentry
from server.websockets import create_websocket
from server.utils import jinja

if settings.DEBUG:
    cors_allow_origins = "*"
else:
    cors_allow_origins = "*"  # ["https://together-coding.com"]


_kwargs = {}
if not settings.DEBUG:
    _kwargs.update({"docs_url": None, "redoc_url": None})

app = FastAPI(**_kwargs)
sio, sio_app = create_websocket(app, cors_allow_origins)

init_sentry(app)
app.mount("/static", StaticFiles(directory="server/static"), name="static")
templates = Jinja2Templates(directory="server/templates")
jinja.register(templates)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "X-API-KEY"],
)

for router_mod in routers.__all__:
    router = importlib.import_module(f".routers.{router_mod}", package=__name__)
    app.include_router(router.router)


for model_mod in models.__all__:
    model = importlib.import_module(f".models.{model_mod}", package=__name__)

for ws_mod in websockets.__all__:
    ws = importlib.import_module(f".websockets.{ws_mod}", package=__name__)
