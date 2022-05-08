import uvicorn

from server import sio_app as app

if __name__ == "__main__":
    uvicorn.run(app)
