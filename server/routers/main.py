from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from configs import global_settings, settings
from server.response import api_response

router = APIRouter()


@router.get("/ping")
async def ping():
    return PlainTextResponse("pong")
