import socket
import struct

from app.core.config import get_settings


class MalwareDetectedError(ValueError):
    pass


def scan_bytes(data: bytes) -> None:
    settings = get_settings()
    if not settings.clamav_host:
        return
    with socket.create_connection(
        (settings.clamav_host, settings.clamav_port), timeout=15
    ) as connection:
        connection.sendall(b"zINSTREAM\0")
        for offset in range(0, len(data), 64 * 1024):
            chunk = data[offset : offset + 64 * 1024]
            connection.sendall(struct.pack("!I", len(chunk)) + chunk)
        connection.sendall(struct.pack("!I", 0))
        response = connection.recv(4096).decode("utf-8", errors="replace")
    if "FOUND" in response:
        raise MalwareDetectedError("文件未通过安全扫描")
    if "OK" not in response:
        raise ConnectionError(f"ClamAV 扫描失败: {response.strip()}")
