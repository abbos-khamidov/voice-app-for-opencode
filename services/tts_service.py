import asyncio
import re
from collections.abc import Callable
from pathlib import Path

import edge_tts


class TTSGenerationError(Exception):
    pass


class TTSCancelled(Exception):
    pass


class TTSService:
    SYMBOLS_TO_SKIP = re.compile(r"[\-*—–•_~`#=<>|/\\\[\]{}]+")
    EXTRA_SPACES = re.compile(r"\s+")
    LANGUAGE_PARTS = re.compile(r"([A-Za-z]+|[А-Яа-яЁё]+|[^A-Za-zА-Яа-яЁё]+)")
    SENTENCE_PARTS = re.compile(r"[^.!?;:]+[.!?;:]?|[^.!?;:]+$")
    MAX_SEGMENT_CHARS = 280

    def generate_speech(
        self,
        text: str,
        voice: str,
        speed: str,
        pitch: str,
        volume: str,
        output_path: Path,
        should_cancel=None,
    ) -> None:
        segments = self._prepare_segments(text, voice)
        if not segments:
            raise TTSGenerationError("There is no readable text after removing symbols.")

        temp_output_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")

        try:
            asyncio.run(
                self._generate(
                    segments,
                    speed,
                    pitch,
                    volume,
                    temp_output_path,
                    should_cancel,
                )
            )
            temp_output_path.replace(output_path)
        except TTSCancelled:
            temp_output_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            temp_output_path.unlink(missing_ok=True)
            raise TTSGenerationError(
                "Could not generate speech. Check your internet connection and try again."
            ) from exc

    def generate_speech_streaming(
        self,
        text: str,
        voice: str,
        speed: str,
        pitch: str,
        volume: str,
        output_path: Path,
        chunk_dir: Path,
        on_chunk_ready: Callable[[Path], None],
        wait_for_slot=None,
        should_cancel=None,
    ) -> None:
        segments = self._prepare_segments(text, voice)
        if not segments:
            raise TTSGenerationError("There is no readable text after removing symbols.")

        chunk_dir.mkdir(parents=True, exist_ok=True)
        for old_chunk in chunk_dir.glob("chunk_*.mp3"):
            old_chunk.unlink(missing_ok=True)

        temp_output_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")

        try:
            asyncio.run(
                self._generate_streaming(
                    segments,
                    speed,
                    pitch,
                    volume,
                    temp_output_path,
                    chunk_dir,
                    on_chunk_ready,
                    wait_for_slot,
                    should_cancel,
                )
            )
            temp_output_path.replace(output_path)
        except TTSCancelled:
            temp_output_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            temp_output_path.unlink(missing_ok=True)
            raise TTSGenerationError(
                "Could not generate speech. Check your internet connection and try again."
            ) from exc

    async def _generate(
        self,
        segments: list[tuple[str, str]],
        speed: str,
        pitch: str,
        volume: str,
        output_path: Path,
        should_cancel,
    ) -> None:
        with output_path.open("wb") as audio_file:
            for segment_text, segment_voice in segments:
                if should_cancel and should_cancel():
                    raise TTSCancelled()

                communicate = edge_tts.Communicate(
                    text=segment_text,
                    voice=segment_voice,
                    rate=speed,
                    pitch=pitch,
                    volume=volume,
                )
                stream = communicate.stream()
                try:
                    async for message in stream:
                        if should_cancel and should_cancel():
                            raise TTSCancelled()

                        if message["type"] == "audio":
                            audio_file.write(message["data"])
                finally:
                    await stream.aclose()

    async def _generate_streaming(
        self,
        segments: list[tuple[str, str]],
        speed,
        pitch: str,
        volume: str,
        output_path: Path,
        chunk_dir: Path,
        on_chunk_ready: Callable[[Path], None],
        wait_for_slot,
        should_cancel,
    ) -> None:
        with output_path.open("wb") as combined_audio:
            for index, (segment_text, segment_voice) in enumerate(segments):
                if should_cancel and should_cancel():
                    raise TTSCancelled()

                if wait_for_slot:
                    wait_for_slot()

                chunk_path = chunk_dir / f"chunk_{index:04d}.mp3"
                current_speed = speed() if callable(speed) else speed
                await self._generate(
                    [(segment_text, segment_voice)],
                    current_speed,
                    pitch,
                    volume,
                    chunk_path,
                    should_cancel,
                )

                if should_cancel and should_cancel():
                    raise TTSCancelled()

                combined_audio.write(chunk_path.read_bytes())
                combined_audio.flush()
                on_chunk_ready(chunk_path)

    def _prepare_segments(self, text: str, selected_voice: str) -> list[tuple[str, str]]:
        cleaned_text = self._clean_text(text)
        if not cleaned_text:
            return []

        segments: list[tuple[str, str]] = []
        current_language: str | None = None
        current_text = ""

        for part in self.LANGUAGE_PARTS.findall(cleaned_text):
            part_language = self._detect_language(part)

            if part_language is None:
                current_text += part
                continue

            if current_language is None:
                current_language = part_language

            if part_language != current_language and current_text.strip():
                segments.extend(
                    (chunk, selected_voice)
                    for chunk in self._split_readable_chunks(current_text.strip())
                )
                current_text = part
                current_language = part_language
            else:
                current_text += part
                current_language = part_language

        if current_text.strip():
            segments.extend(
                (chunk, selected_voice)
                for chunk in self._split_readable_chunks(current_text.strip())
            )

        return segments

    def _clean_text(self, text: str) -> str:
        without_symbols = self.SYMBOLS_TO_SKIP.sub(" ", text)
        return self.EXTRA_SPACES.sub(" ", without_symbols).strip()

    def _split_readable_chunks(self, text: str) -> list[str]:
        chunks: list[str] = []
        current = ""

        for match in self.SENTENCE_PARTS.findall(text):
            part = match.strip()
            if not part:
                continue

            if len(part) > self.MAX_SEGMENT_CHARS:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._split_long_text(part))
                continue

            candidate = f"{current} {part}".strip()
            if current and len(candidate) > self.MAX_SEGMENT_CHARS:
                chunks.append(current.strip())
                current = part
            else:
                current = candidate

        if current:
            chunks.append(current.strip())

        return chunks

    def _split_long_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        current = ""

        for word in text.split():
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > self.MAX_SEGMENT_CHARS:
                chunks.append(current.strip())
                current = word
            else:
                current = candidate

        if current:
            chunks.append(current.strip())

        return chunks

    def _detect_language(self, text: str) -> str | None:
        if re.search(r"[А-Яа-яЁё]", text):
            return "ru"

        if re.search(r"[A-Za-z]", text):
            return "en"

        return None
