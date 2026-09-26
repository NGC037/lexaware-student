"""Standalone poller for the PostgreSQL provenance outbox."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.provenance.service import claim_anchor, process_anchor

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    while True:
        if not settings.blockchain_enabled:
            await asyncio.sleep(settings.provenance_worker_poll_seconds)
            continue
        async with AsyncSessionLocal() as session:
            anchor_id = await claim_anchor(session)
            if anchor_id is not None:
                state = await process_anchor(session, anchor_id)
                logger.info("provenance_job_finished state=%s", state)
                continue
        await asyncio.sleep(settings.provenance_worker_poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("provenance_worker_stopped")
