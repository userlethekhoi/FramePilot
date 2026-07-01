import os
from typing import Any, List
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import TranscriptionSegment
from app.core.interfaces.tts import BaseTextToSpeech


class LocalTextToSpeech(BaseTextToSpeech):
    """Local offline voice synthesis provider wrapping pyttsx3 or writing dummy files."""

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        options: dict[str, Any],
    ) -> str:
        
        # Support mock/test environments
        if options.get("mock", False) or os.getenv("MEDIAFLOW_TTS_MOCK") == "1":
            return self._write_dummy_audio(output_path)

        import asyncio
        return await asyncio.to_thread(self._synthesize_sync, text, voice_id, output_path, options)

    def _synthesize_sync(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        options: dict[str, Any],
    ) -> str:
        try:
            import pyttsx3
        except ImportError as e:
            logger.warning("pyttsx3 package not installed. Writing dummy audio fallback.")
            return self._write_dummy_audio(output_path)

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            engine = pyttsx3.init()
            
            # Configure voice if voice_id given
            if voice_id:
                engine.setProperty("voice", voice_id)
            
            # Speed configuration
            rate = options.get("rate")
            if rate:
                engine.setProperty("rate", rate)

            engine.save_to_file(text, output_path)
            engine.runAndWait()
            
            # Clean up engine resources safely
            del engine
            
            return output_path
        except Exception as e:
            logger.error("Local pyttsx3 voice synthesis failed: {}", e)
            return self._write_dummy_audio(output_path)

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
            out_file = os.path.join(output_dir, f"segment_{i:04d}.wav")
            path = await self.synthesize(seg.text, voice_id, out_file, options)
            results.append(path)
            
        return results

    def _write_dummy_audio(self, path: str) -> str:
        """Writes a small mock audio file for testing/development."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Smallest valid MP3 / WAV block
        dummy_data = b"\xFF\xFB\x90\x44\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        with open(path, "wb") as f:
            f.write(dummy_data)
        return path
