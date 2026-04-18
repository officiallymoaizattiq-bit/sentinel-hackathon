from datetime import datetime, timedelta, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

from sentinel import scheduler, enrollment


@pytest.fixture
def db(monkeypatch):
    client = AsyncMongoMockClient()
    db = client["sentinel_test"]
    monkeypatch.setattr(scheduler, "get_db", lambda: db)
    monkeypatch.setattr(enrollment, "get_db", lambda: db)
    return db


async def test_tick_triggers_due_and_only_due(db, monkeypatch):
    now = datetime.now(tz=timezone.utc)
    await db.patients.insert_many([
        {"_id": "due1", "next_call_at": now - timedelta(minutes=1),
         "call_count": 0, "caregiver": {"phone": "+1"}},
        {"_id": "future", "next_call_at": now + timedelta(hours=1),
         "call_count": 0, "caregiver": {"phone": "+1"}},
    ])
    called: list[str] = []

    async def fake_trigger(patient_id: str) -> None:
        called.append(patient_id)

    monkeypatch.setattr(scheduler, "trigger_call", fake_trigger)
    await scheduler.tick()
    assert called == ["due1"]
