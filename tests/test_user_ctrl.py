from server.controllers.user import AuthController


def test_auth_ctrl():
    EMPTY_RESP =  (False, {"error": "Empty token is not allowed."})
    FAIL_RESP = (False, {"error": "Unknown error"})

    empty_token = ""
    assert AuthController.verify_token(empty_token) == EMPTY_RESP

    invalid_token = "eyJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE2NDkyMzkwMjMsImV4cCI6MTY1MTgzMTAyMywic3ViIjoidHRlc3RAZ21haWwuY29tIn1.Fb0DuUkvKaEYfgqxnDEJInKoKV9fNST4xsxqNv8Zacz"

    assert AuthController.verify_token(invalid_token) == FAIL_RESP

    expired_token = "eyJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE2NDkyMzkwMjMsImV4cCI6MTY1MTgzMTAyMywic3ViIjoidHRlc3RAZ21haWwuY29tIn0.Fb0DuUkvKaEYfgqxnDEJInKoKV9fNST4xsxqNv8ZacU"

    assert AuthController.verify_token(expired_token) == FAIL_RESP
