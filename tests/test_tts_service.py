from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from services.tts_service import TTSGenerationError, TTSService


def test_clean_text_removes_symbols_and_extra_spaces() -> None:
    service = TTSService()

    assert service._clean_text("Hello --- world *** Привет") == "Hello world Привет"


def test_prepare_segments_splits_long_text_without_changing_voice() -> None:
    service = TTSService()
    text = " ".join(["word"] * 120)

    segments = service._prepare_segments(text, "en-US-AvaMultilingualNeural")

    assert len(segments) > 1
    assert all(voice == "en-US-AvaMultilingualNeural" for _, voice in segments)
    assert all(len(segment) <= service.MAX_SEGMENT_CHARS for segment, _ in segments)


def test_generate_speech_rejects_symbol_only_text(tmp_path: Path) -> None:
    service = TTSService()

    with pytest.raises(TTSGenerationError, match="no readable text"):
        service.generate_speech(
            text="--- *** ___",
            voice="en-US-AvaMultilingualNeural",
            speed="+0%",
            pitch="+0Hz",
            volume="+0%",
            output_path=tmp_path / "speech.mp3",
        )

