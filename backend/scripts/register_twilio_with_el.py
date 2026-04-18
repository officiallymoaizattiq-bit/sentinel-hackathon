"""One-off: register a Twilio phone number with ElevenLabs so the
agent can place outbound calls from it.

Run once after buying a Twilio number:

    cd backend && source .venv/bin/activate
    python scripts/register_twilio_with_el.py +15551234567 "Sentinel Line"

Writes the returned phone_number_id to /tmp/el_phone_number_id.txt.
Put that ID into the ELEVENLABS_PHONE_NUMBER_ID env var.
"""
import os
import sys

from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.phone_numbers.types.phone_numbers_create_request_body import (
    PhoneNumbersCreateRequestBody_Twilio,
)


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: register_twilio_with_el.py <+E164> <label>")
        sys.exit(2)
    phone, label = sys.argv[1], sys.argv[2]

    el = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    resp = el.conversational_ai.phone_numbers.create(
        request=PhoneNumbersCreateRequestBody_Twilio(
            provider="twilio",
            phone_number=phone,
            label=label,
            sid=os.environ["TWILIO_ACCOUNT_SID"],
            token=os.environ["TWILIO_AUTH_TOKEN"],
        )
    )
    pid = getattr(resp, "phone_number_id", None) or getattr(resp, "id", None)
    print(f"phone_number_id: {pid}")
    with open("/tmp/el_phone_number_id.txt", "w") as fh:
        fh.write(str(pid))


if __name__ == "__main__":
    main()
