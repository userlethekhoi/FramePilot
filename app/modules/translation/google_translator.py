import json
import urllib.request
import urllib.parse
from typing import List, Optional
from loguru import logger
from app.core.exceptions import ServiceError
from app.core.interfaces.speech import TranscriptionSegment
from app.core.interfaces.translation import BaseTranslator


class GoogleTranslator(BaseTranslator):
    """Free Google Translate public API provider."""

    async def translate_text(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        
        import asyncio
        return await asyncio.to_thread(self._translate_sync, text, target_lang, source_lang)

    def _translate_sync(
        self,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        
        sl = source_lang or "auto"
        tl = target_lang
        
        encoded_text = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={encoded_text}"
        
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                raw_data = response.read().decode("utf-8")
                data = json.loads(raw_data)
                
                # Google Translate single translation returns array of blocks
                translated_blocks = []
                for item in data[0]:
                    if item[0]:
                        translated_blocks.append(item[0])
                return "".join(translated_blocks)
        except Exception as e:
            logger.error("Google Translate request failed: {}", e)
            raise ServiceError(f"Google Translation failed: {e}") from e

    async def translate_segments(
        self,
        segments: List[TranscriptionSegment],
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> List[TranscriptionSegment]:
        
        if not segments:
            return []

        # Optimization: batch translate segments using separator to minimize HTTP calls
        # Using a special delimiter that translators usually preserve
        delimiter = "\n---SEG---\n"
        texts = [seg.text for seg in segments]
        combined_text = delimiter.join(texts)

        translated_combined = await self.translate_text(combined_text, target_lang, source_lang)
        
        # Split back
        translated_texts = [t.strip() for t in translated_combined.split("---SEG---")]
        
        # Fallback if split mismatch occurs
        if len(translated_texts) != len(segments):
            logger.warning(
                "Batch translation split mismatch (expected {}, got {}). Translating individually.",
                len(segments),
                len(translated_texts),
            )
            # Individual fallback
            translated_segments = []
            for seg in segments:
                translated_text = await self.translate_text(seg.text, target_lang, source_lang)
                translated_segments.append(
                    TranscriptionSegment(
                        start=seg.start,
                        end=seg.end,
                        text=translated_text,
                        speaker_id=seg.speaker_id,
                    )
                )
            return translated_segments

        # Map back
        translated_segments = []
        for i, seg in enumerate(segments):
            # Clean up leading/trailing symbols that google translate might add to the separator
            clean_text = translated_texts[i].strip().lstrip("-").strip()
            translated_segments.append(
                TranscriptionSegment(
                    start=seg.start,
                    end=seg.end,
                    text=clean_text,
                    speaker_id=seg.speaker_id,
                )
            )
        return translated_segments
