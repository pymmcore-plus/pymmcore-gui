"""Voice control: wake word detection, VAD, and speech-to-text."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from pymmcore_gui._qt.QtCore import QObject, Signal

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHANNELS = 1
OWW_CHUNK = 1280  # openWakeWord chunk size (80ms at 16kHz)
MAX_RECORD_SECONDS = 10
SILENCE_TIMEOUT = 1.0
WHISPER_MODEL = "base"
WAKE_WORD_MODEL = "hey_jarvis"

# ---------------------------------------------------------------------------
# Lazy-loaded models
# ---------------------------------------------------------------------------

_oww_model = None
_vad_model = None
_whisper_model = None


def _get_oww_model() -> Any:
    global _oww_model
    if _oww_model is None:
        import urllib.request
        from pathlib import Path

        from openwakeword.model import Model

        oww_file = __import__("openwakeword").__file__
        if oww_file is None:
            raise RuntimeError("Cannot locate openwakeword package")
        pkg_dir = Path(oww_file).parent
        model_dir = pkg_dir / "resources" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)

        needed = {
            "melspectrogram.onnx": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx",
            "embedding_model.onnx": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx",
            "hey_jarvis_v0.1.onnx": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx",
        }
        for fname, url in needed.items():
            dest = model_dir / fname
            if not dest.exists():
                logger.debug("Downloading %s...", fname)
                urllib.request.urlretrieve(url, dest)

        _oww_model = Model(
            wakeword_models=[str(model_dir / "hey_jarvis_v0.1.onnx")],
            inference_framework="onnx",
        )
    return _oww_model


def _get_vad_model() -> Any:
    global _vad_model
    if _vad_model is None:
        import torch

        model, _utils = torch.hub.load(  # pyright: ignore[reportGeneralTypeIssues]
            "snakers4/silero-vad",
            "silero_vad",
            trust_repo=True,  # pyright: ignore[reportArgumentType]
        )
        _vad_model = model
    return _vad_model


def _get_whisper_model() -> Any:
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel(WHISPER_MODEL, device="auto", compute_type="int8")
    return _whisper_model


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def _transcribe(audio: np.ndarray) -> str:
    model = _get_whisper_model()
    segments, _info = model.transcribe(audio, beam_size=5, language="en")
    return " ".join(seg.text.strip() for seg in segments).strip()


def _record_until_silence() -> np.ndarray:
    import numpy as np
    import sounddevice as sd
    import torch

    vad_model = _get_vad_model()
    vad_frame = 512
    silent_chunks_needed = int(SILENCE_TIMEOUT * SAMPLE_RATE / vad_frame)
    max_chunks = int(MAX_RECORD_SECONDS * SAMPLE_RATE / vad_frame)

    chunks: list[np.ndarray] = []
    silent_chunks = 0
    speech_started = False

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=vad_frame,
    )
    stream.start()
    try:
        for _ in range(max_chunks):
            data, _overflow = stream.read(vad_frame)
            audio_f32 = data[:, 0]
            chunks.append(audio_f32.copy())

            tensor = torch.from_numpy(audio_f32)
            speech_prob = vad_model(tensor, SAMPLE_RATE).item()

            if speech_prob > 0.5:
                speech_started = True
                silent_chunks = 0
            elif speech_started:
                silent_chunks += 1
                if silent_chunks >= silent_chunks_needed:
                    break
    finally:
        stream.stop()
        stream.close()
        vad_model.reset_states()

    return np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)


# ---------------------------------------------------------------------------
# VoiceListener QObject
# ---------------------------------------------------------------------------


class VoiceListener(QObject):
    """Listens for a wake word, records speech, transcribes, and emits text."""

    # Emitted with the transcribed text after wake word + speech
    command_received = Signal(str)
    # Status updates for the UI
    status_changed = Signal(str)  # "listening", "recording", "transcribing"
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_listening(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start listening for wake words in a background thread."""
        if self.is_listening:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="voice-listener"
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the voice listener."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None

    def _run(self) -> None:
        try:
            import sounddevice as sd

            logger.debug("Loading voice models...")
            self.status_changed.emit("loading models...")
            oww = _get_oww_model()
            _get_vad_model()
            _get_whisper_model()

            self.status_changed.emit("listening")
            logger.debug("Voice listener ready, waiting for wake word...")

            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=OWW_CHUNK,
            )
            stream.start()
            try:
                while not self._stop_event.is_set():
                    data, _overflow = stream.read(OWW_CHUNK)
                    audio_i16 = data[:, 0]
                    prediction = oww.predict(audio_i16)
                    for _name, score in prediction.items():
                        if score > 0.5:
                            oww.reset()
                            self._handle_wake()
            finally:
                stream.stop()
                stream.close()
        except Exception as e:
            logger.exception("Voice listener error")
            self.error_occurred.emit(str(e))
        finally:
            self.status_changed.emit("")

    def _handle_wake(self) -> None:

        logger.debug("Wake word detected!")
        self.status_changed.emit("recording...")

        audio = _record_until_silence()
        if len(audio) < SAMPLE_RATE * 0.3:
            logger.debug("Recording too short, ignoring")
            self.status_changed.emit("listening")
            return

        self.status_changed.emit("transcribing...")
        text = _transcribe(audio)
        self.status_changed.emit("listening")

        if text:
            logger.debug("Transcribed: %s", text)
            self.command_received.emit(text)
        else:
            logger.debug("Empty transcription")
