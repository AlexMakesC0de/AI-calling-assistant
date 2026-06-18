"""
Seed the database with test call conversations and generate small test MP3 files.
Uses a minimal valid MP3 frame (silence) repeated to create short audio files.
"""

import os
import struct
import math
import wave
import tempfile
import subprocess
import sys
from pathlib import Path

import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:KLRKfBScdBeOanqetcFSXvYDUNztmVcq@shortline.proxy.rlwy.net:15338/railway",
)

RECORDINGS_DIR = Path(os.getenv(
    "CALL_RECORDINGS_DIR",
    str(Path(__file__).resolve().parent.parent / "local-storage" / "shared" / "call-recordings"),
))


def generate_wav_tone(filepath: Path, duration_s: float = 3.0, freq: float = 440.0, sample_rate: int = 16000):
    """Generate a simple sine-wave WAV file."""
    n_samples = int(sample_rate * duration_s)
    with wave.open(str(filepath), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            sample = int(16000 * math.sin(2 * math.pi * freq * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample))


def generate_test_mp3(filepath: Path, duration_s: float = 3.0, freq: float = 440.0):
    """Generate a test MP3 file. Falls back to WAV if no encoder is available."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Just create a WAV — the audio player in the browser can handle it too,
    # and the dashboard route serves it as audio/mpeg regardless.
    # For a proper demo this is fine.
    wav_path = filepath.with_suffix(".wav")
    generate_wav_tone(wav_path, duration_s, freq)

    # Try to convert to MP3 if ffmpeg is available
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", "64k", str(filepath)],
            capture_output=True, timeout=10,
        )
        if filepath.exists():
            wav_path.unlink(missing_ok=True)
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # No ffmpeg — rename WAV to .mp3 (browser audio element handles it)
    if wav_path.exists():
        wav_path.rename(filepath)
    print(f"  Note: created as WAV (no ffmpeg). Browser will still play it.")


TEST_CONVERSATIONS = [
    {
        "phone": "+31612345678",
        "name": "Jan de Vries",
        "calls": [
            {
                "call_sid": "CA_test_001_aaa",
                "direction": "inbound",
                "status": "completed",
                "duration": 45,
                "recording_sid": "RE_test_001_aaa",
                "transcript": (
                    "Speaker 1: Hi, I'm calling because my internet connection has been down since this morning. "
                    "I've already tried restarting the router but it didn't help.\n"
                    "Speaker 2: I'm sorry to hear that. Can you give me your account number?\n"
                    "Speaker 1: Yes, it's NL-2024-8834.\n"
                    "Speaker 2: Thank you. I can see there's a known outage in your area. "
                    "Our engineers are working on it and it should be resolved within 2 hours.\n"
                    "Speaker 1: Okay, thank you for the information."
                ),
                "freq": 440.0,
            },
            {
                "call_sid": "CA_test_002_aaa",
                "direction": "inbound",
                "status": "completed",
                "duration": 32,
                "recording_sid": "RE_test_002_aaa",
                "transcript": (
                    "Speaker 1: Hello, it's Jan de Vries again. The internet is still not working. "
                    "It's been over 3 hours now.\n"
                    "Speaker 2: Let me check the status. I see the outage has been extended. "
                    "I'll escalate this to priority and have someone call you back within 30 minutes.\n"
                    "Speaker 1: Please do, I need it for work. Thank you."
                ),
                "freq": 523.0,
            },
        ],
    },
    {
        "phone": "+31687654321",
        "name": "Maria Jansen",
        "calls": [
            {
                "call_sid": "CA_test_003_bbb",
                "direction": "inbound",
                "status": "completed",
                "duration": 78,
                "recording_sid": "RE_test_003_bbb",
                "transcript": (
                    "Speaker 1: Good morning. I received my invoice and I think there's an error. "
                    "I'm being charged for a premium package but I only have the basic plan.\n"
                    "Speaker 2: I understand your concern. Let me pull up your account. "
                    "What's the invoice number?\n"
                    "Speaker 1: It's INV-2026-04-1892.\n"
                    "Speaker 2: I can see the issue — there was a system upgrade that incorrectly "
                    "moved some accounts to premium. I'll correct this and issue a credit note "
                    "for the difference of 24.99 euros. You should see it within 5 business days.\n"
                    "Speaker 1: Great, thank you so much for resolving that quickly."
                ),
                "freq": 392.0,
            },
        ],
    },
    {
        "phone": "+31698765432",
        "name": None,
        "calls": [
            {
                "call_sid": "CA_test_004_ccc",
                "direction": "inbound",
                "status": "failed",
                "duration": 5,
                "recording_sid": "RE_test_004_ccc",
                "transcript": None,
                "error_message": "Recording download failed: Connection timeout",
                "freq": 330.0,
            },
        ],
    },
    {
        "phone": "+31645678901",
        "name": "Pieter Bakker",
        "calls": [
            {
                "call_sid": "CA_test_005_ddd",
                "direction": "inbound",
                "status": "completed",
                "duration": 120,
                "recording_sid": "RE_test_005_ddd",
                "transcript": (
                    "Speaker 1: Hi, I just bought a new laptop from your store and the screen "
                    "has a dead pixel in the center. I'd like to return it or get a replacement.\n"
                    "Speaker 2: I'm sorry about that. When did you purchase it?\n"
                    "Speaker 1: Three days ago, on Monday.\n"
                    "Speaker 2: That's well within our 14-day return window. I can arrange a "
                    "replacement to be shipped today. You'll receive a return label via email "
                    "for the defective unit. The replacement should arrive within 2 business days.\n"
                    "Speaker 1: Perfect, that works for me.\n"
                    "Speaker 2: Is there anything else I can help with?\n"
                    "Speaker 1: No, that's all. Thanks for the quick help."
                ),
                "freq": 349.0,
            },
        ],
    },
]


def main():
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Recordings dir: {RECORDINGS_DIR}")

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        for conv_data in TEST_CONVERSATIONS:
            phone = conv_data["phone"]
            name = conv_data["name"]

            cur.execute(
                """
                INSERT INTO call_conversation (contact_phone, contact_name, last_call_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (contact_phone) DO UPDATE
                  SET contact_name = COALESCE(EXCLUDED.contact_name, call_conversation.contact_name),
                      last_call_at = NOW()
                RETURNING id
                """,
                (phone, name),
            )
            conv_id = cur.fetchone()[0]
            print(f"Conversation: {name or phone} (id={conv_id})")

            for call_data in conv_data["calls"]:
                call_sid = call_data["call_sid"]
                rec_sid = call_data["recording_sid"]
                status = call_data["status"]
                transcript = call_data.get("transcript")
                error_msg = call_data.get("error_message")

                # Generate MP3 file if call has a recording
                local_path = None
                if status == "completed":
                    mp3_name = f"{call_sid}_{rec_sid}.mp3"
                    mp3_path = RECORDINGS_DIR / mp3_name
                    print(f"  Generating: {mp3_name}")
                    generate_test_mp3(mp3_path, duration_s=min(call_data["duration"], 5), freq=call_data["freq"])
                    local_path = str(mp3_path)

                cur.execute(
                    """
                    INSERT INTO twilio_call
                      (conversation_id, call_sid, direction, from_number, to_number,
                       status, duration_seconds, recording_sid, local_recording_path,
                       transcript_text, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (call_sid) DO UPDATE
                      SET status = EXCLUDED.status,
                          transcript_text = COALESCE(EXCLUDED.transcript_text, twilio_call.transcript_text),
                          local_recording_path = COALESCE(EXCLUDED.local_recording_path, twilio_call.local_recording_path),
                          error_message = EXCLUDED.error_message
                    RETURNING id
                    """,
                    (
                        conv_id,
                        call_sid,
                        call_data["direction"],
                        phone,
                        "+31201234567",
                        status,
                        call_data["duration"],
                        rec_sid,
                        local_path,
                        transcript,
                        error_msg,
                    ),
                )
                call_id = cur.fetchone()[0]
                print(f"  Call: {call_sid} -> id={call_id} status={status}")

        conn.commit()
        print("\nDone! Test data seeded successfully.")
        print(f"Created {sum(len(c['calls']) for c in TEST_CONVERSATIONS)} calls across {len(TEST_CONVERSATIONS)} conversations.")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
