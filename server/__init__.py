import importlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from configs import global_settings
from server import routers, models

app = FastAPI()

origins = ["https://together-coding.com"]
if global_settings.DEBUG:
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
