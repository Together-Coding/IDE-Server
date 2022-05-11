from fastapi.responses import JSONResponse


def api_response(data: dict = None, status_code: int = 200):
    if not data:
        data = {}
    return JSONResponse(status_code=status_code, content=data)


def ws_error_response(reason: str) -> dict:
    return dict(error=reason)
