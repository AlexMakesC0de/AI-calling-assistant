import logging

from flask import Blueprint, jsonify, request

from auth import require_auth
from events import save_event
from recordings import forward_to_voice_app, resolve_recording_path

logger = logging.getLogger(__name__)

bp = Blueprint("telephony", __name__)


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@bp.route("/webhooks/recording-complete", methods=["POST"])
def recording_complete():
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        event_file = save_event(payload)
        recording_path = resolve_recording_path(payload)
        pipeline_result = forward_to_voice_app(payload, recording_path)

        # Cleanup temporary downloads only; keep explicit local recording_path untouched.
        if payload.get("recording_url") and recording_path.exists():
            recording_path.unlink(missing_ok=True)

        return jsonify(
            {
                "status": "processed",
                "event_file": str(event_file),
                "voice_app": pipeline_result,
            }
        ), 200
    except Exception as exc:
        logger.exception("Failed to process telephony recording event")
        return jsonify({"status": "failed", "error": str(exc)}), 502


@bp.route("/webhooks/example-payload", methods=["GET"])
def example_payload():
    return jsonify(
        {
            "provider": "pbx",
            "event_id": "evt-123",
            "call_id": "call-abc",
            "source_number": "+31-10-0000000",
            "destination_number": "+31-10-1111111",
            "caller_id": "+31-6-12345678",
            "answered": True,
            "recording_url": "https://example.invalid/recordings/call-abc.wav",
            "recording_path": "/data/shared/uploads/test_call.wav",
            "started_at": "2026-03-26T09:00:00Z",
            "ended_at": "2026-03-26T09:03:20Z",
        }
    ), 200
