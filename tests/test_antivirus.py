import pytest

from app.core.config import get_settings
from app.services import antivirus


class FakeClamAVConnection:
    def __init__(self, response: bytes):
        self.response = response
        self.sent = bytearray()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def sendall(self, data: bytes):
        self.sent.extend(data)

    def recv(self, _size: int) -> bytes:
        return self.response


def test_clamav_rejects_detected_file(monkeypatch):
    monkeypatch.setattr(get_settings(), "clamav_host", "clamav")
    connection = FakeClamAVConnection(b"stream: Eicar-Signature FOUND\0")
    monkeypatch.setattr(antivirus.socket, "create_connection", lambda *_args, **_kwargs: connection)
    with pytest.raises(antivirus.MalwareDetectedError):
        antivirus.scan_bytes(b"unsafe")
    assert connection.sent.startswith(b"zINSTREAM\0")
