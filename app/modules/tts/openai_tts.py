import json
import os
import urllib.request
from typing import Any, List
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import TranscriptionSegment
from app.core.interfaces.tts import BaseTextToSpeech


class OpenAiTextToSpeech(BaseTextToSpeech):
    """Cloud voice synthesis provider leveraging OpenAI's TTS API."""

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        options: dict[str, Any],
    ) -> str:
        
        api_key = options.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Fallback for mock mode or testing: write dummy wav/mp3 file
            return self._write_dummy_audio(output_path)

        import asyncio
        return await asyncio.to_thread(
            self._synthesize_sync, text, voice_id, output_path, api_key, options
        )

    def _synthesize_sync(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        api_key: str,
        options: dict[str, Any],
    ) -> str:
        
        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": options.get("model", "tts-1"),
            "input": text,
            "voice": voice_id or "alloy",
            "response_format": options.get("format", "mp3"),
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                audio_data = response.read()
                
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_data)
            return output_path
        except Exception as e:
            logger.error("OpenAI TTS synthesis failed: {}", e)
            raise ServiceError(f"OpenAI TTS synthesis failed: {e}") from e

    async def synthesize_segments(
        self,
        segments: List[TranscriptionSegment],
        voice_id: str,
        output_dir: str,
        options: dict[str, Any],
    ) -> List[str]:
        
        results = []
        os.makedirs(output_dir, exist_ok=True)
        
        for i, seg in enumerate(segments):
            out_file = os.path.join(output_dir, f"segment_{i:04d}.mp3")
            # Call synthesize on each segment
            path = await self.synthesize(seg.text, voice_id, out_file, options)
            results.append(path)
            
        return results

    def _write_dummy_audio(self, path: str) -> str:
        """Writes a small mock audio file for testing/development."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Smallest valid MP3 block
        dummy_mp3 = b"\xFF\xFB\x90\x44\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        with open(path, "wb") as f:
            f.write(dummy_mp3)
        return path
