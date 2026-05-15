from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.audio_service import AudioPlaybackError, AudioService
from services.tts_service import TTSCancelled, TTSGenerationError, TTSService


class TTSWorker(QThread):
    generated = pyqtSignal(Path)
    chunk_ready = pyqtSignal(Path)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        generation_id: int,
        text: str,
        voice: str,
        speed: str,
        pitch: str,
        volume: str,
        output_path: Path,
        chunk_dir: Path,
    ) -> None:
        super().__init__()
        self.generation_id = generation_id
        self.text = text
        self.voice = voice
        self.speed = speed
        self.pitch = pitch
        self.volume = volume
        self.output_path = output_path
        self.chunk_dir = chunk_dir
        self._cancel_requested = False
        self._speed = speed
        self._queued_chunks = 0

    def cancel(self) -> None:
        self._cancel_requested = True

    def set_speed(self, speed: str) -> None:
        self._speed = speed

    def get_speed(self) -> str:
        return self._speed

    def emit_chunk_ready(self, chunk_path: Path) -> None:
        self._queued_chunks += 1
        self.chunk_ready.emit(chunk_path)

    def mark_chunk_started(self) -> None:
        if self._queued_chunks > 0:
            self._queued_chunks -= 1

    def wait_for_slot(self) -> None:
        while self._queued_chunks >= 2 and not self._cancel_requested:
            self.msleep(50)

    def run(self) -> None:
        try:
            TTSService().generate_speech_streaming(
                text=self.text,
                voice=self.voice,
                speed=self.get_speed,
                pitch=self.pitch,
                volume=self.volume,
                output_path=self.output_path,
                chunk_dir=self.chunk_dir,
                on_chunk_ready=self.emit_chunk_ready,
                wait_for_slot=self.wait_for_slot,
                should_cancel=lambda: self._cancel_requested,
            )
        except TTSCancelled:
            self.cancelled.emit()
        except TTSGenerationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Unexpected TTS error: {exc}")
        else:
            if self._cancel_requested:
                self.cancelled.emit()
                return

            self.generated.emit(self.output_path)


