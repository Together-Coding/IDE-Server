import base64
import hashlib
import socket
from urllib.parse import quote, unquote


def get_server_ident():
    return "S-" + get_hostname()


def get_hostname():
    return socket.gethostname()


def get_hashed(name: str) -> str:
    _md5 = hashlib.md5()
    _md5.update(name.encode())
    return _md5.hexdigest()


def text_encode(v: str | bytes) -> str:
    if type(v) in [str, bytes]:
        return base64.b64encode(quote(v).encode()).decode()

    raise TypeError("`v` must be str or bytes type.")


def text_decode(v: str | bytes) -> str:
    if type(v) == str:
        return unquote(base64.b64decode(v.encode()))
    elif type(v) == bytes:
        return unquote(base64.b64decode(v))

    raise TypeError("`v` must be str or bytes type.")


def text_decode_list(l: list[str | bytes]) -> list[str]:
    return [text_decode(item) for item in l]
