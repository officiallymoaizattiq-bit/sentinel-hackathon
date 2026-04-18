from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from sentinel.db import get_db

log = logging.getLogger("sentinel.scheduler")


async def trigger_call(patient_id: str) -> None:
    # Late import to avoid circular dep with call_handler.
    from sentinel.call_handler import place_call
    await place_call(patient_id)


async def tick() -> None:
    now = datetime.now(tz=timezone.utc)
    cur = get_db().patients.find({"next_call_at": {"$lte": now}})
    async for p in cur:
        try:
            await trigger_call(p["_id"])
        except Exception:
            log.exception("trigger_call failed for %s", p["_id"])


_sched: AsyncIOScheduler | None = None


def start() -> AsyncIOScheduler:
    global _sched
    if _sched is not None:
        return _sched
    _sched = AsyncIOScheduler()
    _sched.add_job(
        lambda: asyncio.create_task(tick()),
        trigger="interval",
        seconds=60,
        id="sentinel_tick",
        replace_existing=True,
    )
    _sched.start()
    return _sched


def stop() -> None:
    global _sched
    if _sched is not None:
        _sched.shutdown(wait=False)
        _sched = None
