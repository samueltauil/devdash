"""Piezo buzzer controller for audio alerts."""

from __future__ import annotations

import logging
import threading
import time

from devdash.config import AppConfig

log = logging.getLogger(__name__)


# Note frequencies (Hz)
NOTES = {
    "C4": 262, "D4": 294, "E4": 330, "F4": 349,
    "G4": 392, "A4": 440, "B4": 494, "C5": 523,
}

# Alert melodies
MELODIES = {
    "success": [("C4", 0.15), ("E4", 0.15), ("G4", 0.15), ("C5", 0.3)],
    "error": [("C5", 0.2), ("G4", 0.2), ("C4", 0.4)],
    "alert": [("A4", 0.1), (None, 0.05), ("A4", 0.1), (None, 0.05), ("A4", 0.3)],
    "deploy": [("C4", 0.1), ("D4", 0.1), ("E4", 0.1), ("F4", 0.1), ("G4", 0.3)],
}


class BuzzerController:
    def __init__(self, config: AppConfig):
        self.config = config
        self.pin = config.gpio.buzzer_pin
        self._pwm = None
        self._hw_available = False

        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self._pwm = GPIO.PWM(self.pin, 440)
            self._hw_available = True
            log.info("Buzzer initialized on GPIO %d", self.pin)
        except (ImportError, RuntimeError) as e:
            log.warning("Buzzer hardware unavailable: %s", e)

    def _play_melody(self, melody_name: str):
        """Play a melody in a background thread."""
        melody = MELODIES.get(melody_name)
        if not melody:
            return

        def _play():
            for note, duration in melody:
                if note and self._hw_available and self._pwm:
                    freq = NOTES.get(note, 440)
                    self._pwm.ChangeFrequency(freq)
                    self._pwm.start(50)
                    time.sleep(duration)
                    self._pwm.stop()
                else:
                    time.sleep(duration)

        thread = threading.Thread(target=_play, daemon=True)
        thread.start()

    def play_success(self):
        self._play_melody("success")

    def play_error(self):
        self._play_melody("error")

    def play_alert(self):
        self._play_melody("alert")

    def play_deploy(self):
        self._play_melody("deploy")

    def stop(self):
        if self._pwm:
            self._pwm.stop()
