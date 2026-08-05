"""Mock partner webhook for the partner-payment-events POC.

Receives GCP PubSub push deliveries, logs the envelope, decodes the message
body, and optionally verifies the GCP-signed OIDC token.

Run:
    python3 -m venv .venv && source .venv/bin/activate
    pip install flask google-auth requests
    python docs/partner-poc-webhook.py

Then expose via ngrok:
    ngrok http 8080
    # copy the https URL into your subscription's --push-endpoint

Query params:
    ?fail=1  -> return 500 (use to exercise DLQ + BigQuery path)
"""

import base64
import json
import logging
import os
import sys

from flask import Flask, request

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

app = Flask(__name__)

# Toggle OIDC verification on/off. Off is fine for pure POC delivery testing;
# turn on to prove the auth path partners will actually implement.
VERIFY_OIDC = os.getenv("VERIFY_OIDC", "false").lower() == "true"
# Expected audience is normally the push endpoint URL, unless overridden with
# --push-auth-token-audience on the subscription. Set to your ngrok https URL.
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE")


def _verify_oidc(auth_header: str | None) -> dict | None:
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    # Import here so google-auth is only required when VERIFY_OIDC=true
    from google.auth.transport import requests as grequests  # noqa: PLC0415
    from google.oauth2 import id_token  # noqa: PLC0415

    return id_token.verify_oauth2_token(token, grequests.Request(), audience=OIDC_AUDIENCE)


@app.post("/")
def receive() -> tuple[str, int]:
    if request.args.get("fail") == "1":
        app.logger.warning("Returning 500 for DLQ test (fail=1)")
        return "forced failure", 500

    if VERIFY_OIDC:
        try:
            claims = _verify_oidc(request.headers.get("Authorization"))
            app.logger.info("OIDC verified: sub=%s email=%s", claims.get("sub"), claims.get("email"))
        except Exception as exc:  # noqa: BLE001
            app.logger.error("OIDC verification failed: %s", exc)
            return "unauthorized", 401

    envelope = request.get_json(silent=True) or {}
    message = envelope.get("message", {})
    attributes = message.get("attributes", {})

    try:
        decoded = base64.b64decode(message.get("data", "")).decode("utf-8")
        payload = json.loads(decoded)
    except Exception:  # noqa: BLE001
        payload = None
        decoded = None

    app.logger.info(
        "PubSub push received\n"
        "  subscription:  %s\n"
        "  message_id:    %s\n"
        "  publish_time:  %s\n"
        "  attributes:    %s\n"
        "  payload:       %s",
        envelope.get("subscription"),
        message.get("messageId"),
        message.get("publishTime"),
        json.dumps(attributes, indent=2, sort_keys=True),
        json.dumps(payload, indent=2) if payload else decoded,
    )
    return "", 204


@app.get("/health")
def health() -> tuple[str, int]:
    return "ok", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)  # noqa: S104
