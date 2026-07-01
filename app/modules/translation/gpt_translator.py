import json
import os
import urllib.request
import urllib.parse
from typing import Any, List, Optional
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import TranscriptionSegment
from app.core.interfaces.translation import BaseTranslator


class GptTranslator(BaseTranslator):
    """Cloud translation provider leveraging OpenAI GPT models."""

    def __init__(self) -> None:
        self.default_model = "gpt-4o-mini"

    async def translate_text(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        # Resolve API Key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Fallback for mock mode or testing
            return f"[Translated to {target_lang}]: {text}"

        import asyncio
        return await asyncio.to_thread(self._translate_sync, text, target_lang, source_lang, api_key)

    def _translate_sync(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str],
        api_key: str,
    ) -> str:
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        src_info = f"from {source_lang} " if source_lang else ""
        system_prompt = (
            "You are a professional subtitle translator. "
            f"Translate the following text {src_info}to target language: {target_lang}. "
            "Preserve any markers like '---SEG---' and match line counts precisely. "
            "Return only the direct translation, nothing else."
        )

        payload = {
            "model": self.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_data = response.read().decode("utf-8")
                data = json.loads(resp_data)
                return str(data["choices"][0]["message"]["content"]).strip()
        except Exception as e:
            logger.error("GPT Translation failed: {}", e)
            raise ServiceError(f"GPT translation failed: {e}") from e

    async def translate_segments(
        self,
        segments: List[TranscriptionSegment],
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> List[TranscriptionSegment]:
        
        if not segments:
            return []

        # OpenAI API Key check (for tests/mock fallbacks)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Mock mode translation: return text with localized prefix
            return [
                TranscriptionSegment(
                    start=seg.start,
                    end=seg.end,
                    text=f"[{target_lang}] {seg.text}",
                    speaker_id=seg.speaker_id,
                )
                for seg in segments
            ]

        # Batch translate segments
        delimiter = "\n---SEG---\n"
        texts = [seg.text for seg in segments]
        combined_text = delimiter.join(texts)

        translated_combined = await self.translate_text(combined_text, target_lang, source_lang)
        translated_texts = [t.strip() for t in translated_combined.split("---SEG---")]

        # Split mismatch fallback
        if len(translated_texts) != len(segments):
            logger.warning("GPT split mismatch, falling back to individual segment translations.")
            result_segments = []
            for seg in segments:
                tr_text = await self.translate_text(seg.text, target_lang, source_lang)
                result_segments.append(
                    TranscriptionSegment(
                        start=seg.start,
                        end=seg.end,
                        text=tr_text,
                        speaker_id=seg.speaker_id,
                    )
                )
            return result_segments

        result_segments = []
        for i, seg in enumerate(segments):
            clean_text = translated_texts[i].strip().lstrip("-").strip()
            result_segments.append(
                TranscriptionSegment(
                    start=seg.start,
                    end=seg.end,
                    text=clean_text,
                    speaker_id=seg.speaker_id,
                )
            )
        return result_segments
