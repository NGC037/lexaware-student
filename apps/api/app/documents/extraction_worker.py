from __future__ import annotations

import json
import sys

from app.core.config import get_settings
from app.documents.analysis import extract_pdf


def main() -> int:
    max_bytes = get_settings().document_max_upload_bytes
    data = sys.stdin.buffer.read(max_bytes + 1)
    if len(data) > max_bytes:
        return 2
    try:
        result = extract_pdf(data)
    except Exception:
        return 1
    output = json.dumps(
        {
            "pages": [
                {"page_number": page.page_number, "text": page.text} for page in result.pages
            ],
            "quality": result.quality,
            "needs_ocr": result.needs_ocr,
            "warnings": list(result.warnings),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    sys.stdout.buffer.write(output.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
