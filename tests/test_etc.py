from server.utils.etc import get_hashed, text_decode, text_decode_list, text_encode


def test_get_hashed():
    assert get_hashed("asdf"), "912ec803b2ce49e4a541068d495ab570"
    assert get_hashed("한글"), "52b8c54ab4ea672ee6cdfdfef0a31db4"
    assert get_hashed("한글asdf1234"), "23e073628acf22bd5176c82c7c9cce64"


def test_text_encode():
    assert text_encode("asdf"), "YXNkZg=="
    assert text_encode("한글"), "JUVEJTk1JTlDJUVBJUI4JTgw"
    assert text_encode("한글asdf1234"), "JUVEJTk1JTlDJUVBJUI4JTgwYXNkZjEyMzQ="
    assert text_encode(b"asdf"), "YXNkZg=="
    assert text_encode(b"asdf1234"), "YXNkZjEyMzQ="


def test_text_decode():
    assert text_decode("YXNkZg=="), "asdf"
    assert text_decode("JUVEJTk1JTlDJUVBJUI4JTgw"), "한글"
    assert text_decode("JUVEJTk1JTlDJUVBJUI4JTgwYXNkZjEyMzQ="), "한글asdf1234"
    assert text_decode("YXNkZg=="), "asdf"
    assert text_decode("YXNkZjEyMzQ="), "asdf1234"


def test_text_decode_list():
    l = ["YXNkZg==", "JUVEJTk1JTlDJUVBJUI4JTgw", "JUVEJTk1JTlDJUVBJUI4JTgwYXNkZjEyMzQ=", "YXNkZg==", "YXNkZjEyMzQ="]
    expected = ["asdf", "한글", "한글asdf1234", "asdf", "asdf1234"]

    assert expected == text_decode_list(l)
