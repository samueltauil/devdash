"""NeoPixel LED strip controller — ambient status via GPIO."""

from __future__ import annotations

import logging
import threading
import time

from devdash.config import AppConfig

log = logging.getLogger(__name__)


# LED patterns
PATTERNS = {
    "solid_green": {"colors": [(0, 255, 0)], "mode": "solid"},
    "solid_red": {"colors": [(255, 0, 0)], "mode": "solid"},
    "solid_yellow": {"colors": [(255, 200, 0)], "mode": "solid"},
    "breathe_green": {"colors": [(0, 255, 0)], "mode": "breathe"},
    "breathe_blue": {"colors": [(0, 100, 255)], "mode": "breathe"},
    "breathe_yellow": {"colors": [(255, 200, 0)], "mode": "breathe"},
    "breathe_red": {"colors": [(255, 0, 0)], "mode": "breathe"},
    "flash_red": {"colors": [(255, 0, 0)], "mode": "flash"},
    "celebration": {
        "colors": [(255, 0, 0), (255, 127, 0), (255, 255, 0),
                   (0, 255, 0), (0, 0, 255), (148, 0, 211)],
        "mode": "rainbow",
    },
    "off": {"colors": [(0, 0, 0)], "mode": "solid"},
}


class LEDController:
    def __init__(self, config: AppConfig):
        self.config = config
        self.pin = config.gpio.led_pin
        self.count = config.gpio.led_count
        self.brightness = config.gpio.led_brightness
        self._strip = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._current_pattern = "off"
        self._hw_available = False

    def start(self):
        """Initialize LED strip."""
        try:
            from rpi_ws281x import PixelStrip, Color

            self._strip = PixelStrip(
                self.count, self.pin, 800000, 10, False, self.brightness, 0
            )
            self._strip.begin()
            self._hw_available = True
            log.info("NeoPixel LED strip initialized: %d LEDs on GPIO %d", self.count, self.pin)
        except (ImportError, RuntimeError) as e:
            log.warning("LED hardware unavailable: %s — running in simulation mode", e)
            self._hw_available = False

        self._running = True
        self._thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Turn off LEDs and stop animation thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.set_pattern("off")
        if self._hw_available and self._strip:
            for i in range(self.count):
                self._strip.setPixelColor(i, 0)
            self._strip.show()

    def set_pattern(self, pattern_name: str):
        """Set the current LED pattern."""
        if pattern_name in PATTERNS:
            self._current_pattern = pattern_name
            log.debug("LED pattern → %s", pattern_name)
        else:
            log.warning("Unknown LED pattern: %s", pattern_name)

    def set_status(self, ci_failing: bool, prs_pending: int, deploying: bool):
        """Auto-set LED pattern based on overall status."""
        if deploying:
            self.set_pattern("breathe_blue")
        elif ci_failing:
            self.set_pattern("flash_red")
        elif prs_pending > 3:
            self.set_pattern("breathe_yellow")
        elif prs_pending > 0:
            self.set_pattern("solid_yellow")
        else:
            self.set_pattern("solid_green")

    def _animation_loop(self):
        """Background thread running LED animations."""
        t = 0
        while self._running:
            pattern = PATTERNS.get(self._current_pattern, PATTERNS["off"])
            mode = pattern["mode"]
            colors = pattern["colors"]

            if mode == "solid":
                self._set_all(colors[0])
            elif mode == "breathe":
                import math
                brightness = (math.sin(t * 2) + 1) / 2  # 0.0 to 1.0
                r, g, b = colors[0]
                self._set_all((int(r * brightness), int(g * brightness), int(b * brightness)))
            elif mode == "flash":
                on = int(t * 4) % 2 == 0
                self._set_all(colors[0] if on else (0, 0, 0))
            elif mode == "rainbow":
                for i in range(self.count):
                    color_idx = (i + int(t * 5)) % len(colors)
                    self._set_pixel(i, colors[color_idx])
                self._show()

            t += 0.05
            time.sleep(0.05)

    def _set_all(self, color: tuple[int, int, int]):
        for i in range(self.count):
            self._set_pixel(i, color)
        self._show()

    def _set_pixel(self, idx: int, color: tuple[int, int, int]):
        if self._hw_available and self._strip:
            from rpi_ws281x import Color
            self._strip.setPixelColor(idx, Color(*color))

    def _show(self):
        if self._hw_available and self._strip:
            self._strip.show()