class MainWindow(QMainWindow):
    VOICES = {
        "Ava Multilingual Natural": "en-US-AvaMultilingualNeural",
        "Andrew Multilingual Natural": "en-US-AndrewMultilingualNeural",
        "Emma Multilingual Natural": "en-US-EmmaMultilingualNeural",
        "Brian Multilingual Natural": "en-US-BrianMultilingualNeural",
        "Jenny (US English)": "en-US-JennyNeural",
        "Guy (US English)": "en-US-GuyNeural",
        "Svetlana (Russian)": "ru-RU-SvetlanaNeural",
        "Dmitry (Russian)": "ru-RU-DmitryNeural",
    }

    TONES = {
        "Natural": ("+0Hz", "+0%"),
        "Lively": ("+8Hz", "+8%"),
        "Confident": ("-2Hz", "+10%"),
        "Soft": ("+4Hz", "-8%"),
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Text Reader")
        self.resize(820, 560)

        self.audio_service = AudioService()
        self.worker: TTSWorker | None = None
        self.current_generation_id = 0
        self.stop_requested = False
        self.generation_finished = False
        self.output_path = Path(__file__).resolve().parents[1] / "speech.mp3"
        self.chunk_dir = self.output_path.parent / "tts_chunks"
        self.playback_queue: list[Path] = []

        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(60)
        self.playback_timer.timeout.connect(self.play_next_chunk_if_ready)

        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("Paste text to read aloud...")

        self.voice_selector = QComboBox()
        self.voice_selector.addItems(self.VOICES.keys())

        self.speed_selector = QDoubleSpinBox()
        self.speed_selector.setRange(0.5, 2.0)
        self.speed_selector.setSingleStep(0.05)
        self.speed_selector.setDecimals(2)
        self.speed_selector.setValue(1.0)
        self.speed_selector.setSuffix("x")
        self.speed_selector.valueChanged.connect(self.on_speed_changed)

        self.tone_selector = QComboBox()
        self.tone_selector.addItems(self.TONES.keys())

        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        self.status_label = QLabel("Ready")

        self.play_button.clicked.connect(self.play)
        self.stop_button.clicked.connect(self.stop)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Voice"))
        controls.addWidget(self.voice_selector)
        controls.addWidget(QLabel("Speed"))
        controls.addWidget(self.speed_selector)
        controls.addWidget(QLabel("Tone"))
        controls.addWidget(self.tone_selector)
        controls.addStretch()
        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)

        layout = QVBoxLayout()
        layout.addWidget(self.text_area)
        layout.addLayout(controls)
        layout.addWidget(self.status_label)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

    def play(self) -> None:
        text = self.text_area.toPlainText().strip()
        if not text:
            self.set_status("Please enter text before pressing Play.")
            QMessageBox.warning(self, "Empty text", "Paste or type some text first.")
            return

        if self.worker and self.worker.isRunning():
            self.set_status("Speech generation is already running.")
            return

        self.audio_service.stop()
        self.stop_requested = False
        self.generation_finished = False
        self.playback_queue.clear()
        self.cleanup_chunks()
        self.set_controls_enabled(False)
        self.set_status("Preparing speech...")

        voice = self.VOICES[self.voice_selector.currentText()]
        speed = self.speed_to_rate(self.speed_selector.value())
        pitch, volume = self.TONES[self.tone_selector.currentText()]

        self.current_generation_id += 1
        generation_id = self.current_generation_id

        self.worker = TTSWorker(
            generation_id,
            text,
            voice,
            speed,
            pitch,
            volume,
            self.output_path,
            self.chunk_dir,
        )
        self.worker.chunk_ready.connect(self.on_chunk_ready)
        self.worker.generated.connect(self.on_tts_finished)
        self.worker.failed.connect(self.on_tts_failed)
        self.worker.cancelled.connect(self.on_tts_cancelled)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def stop(self) -> None:
        self.stop_requested = True
        self.current_generation_id += 1
        self.generation_finished = True
        self.playback_queue.clear()

        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.set_controls_enabled(True)
            self.set_status("Stopping...")

        self.playback_timer.stop()
        self.audio_service.stop()
        self.cleanup_chunks()
        if not self.worker or not self.worker.isRunning():
            self.set_status("Stopped")

    def on_speed_changed(self, value: float) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.set_speed(self.speed_to_rate(value))
            self.set_status(f"Speed changed to {value:.2f}x")

    def on_chunk_ready(self, chunk_path: Path) -> None:
        sender = self.sender()
        if (
            self.stop_requested
            or not isinstance(sender, TTSWorker)
            or sender.generation_id != self.current_generation_id
        ):
            return

        self.playback_queue.append(chunk_path)
        self.set_controls_enabled(True)
        self.play_next_chunk_if_ready()

    def on_tts_finished(self, output_path: Path) -> None:
        sender = self.sender()
        if (
            self.stop_requested
            or not isinstance(sender, TTSWorker)
            or sender.generation_id != self.current_generation_id
        ):
            self.set_controls_enabled(True)
            self.set_status("Stopped")
            return

        self.generation_finished = True
        self.set_controls_enabled(True)
        if self.audio_service.is_playing() or self.playback_queue:
            self.set_status("Playing")
        else:
            self.set_status("Ready")

    def on_tts_failed(self, message: str) -> None:
        if self.stop_requested:
            self.set_controls_enabled(True)
            self.set_status("Stopped")
            return

        self.generation_finished = True
        self.set_controls_enabled(True)
        self.set_status(message)
        QMessageBox.critical(self, "TTS failed", message)

    def on_tts_cancelled(self) -> None:
        self.generation_finished = True
        self.set_controls_enabled(True)
        self.set_status("Stopped")

    def on_worker_finished(self) -> None:
        sender = self.sender()
        if sender is self.worker:
            self.worker = None

    def play_next_chunk_if_ready(self) -> None:
        if self.stop_requested:
            return

        if self.audio_service.is_playing():
            if not self.playback_timer.isActive():
                self.playback_timer.start()
            return

        if not self.playback_queue:
            if self.generation_finished:
                self.playback_timer.stop()
                self.set_status("Finished")
            return

        next_chunk = self.playback_queue.pop(0)
        if self.worker and self.worker.isRunning():
            self.worker.mark_chunk_started()

        try:
            self.audio_service.play(next_chunk)
        except AudioPlaybackError as exc:
            self.playback_timer.stop()
            self.set_status(str(exc))
            QMessageBox.critical(self, "Playback failed", str(exc))
            return

        self.set_status("Playing")
        if not self.playback_timer.isActive():
            self.playback_timer.start()

    def cleanup_chunks(self) -> None:
        if not self.chunk_dir.exists():
            return

        for chunk_path in self.chunk_dir.glob("chunk_*.mp3"):
            chunk_path.unlink(missing_ok=True)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.play_button.setEnabled(enabled)
        self.voice_selector.setEnabled(enabled)
        self.tone_selector.setEnabled(enabled)

    def set_status(self, message: str) -> None:
        self.status_label.setText(f"Status: {message}")

    def speed_to_rate(self, speed: float) -> str:
        percent = round((speed - 1.0) * 100)
        sign = "+" if percent >= 0 else ""
        return f"{sign}{percent}%"
