from __future__ import annotations

import socket
import struct

from app.core.config import get_settings


class ClamAVScanner:
    """Submit bounded in-memory bytes to clamd using its INSTREAM protocol."""

    _CHUNK_BYTES = 64 * 1024
    _MAX_RESPONSE_BYTES = 4096

    def scan(self, data: bytes) -> str:
        settings = get_settings()
        try:
            with socket.create_connection(
                (settings.clamav_host, settings.clamav_port),
                timeout=settings.clamav_timeout_seconds,
            ) as connection:
                connection.settimeout(settings.clamav_timeout_seconds)
                connection.sendall(b"zINSTREAM\0")
                for offset in range(0, len(data), self._CHUNK_BYTES):
                    chunk = data[offset : offset + self._CHUNK_BYTES]
                    connection.sendall(struct.pack(">I", len(chunk)))
                    connection.sendall(chunk)
                connection.sendall(struct.pack(">I", 0))
                response = bytearray()
                while len(response) < self._MAX_RESPONSE_BYTES:
                    chunk = connection.recv(512)
                    if not chunk:
                        break
                    response.extend(chunk)
                    if b"\0" in response or b"\n" in response:
                        break
        except OSError, TimeoutError:
            return "unavailable"

        # Never expose daemon diagnostics. Only exact documented verdicts are trusted.
        verdict = bytes(response).rstrip(b"\0\r\n")
        if b":" not in verdict:
            return "error"
        stream_name, result = verdict.split(b":", maxsplit=1)
        if stream_name.strip() != b"stream":
            return "error"
        result = result.strip()
        if result == b"OK":
            return "clean"
        if result.endswith(b" FOUND") and result.removesuffix(b" FOUND").strip():
            return "infected"
        return "error"
