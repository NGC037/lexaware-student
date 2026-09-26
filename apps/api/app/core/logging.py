"""Application-wide logging configuration.

Configures standard library (text) logging with a consistent format.
This is NOT structured JSON logging; it is human-readable text.
Call ``setup_logging()`` once at application startup.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a consistent format.

    Safe to call multiple times; duplicate handlers are not added.
    No sensitive information (passwords, tokens, document content, PII)
    should ever be passed to the logger by calling code.
    """
    root = logging.getLogger()

    # Guard: do not attach duplicate handlers if already configured.
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(handler)

    # Suppress excessively noisy third-party access logs.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
