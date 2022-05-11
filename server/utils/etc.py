import hashlib


def get_hashed(name: str):
    _md5 = hashlib.md5()
    _md5.update(name.encode())
    return _md5.hexdigest()
