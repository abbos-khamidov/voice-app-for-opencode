import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame


class AudioPlaybackError(Exception):
    pass


class AudioService:
    def __init__(self) -> None:
        self._initialized = False

    def play(self, audio_path: Path) -> None:
        if not audio_path.exists():
            raise AudioPlaybackError("Audio file was not created.")

        try:
            self._ensure_initialized()
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
        except Exception as exc:
            raise AudioPlaybackError(
                "Could not play audio. Check your macOS audio output and try again."
            ) from exc

    def stop(self) -> None:
        if not self._initialized:
            return

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

    def is_playing(self) -> bool:
        if not self._initialized:
            return False

        try:
            return bool(pygame.mixer.music.get_busy())
        except Exception:
            return False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        pygame.mixer.init()
        self._initialized = True
