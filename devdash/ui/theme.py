"""Color theme and style constants."""

from __future__ import annotations

# Layout constants
STATUS_BAR_HEIGHT = 32
NAV_BAR_HEIGHT = 40
CONTENT_Y = STATUS_BAR_HEIGHT
CONTENT_HEIGHT = 248  # 320 - 32 - 40

# Touch targets
MIN_TAP_SIZE = 48
BUTTON_HEIGHT = 48
BUTTON_PADDING = 8

# Card dimensions (480px wide screen)
CARD_MARGIN = 12
CARD_WIDTH = 480 - 2 * CARD_MARGIN  # 456px
CARD_PADDING = 12
CARD_BORDER_RADIUS = 12

# Animation
SWIPE_ANIM_MS = 200
FADE_ANIM_MS = 150
