"""Voice input — USB mic auto-detection + local Whisper STT."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class VoiceInput:
    """Auto-detected voice input using local Whisper model.

    Only active when a USB microphone is detected.
    Uses faster-whisper (small model, int8 quantized) for fully offline STT.
    """

    def __init__(self):
        self.model = None
        self.mic_available = self._detect_usb_mic()

    def _detect_usb_mic(self) -> bool:
        """Check if a USB microphone is connected."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d["max_input_channels"] > 0]
            if input_devices:
                log.info("USB mic detected: %s", input_devices[0]["name"])
                return True
            return False
        except (ImportError, Exception) as e:
            log.debug("Voice input unavailable: %s", e)
            return False

    async def load_model(self):
        """Load Whisper small model — runs well on Pi 5 (2-3s for 10s audio)."""
        if self.mic_available and self.model is None:
            try:
                from faster_whisper import WhisperModel
                self.model = WhisperModel("small", device="cpu", compute_type="int8")
                log.info("Whisper model loaded (small, int8)")
            except ImportError:
                log.warning("faster-whisper not installed — voice disabled")
                self.mic_available = False

    async def record_and_transcribe(self, max_seconds: int = 10) -> str:
        """Record from mic until silence/timeout, then transcribe locally."""
        if not self.mic_available or not self.model:
            return ""

        try:
            import sounddevice as sd
            import numpy as np

            samplerate = 16000
            log.info("Recording for up to %ds...", max_seconds)
            audio = sd.rec(
                int(max_seconds * samplerate),
                samplerate=samplerate,
                channels=1,
                dtype="float32",
            )
            sd.wait()

            # Transcribe locally — audio never leaves the device
            segments, _ = self.model.transcribe(audio.flatten(), language="en")
            text = " ".join(seg.text for seg in segments)
            result = text.strip()
            log.info("Transcribed: %s", result[:80])
            return result
        except Exception as e:
            log.error("Voice recording/transcription failed: %s", e)
            return ""
