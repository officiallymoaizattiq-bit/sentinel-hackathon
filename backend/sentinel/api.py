from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from twilio.twiml.voice_response import VoiceResponse as TwilioVoiceResponse

from sentinel import enrollment
from sentinel.call_handler import build_check_in_twiml, run_convo_bridge
from sentinel.db import get_db
from sentinel.models import Caregiver, Consent, SurgeryType

router = APIRouter(prefix="/api")


class EnrollRequest(BaseModel):
    name: str
    phone: str
    language: str = "en"
    surgery_type: SurgeryType
    surgery_date: datetime
    discharge_date: datetime
    caregiver: Caregiver
    consent: Consent | None = None


@router.post("/patients", status_code=201)
async def enroll(body: EnrollRequest):
    try:
        pid = await enrollment.enroll_patient(
            name=body.name,
            phone=body.phone,
            language=body.language,
            surgery_type=body.surgery_type,
            surgery_date=body.surgery_date,
            discharge_date=body.discharge_date,
            caregiver=body.caregiver,
            consent=body.consent,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": pid}


@router.get("/patients")
async def list_patients():
    docs = [d async for d in get_db().patients.find({})]
    return [
        {
            "id": d["_id"],
            "name": d["name"],
            "surgery_type": d["surgery_type"],
            "next_call_at": d.get("next_call_at"),
            "call_count": d.get("call_count", 0),
        }
        for d in docs
    ]


@router.get("/patients/{pid}/calls")
async def patient_calls(pid: str):
    cur = (
        get_db()
        .calls.find({"patient_id": pid})
        .sort("called_at", 1)
    )
    return [
        {
            "id": d["_id"],
            "called_at": d["called_at"],
            "score": d.get("score"),
            "similar_calls": d.get("similar_calls", []),
            "short_call": d.get("short_call", False),
            "llm_degraded": d.get("llm_degraded", False),
        }
        async for d in cur
    ]


@router.get("/alerts")
async def list_alerts():
    cur = get_db().alerts.find({}).sort("sent_at", -1).limit(50)
    return [
        {
            "id": d["_id"],
            "patient_id": d["patient_id"],
            "call_id": d["call_id"],
            "severity": d["severity"],
            "channel": d["channel"],
            "sent_at": d["sent_at"],
        }
        async for d in cur
    ]


@router.get("/calls/twiml")
async def twiml_for_call(patient_id: str):
    patient = await get_db().patients.find_one({"_id": patient_id})
    name = (patient or {}).get("name", "there")
    xml = build_check_in_twiml(
        patient_name=name,
        action_url=f"/api/calls/gather?patient_id={patient_id}",
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/calls/gather")
async def twiml_gather(patient_id: str, SpeechResult: str = Form("")):
    from uuid import uuid4
    call_id = str(uuid4())
    await get_db().calls.insert_one({
        "_id": call_id,
        "patient_id": patient_id,
        "called_at": datetime.utcnow(),
        "transcript": [
            {"role": "patient", "text": SpeechResult,
             "t_start": 0.0, "t_end": 10.0}
        ],
        "score": None, "similar_calls": [], "embedding": [],
        "audio_features": {}, "baseline_drift": {},
        "llm_degraded": False, "audio_degraded": True, "short_call": True,
    })
    resp = TwilioVoiceResponse()
    resp.say("Thank you. A nurse will review your check-in. Goodbye.")
    return Response(content=str(resp), media_type="application/xml")


@router.websocket("/ws/twilio")
async def twilio_media_stream(ws: WebSocket):
    await ws.accept()
    patient_id: str | None = None
    stream_sid: str | None = None
    inbound_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def reader():
        nonlocal stream_sid, patient_id
        try:
            while True:
                msg = await ws.receive_text()
                data = json.loads(msg)
                ev = data.get("event")
                if ev == "start":
                    stream_sid = data["start"]["streamSid"]
                    patient_id = (
                        data["start"].get("customParameters", {}).get("patient_id")
                    )
                elif ev == "media":
                    payload = data["media"]["payload"]
                    await inbound_queue.put(base64.b64decode(payload))
                elif ev == "stop":
                    await inbound_queue.put(None)
                    break
        except WebSocketDisconnect:
            await inbound_queue.put(None)

    async def writer(audio_bytes: bytes) -> None:
        if stream_sid is None:
            return
        await ws.send_text(json.dumps({
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": base64.b64encode(audio_bytes).decode()},
        }))

    reader_task = asyncio.create_task(reader())
    try:
        await run_convo_bridge(
            patient_id_getter=lambda: patient_id,
            inbound_queue=inbound_queue,
            send_to_twilio=writer,
        )
    finally:
        reader_task.cancel()
