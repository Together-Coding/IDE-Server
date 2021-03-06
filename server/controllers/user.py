import json

import requests

from constants.common import API_HEADER, API_URL
from server.controllers.base import BaseController


class AuthController(BaseController):
    @staticmethod
    def verify_token(token: str) -> tuple[bool, dict]:
        """Verify the given JWT token by asking API server. Return True if verified, otherwise, False"""

        if not token:
            return False, {"error": "Empty token is not allowed."}

        payload = {"token": token}
        resp = requests.post(API_URL + "/auth/token", json=payload, headers=API_HEADER)

        success = False
        try:
            data = resp.json()
            success = resp.ok and data.get('valid') is True
        except json.JSONDecodeError:
            data = {"error": "Unknown error"}

        return success, data
