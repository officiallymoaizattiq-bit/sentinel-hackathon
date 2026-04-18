from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

from sentinel import auth


@pytest.fixture
def db(monkeypatch):
    client = AsyncMongoMockClient()
    db = client["sentinel_test"]
    monkeypatch.setattr(auth, "get_db", lambda: db)
    return db


def test_issue_and_decode_round_trip():
    token = auth.issue_device_token(device_id="d1", patient_id="p1")
    payload = auth._decode_token(token)
    assert payload["sub"] == "d1"
    assert payload["pid"] == "p1"
    assert payload["typ"] == "device"


def test_decode_tampered_signature_rejected():
    token = auth.issue_device_token(device_id="d1", patient_id="p1")
    head, pay, _sig = token.split(".")
    tampered = f"{head}.{pay}.invalidsig"
    with pytest.raises(HTTPException) as e:
        auth._decode_token(tampered)
    assert e.value.status_code == 401


def test_decode_malformed_rejected():
    with pytest.raises(HTTPException) as e:
        auth._decode_token("not.a.valid.jwt.format")
    assert e.value.status_code == 401


def test_decode_wrong_type_rejected(monkeypatch):
    import json
    from base64 import urlsafe_b64encode
    import hmac, hashlib
    from sentinel.config import get_settings
    secret = get_settings().device_token_secret.encode()
    header = urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = urlsafe_b64encode(json.dumps({"sub": "d1", "typ": "admin"}).encode()).rstrip(b"=").decode()
    sig = urlsafe_b64encode(
        hmac.new(secret, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    token = f"{header}.{payload}.{sig}"
    with pytest.raises(HTTPException) as e:
        auth._decode_token(token)
    assert e.value.status_code == 401


async def test_require_device_token_happy_path(db, monkeypatch):
    token = auth.issue_device_token(device_id="d1", patient_id="p1")
    await db.devices.insert_one({
        "_id": "d1", "patient_id": "p1", "token_hash": "x",
        "created_at": datetime.now(tz=timezone.utc),
        "revoked_at": None,
    })
    payload = await auth.require_device_token(authorization=f"Bearer {token}")
    assert payload["sub"] == "d1"
    # last_seen updated
    d = await db.devices.find_one({"_id": "d1"})
    assert d["last_seen_at"] is not None


async def test_require_device_token_revoked_rejected(db):
    token = auth.issue_device_token(device_id="d1", patient_id="p1")
    await db.devices.insert_one({
        "_id": "d1", "patient_id": "p1", "token_hash": "x",
        "created_at": datetime.now(tz=timezone.utc),
        "revoked_at": datetime.now(tz=timezone.utc),
    })
    with pytest.raises(HTTPException) as e:
        await auth.require_device_token(authorization=f"Bearer {token}")
    assert e.value.status_code == 401
    assert e.value.detail["error"] == "device_revoked"


async def test_require_device_token_unknown_device_rejected(db):
    token = auth.issue_device_token(device_id="ghost", patient_id="p1")
    with pytest.raises(HTTPException) as e:
        await auth.require_device_token(authorization=f"Bearer {token}")
    assert e.value.status_code == 401


async def test_require_device_token_non_bearer_rejected(db):
    with pytest.raises(HTTPException) as e:
        await auth.require_device_token(authorization="Basic abc")
    assert e.value.status_code == 401


async def test_require_device_token_models_validate():
    """Sanity: Vital/Device/PairingCode/ProcessedBatch models roundtrip."""
    from sentinel.models import Vital, Device, DeviceInfo, PairingCode, ProcessedBatch
    now = datetime.now(tz=timezone.utc)

    v = Vital(t=now, patient_id="p1", device_id="d1", kind="heart_rate",
              value=72.0, unit="bpm", source="apple_healthkit", confidence=0.9)
    Vital.model_validate(v.model_dump(mode="json"))

    d = Device(_id="d1", patient_id="p1", token_hash="x",
               device_info=DeviceInfo(model="iPhone 15", os="iOS 18", app_version="0.1.0"),
               created_at=now)
    Device.model_validate(d.model_dump(mode="json"))

    pc = PairingCode(_id="123456", patient_id="p1", expires_at=now)
    PairingCode.model_validate(pc.model_dump(mode="json"))

    pb = ProcessedBatch(_id="batch-uuid", patient_id="p1", device_id="d1",
                        processed_at=now, accepted_count=10)
    ProcessedBatch.model_validate(pb.model_dump(mode="json"))
