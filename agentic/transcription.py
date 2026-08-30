from __future__ import annotations

import json
import os
import re
import subprocess
import wave
from pathlib import Path

import httpx

from .models import TranscriptSegment


TIMESTAMP_RE = re.compile(r"\[?(\d{1,2}):?(\d{2})(?:[.,](\d{1,3}))?\s*(?:-->|-)\s*(\d{1,2}):?(\d{2})(?:[.,](\d{1,3}))?\]?")


def _seconds(minute: str, second: str, millis: str | None) -> float:
    fraction = int((millis or "0").ljust(3, "0")[:3]) / 1000
    return int(minute) * 60 + int(second) + fraction


def parse_transcript(path: str | Path) -> list[TranscriptSegment]:
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")
    if source.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("segments", payload.get("transcript", []))
        return [TranscriptSegment(start=float(item.get("start", index * 5)), end=float(item.get("end", index * 5 + 5)), text=str(item.get("text", "")).strip(), speaker=str(item.get("speaker", "unknown"))) for index, item in enumerate(payload) if str(item.get("text", "")).strip()]
    lines = text.splitlines()
    segments: list[TranscriptSegment] = []
    index = 0
    while index < len(lines):
        match = TIMESTAMP_RE.search(lines[index])
        if match:
            start = _seconds(match.group(1), match.group(2), match.group(3))
            end = _seconds(match.group(4), match.group(5), match.group(6))
            body: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() and not TIMESTAMP_RE.search(lines[index]):
                if not lines[index].strip().isdigit():
                    body.append(lines[index].strip())
                index += 1
            content = " ".join(body)
            speaker, utterance = "unknown", content
            if ":" in content and len(content.split(":", 1)[0].split()) <= 3:
                speaker, utterance = content.split(":", 1)
            if utterance.strip():
                segments.append(TranscriptSegment(start=start, end=end, text=utterance.strip(), speaker=speaker.strip() or "unknown"))
        else:
            index += 1
    if segments:
        return segments
    plain = [line.strip() for line in lines if line.strip()]
    return [TranscriptSegment(start=index * 5.0, end=index * 5.0 + 5.0, text=line) for index, line in enumerate(plain)]


def audio_technical_metrics(path: str | Path) -> dict[str, float | str | None]:
    source = Path(path)
    if source.suffix.lower() == ".wav":
        try:
            with wave.open(str(source), "rb") as audio:
                duration = audio.getnframes() / max(audio.getframerate(), 1)
                return {"duration_seconds": round(duration, 2), "sample_rate": audio.getframerate(), "channels": audio.getnchannels(), "status": "usable" if duration >= 5 else "review"}
        except (wave.Error, EOFError):
            return {"duration_seconds": None, "status": "unreadable"}
    try:
        completed = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(source)], capture_output=True, text=True, timeout=10, check=False)
        duration = float(completed.stdout.strip()) if completed.returncode == 0 and completed.stdout.strip() else None
        return {"duration_seconds": None if duration is None else round(duration, 2), "status": "usable" if duration and duration >= 5 else "review"}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"duration_seconds": None, "status": "unknown"}


async def transcribe_audio(path: str | Path, api_key: str | None = None, model: str = "whisper-large-v3-turbo") -> list[TranscriptSegment]:
    source = Path(path)
    if source.suffix.lower() in {".json", ".txt", ".srt", ".vtt"}:
        return parse_transcript(source)
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Audio transcription requires GROQ_API_KEY, or upload a JSON/SRT/VTT transcript")
    async with httpx.AsyncClient(timeout=180) as client:
        with source.open("rb") as handle:
            response = await client.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"}, data={"model": model, "response_format": "verbose_json", "temperature": "0"}, files={"file": (source.name, handle, "application/octet-stream")})
    if response.status_code >= 400:
        raise RuntimeError("The transcription provider rejected the recording")
    payload = response.json()
    segments = payload.get("segments") or []
    if not segments and payload.get("text"):
        duration = float(payload.get("duration") or 0)
        segments = [{"start": 0, "end": duration, "text": payload["text"]}]
    return [TranscriptSegment(start=float(item.get("start", 0)), end=float(item.get("end", 0)), text=str(item.get("text", "")).strip()) for item in segments if str(item.get("text", "")).strip()]
