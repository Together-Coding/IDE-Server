# IDE server

# API Document
- http://localhost:8001/docs

# Requirements
- Python 3.10.0

# Installation
1. `.env` 파일을 생성합니다.
1. `$ pip install -r requirements.txt`

# Development
- Start server
    1. `$ export $(cat .env | grep -v "#" | xargs)`
    1. `$ DEBUG=true uvicorn app:app --port 8001 --reload`