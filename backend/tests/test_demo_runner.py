import pytest
from mongomock_motor import AsyncMongoMockClient

from sentinel import demo_runner, named_seed, enrollment, replay, scoring, \
                     seed as cohort_seed, escalation


@pytest.fixture
def db(monkeypatch):
    client = AsyncMongoMockClient()
    db = client["sentinel_test"]
    for mod in (named_seed, enrollment, replay, scoring, cohort_seed,
                escalation, demo_runner):
        monkeypatch.setattr(mod, "get_db", lambda d=db: d, raising=False)
    return db


async def test_trajectory_demo_seeds_three_patients_with_three_calls_each(db, monkeypatch, tmp_path):
    # Stub send_alert so demo runner doesn't hit real Twilio.
    async def noop(*a, **k): return None
    monkeypatch.setattr(demo_runner, "send_alert", noop)
    # Point cohort seeding at mock DB
    await cohort_seed.seed_cohort(count=3)

    # Build tiny fake script + WAV so replay_file works.
    demo_dir = tmp_path / "demo"
    scripts = demo_dir / "scripts"
    audio = demo_dir / "audio"
    scripts.mkdir(parents=True)
    audio.mkdir(parents=True)
    for name in ("baseline", "drift", "red"):
        (scripts / f"{name}.txt").write_text("patient 0.0 1.0 hello\n")
    import numpy as np, soundfile as sf
    for name in ("baseline", "drift", "red"):
        sf.write(str(audio / f"{name}.wav"),
                 np.zeros(16000 * 3, dtype="float32"), 16000, subtype="PCM_16")

    pids = await demo_runner.run_trajectory_demo(root=str(demo_dir))
    assert len(pids) == 3

    # Each patient should have 3 scored calls.
    for pid in pids:
        calls = [c async for c in db.calls.find({"patient_id": pid})]
        assert len(calls) == 3
