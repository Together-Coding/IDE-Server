# IDE server

# API Document
- http://localhost:8001/docs

# Requirements
- Python 3.10.0

# Installation
1. `.env` 파일을 생성합니다.
1. `$ pip install -r requirements.txt`

# Development
- SSH tunneling for AWS Elasticache(Redis)
    `$ ssh -i <ssh_pem_key> <EC2_user>@<EC2_IP_address> -f -N -L 6379:<Redis_endpoint>:6379`
- Connect to Redis
    `$ redis-cli`
- Start server
    1. Configure `.env` file.
    1. `$ uvicorn app:app --port 8001 --reload`
- Test
    `$ make test`