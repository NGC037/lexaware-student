from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.documents.queue import claim_next_document_job, run_document_job
from app.documents.scanner import ClamAVScanner
from app.documents.storage import S3ObjectStorage

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    """Poll the PostgreSQL job table and process one job at a time per worker."""
    settings = get_settings()
    storage = S3ObjectStorage()
    scanner = ClamAVScanner()
    while True:
        async with AsyncSessionLocal() as session:
            job_id = await claim_next_document_job(session)
            if job_id is not None:
                state = await run_document_job(session, job_id, storage=storage, scanner=scanner)
                logger.info("document_job_finished state=%s", state)
                continue
        await asyncio.sleep(settings.document_worker_poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("document_worker_stopped")
