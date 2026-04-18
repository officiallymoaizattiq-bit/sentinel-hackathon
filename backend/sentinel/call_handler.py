from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from twilio.twiml.voice_response import Gather, VoiceResponse

from sentinel.config import get_settings
from sentinel.db import get_db


def build_check_in_twiml(*, patient_name: str, action_url: str) -> str:
    resp = VoiceResponse()
    resp.say(
        f"Hi {patient_name}, this is Sentinel, your post-op check-in. "
        "After the beep, please describe how you're feeling today. "
        "Any shortness of breath, fever, confusion, or worsening pain?"
    )
    g = Gather(
        input="speech",
        speech_timeout="auto",
        action=action_url,
        method="POST",
        timeout=10,
    )
    resp.append(g)
    resp.say("We didn't catch that — a nurse will follow up.")
    return str(resp)


def _twilio_create_call(**kwargs):
    from twilio.rest import Client
    s = get_settings()
    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    return client.calls.create(**kwargs)


async def place_call(patient_id: str) -> str:
    db = get_db()
    patient = await db.patients.find_one({"_id": patient_id})
    if patient is None:
        raise LookupError(patient_id)
    s = get_settings()

    if s.demo_mode and not s.twilio_account_sid.startswith("AC"):
        return await _demo_stub_call(patient_id)

    base = s.public_base_url.rstrip("/")
    ws_url = base.replace("http", "ws", 1) + "/api/ws/twilio"
    twiml = f"""
<Response>
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="patient_id" value="{patient_id}"/>
    </Stream>
  </Connect>
</Response>
""".strip()

    result = _twilio_create_call(
        to=patient["phone"], from_=s.twilio_from_number, twiml=twiml,
    )
    return result.sid


async def _demo_stub_call(patient_id: str) -> str:
    call_id = str(uuid4())
    await get_db().calls.insert_one({
        "_id": call_id,
        "patient_id": patient_id,
        "called_at": datetime.now(tz=timezone.utc),
        "duration_s": 0.0,
        "transcript": [],
        "audio_features": {}, "baseline_drift": {},
        "score": None, "similar_calls": [], "embedding": [],
        "llm_degraded": False, "audio_degraded": True, "short_call": True,
    })
    return call_id


def _ulaw_to_pcm(ulaw: bytes) -> bytes:
    import audioop
    return audioop.ulaw2lin(ulaw, 2)


async def run_convo_bridge(
    *, patient_id_getter, inbound_queue, send_to_twilio,
) -> str | None:
    """Receive μ-law audio from Twilio, buffer it, score after call ends.

    NOTE: Real ElevenLabs Conversational AI integration is deferred to the
    live-smoke-test step (Task 19). For now this captures audio and runs
    the scoring pipeline on whatever we received.
    """
    import io
    import numpy as np
    import soundfile as sf

    from sentinel.audio_features import extract_features, zscore_drift
    from sentinel.models import AudioFeatures, TranscriptTurn
    from sentinel.scoring import GeminiLLM, score_call

    pcm_buf = bytearray()
    try:
        while True:
            chunk = await inbound_queue.get()
            if chunk is None:
                break
            pcm_buf.extend(_ulaw_to_pcm(chunk))
    except Exception:
        pass

    pid = patient_id_getter()
    if pid is None:
        return None

    if len(pcm_buf) < 8000:  # <1 sec of audio — nothing worth scoring
        return await _demo_stub_call(pid)

    arr = np.frombuffer(bytes(pcm_buf), dtype="<i2").astype("float32") / 32768.0
    tmp_path = f"/tmp/{uuid4()}.wav"
    sf.write(tmp_path, arr, 8000, subtype="PCM_16")

    features = extract_features(tmp_path)
    baseline = await _baseline_features(pid)
    drift = zscore_drift(current=features, baseline=baseline, stdev=None)

    return await score_call(
        patient_id=pid,
        transcript=[],  # Real transcript comes from EL integration in Task 19.
        features=features,
        drift=drift,
        llm=GeminiLLM(),
    )


async def _baseline_features(patient_id: str):
    from sentinel.models import AudioFeatures
    first = await (
        get_db()
        .calls.find({"patient_id": patient_id})
        .sort("called_at", 1)
        .limit(1)
        .to_list(1)
    )
    if first and first[0].get("audio_features"):
        return AudioFeatures(**first[0]["audio_features"])
    return AudioFeatures()
