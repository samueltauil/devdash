"""Voice service — USB mic + local Whisper STT with push-to-talk state machine."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum, auto

log = logging.getLogger(__name__)


class VoiceState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()


class VoiceService:
    """Push-to-talk voice input using local Whisper model."""

    def __init__(self, config):
        self.config = config
        self.model = None
        self.mic_available = False
        self.state = VoiceState.IDLE
        self._sd = None

    async def start(self):
        """Detect mic and load Whisper model."""
        self.mic_available = self._detect_mic()
        if self.mic_available:
            await self._load_model()

    def _detect_mic(self) -> bool:
        try:
            import sounddevice as sd
            self._sd = sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d["max_input_channels"] > 0]
            if input_devices:
                log.info("Mic detected: %s", input_devices[0]["name"])
                return True
            log.warning("No input devices found")
            return False
        except Exception as e:
            log.warning("Mic detection failed: %s", e)
            return False

    async def _load_model(self):
        try:
            from faster_whisper import WhisperModel

            size = self.config.voice.model_size
            log.info("Loading Whisper model (%s)...", size)
            self.model = await asyncio.to_thread(
                WhisperModel, size, device="cpu", compute_type="int8"
            )
            log.info("Whisper model loaded")
        except ImportError:
            log.warning("faster-whisper not installed — voice disabled")
            self.mic_available = False
        except Exception as e:
            log.error("Whisper model load failed: %s", e)
            self.mic_available = False

    async def record_and_transcribe(self, max_seconds: int = 10) -> str:
        """Record audio and transcribe. Runs blocking I/O in threads."""
        if not self.mic_available or not self.model:
            return ""

        self.state = VoiceState.RECORDING
        try:
            samplerate = self.config.voice.sample_rate
            log.info("Recording for up to %ds...", max_seconds)
            audio = self._sd.rec(
                int(max_seconds * samplerate),
                samplerate=samplerate,
                channels=1,
                dtype="float32",
            )
            await asyncio.to_thread(self._sd.wait)

            self.state = VoiceState.TRANSCRIBING
            text = await asyncio.to_thread(self._transcribe, audio.flatten())
            return text
        except Exception as e:
            log.error("Voice recording failed: %s", e)
            return ""
        finally:
            self.state = VoiceState.IDLE

    def _transcribe(self, audio) -> str:
        segments, _ = self.model.transcribe(audio, language="en")
        text = " ".join(seg.text for seg in segments).strip()
        log.info("Transcribed: %s", text[:80])
        return text
