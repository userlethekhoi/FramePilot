import json
import mimetypes
import os
import urllib.request
import urllib.error
from collections.abc import Callable
from typing import Any, Optional
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import (
    BaseSpeechToTextProvider,
    TranscriptionResult,
    TranscriptionSegment,
)


class OpenAiSpeechToTextProvider(BaseSpeechToTextProvider):
    """Cloud Speech-to-Text provider leveraging OpenAI's Whisper API."""

    async def transcribe(
        self,
        audio_path: str,
        options: dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> TranscriptionResult:
        
        api_key = options.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ServiceError("OpenAI API key not found. Please configure it in settings.")

        if not os.path.exists(audio_path):
            raise ServiceError(f"Audio file not found at: {audio_path}")

        logger.info("Starting OpenAI cloud transcription for: {}", audio_path)
        if progress_callback:
            progress_callback(10.0)

        # Execute blocking HTTP operations in a thread pool
        import asyncio
        return await asyncio.to_thread(self._transcribe_sync, audio_path, api_key, options, progress_callback)

    def _transcribe_sync(
        self,
        audio_path: str,
        api_key: str,
        options: dict[str, Any],
        progress_callback: Optional[Callable[[float], None]],
    ) -> TranscriptionResult:
        
        url = "https://api.openai.com/v1/audio/transcriptions"
        boundary = "====MediaFlowAIBoundary===="
        
        # Build multipart/form-data payload
        try:
            with open(audio_path, "rb") as f:
                file_content = f.read()
        except Exception as e:
            raise ServiceError(f"Failed to read audio file: {e}") from e

        file_name = os.path.basename(audio_path)
        mime_type = mimetypes.guess_type(audio_path)[0] or "application/octet-stream"

        # Headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

        # Build form parts
        parts = []
        
        # Model parameter
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="model"\r\n\r\n'.encode("utf-8"))
        parts.append("whisper-1\r\n".encode("utf-8"))

        # Response format (verbose_json to get segment level timestamps)
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="response_format"\r\n\r\n'.encode("utf-8"))
        parts.append("verbose_json\r\n".encode("utf-8"))

        # Optional language parameter
        language = options.get("language")
        if language:
            parts.append(f"--{boundary}\r\n".encode("utf-8"))
            parts.append(f'Content-Disposition: form-data; name="language"\r\n\r\n'.encode("utf-8"))
            parts.append(f"{language}\r\n".encode("utf-8"))

        # File parameter
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode("utf-8")
        )
        parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
        parts.append(file_content)
        parts.append("\r\n".encode("utf-8"))
        
        # End boundary
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))

        body = b"".join(parts)

        if progress_callback:
            progress_callback(40.0)

        # Make Request
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                resp_data = response.read().decode("utf-8")
                data = json.loads(resp_data)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error("OpenAI STT API returned error: {}", error_body)
            raise ServiceError(f"OpenAI transcription API failed: {e.reason} - {error_body}") from e
        except Exception as e:
            logger.error("Failed requesting OpenAI STT: {}", e)
            raise ServiceError(f"OpenAI API request failed: {e}") from e

        if progress_callback:
            progress_callback(90.0)

        # Parse verbose_json segments
        segments = []
        raw_segments = data.get("segments", [])
        for seg in raw_segments:
            segments.append(
                TranscriptionSegment(
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=seg.get("text", "").strip(),
                )
            )

        full_text = data.get("text", "")
        duration = float(data.get("duration", 0.0))
        detected_lang = data.get("language", "en")

        if progress_callback:
            progress_callback(100.0)

        return TranscriptionResult(
            segments=segments,
            language=detected_lang,
            full_text=full_text,
            duration=duration,
        )
