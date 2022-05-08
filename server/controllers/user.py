import json

import requests

from constants.common import API_HEADER, API_URL
from server.controllers.base import BaseContoller


class AuthController(BaseContoller):
    @staticmethod
    def verify_token(token: str) -> bool | dict:
        """Verify the given JWT token by asking to API server. Return True if verified, otherwise, False"""
        if not token:
            return False

        payload = {"token": token}
        resp = requests.post(API_URL + "/auth/token", json=payload, headers=API_HEADER)

        if resp.ok:
            try:
                data = resp.json()
                return data
            except json.JSONDecodeError:
                return False
        else:
            return False
