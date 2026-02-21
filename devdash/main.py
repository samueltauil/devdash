"""DevDash entry point — run with `python -m devdash`."""

import asyncio
import sys
import signal
import logging

from devdash.config import load_config
from devdash.database import Database
from devdash.ui.renderer import Renderer
from devdash.ui.touch import TouchHandler
from devdash.ui.screen_manager import ScreenManager
from devdash.services.github_service import GitHubService
from devdash.services.copilot_service import CopilotService
from devdash.services.system_service import SystemService
from devdash.hardware.leds import LEDController
from devdash.hardware.button import ButtonHandler
from devdash.hardware.buzzer import BuzzerController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("devdash")


async def main():
    config = load_config()
    db = Database(config)
    await db.initialize()

    # Services
    github_svc = GitHubService(config, db)
    copilot_svc = CopilotService(config)
    system_svc = SystemService()

    # Hardware (gracefully disabled if not on Pi)
    leds = LEDController(config)
    button = ButtonHandler(config)
    buzzer = BuzzerController(config)

    # UI
    renderer = Renderer(config)
    touch = TouchHandler(config)

    screen_mgr = ScreenManager(
        config=config,
        renderer=renderer,
        touch=touch,
        github_service=github_svc,
        copilot_service=copilot_svc,
        system_service=system_svc,
        leds=leds,
        button=button,
        buzzer=buzzer,
        db=db,
    )

    # Graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler():
        log.info("Shutting down...")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: signal_handler())

    try:
        await copilot_svc.start()
        leds.start()
        button.start()

        log.info("DevDash started — %dx%d", config.display.width, config.display.height)

        await screen_mgr.run(shutdown_event)
    except KeyboardInterrupt:
        pass
    finally:
        log.info("Cleaning up...")
        button.stop()
        leds.stop()
        await copilot_svc.stop()
        await db.close()
        renderer.quit()


if __name__ == "__main__":
    asyncio.run(main())
