"""GPIO push button handler with debouncing."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from devdash.config import AppConfig

log = logging.getLogger(__name__)

DEBOUNCE_MS = 200


class ButtonHandler:
    def __init__(self, config: AppConfig):
        self.config = config
        self.pin = config.gpio.button_pin
        self._callback: Optional[Callable] = None
        self._hw_available = False
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_press = 0

    def start(self):
        """Initialize GPIO button with interrupt or polling."""
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            # Use edge detection for responsive button
            GPIO.add_event_detect(
                self.pin, GPIO.RISING,
                callback=self._gpio_callback,
                bouncetime=DEBOUNCE_MS,
            )
            self._hw_available = True
            log.info("Button initialized on GPIO %d", self.pin)
        except (ImportError, RuntimeError) as e:
            log.warning("Button hardware unavailable: %s — press 'D' key in UI to simulate", e)

        self._running = True

    def stop(self):
        self._running = False
        if self._hw_available:
            try:
                import RPi.GPIO as GPIO
                GPIO.remove_event_detect(self.pin)
            except Exception:
                pass

    def on_press(self, callback: Optional[Callable]):
        """Register a callback for button press events."""
        self._callback = callback

    async def wait_for_button_press(self, timeout: float = 30) -> bool:
        """Block until button is pressed or timeout. Returns True if pressed."""
        pressed = threading.Event()

        def on_press():
            pressed.set()

        old_callback = self._callback
        self._callback = on_press
        result = pressed.wait(timeout=timeout)
        self._callback = old_callback
        return result

    def _gpio_callback(self, channel):
        """Called by GPIO interrupt."""
        now = time.monotonic()
        if now - self._last_press < DEBOUNCE_MS / 1000:
            return
        self._last_press = now

        log.info("Button pressed!")
        if self._callback:
            self._callback()

    def simulate_press(self):
        """Simulate a button press (for desktop testing)."""
        log.info("Simulated button press")
        if self._callback:
            self._callback()
