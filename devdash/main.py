"""DevDash entry point — voice-first conversational interface."""

import asyncio
import signal
import logging

import pygame

from devdash.config import load_config
from devdash.database import Database
from devdash.ui.renderer import Renderer
from devdash.ui.touch import TouchHandler, GestureType
from devdash.services.github_service import GitHubService
from devdash.services.copilot_service import CopilotService
from devdash.services.voice_service import VoiceService
from devdash.services.system_service import SystemService
from devdash.screens.conversation import ConversationScreen

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
    copilot_svc = CopilotService(config, github_service=github_svc, db=db)
    voice_svc = VoiceService(config)
    system_svc = SystemService()

    # UI
    renderer = Renderer(config)
    touch = TouchHandler(config)

    screen = ConversationScreen(
        config=config,
        renderer=renderer,
        copilot_service=copilot_svc,
        voice_service=voice_svc,
        system_service=system_svc,
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
        await voice_svc.start()

        # Background GitHub data poll
        asyncio.create_task(_periodic_poll(github_svc, config, shutdown_event))

        log.info("DevDash started — %dx%d", config.display.width, config.display.height)

        clock = pygame.time.Clock()
        while not shutdown_event.is_set():
            for gesture in touch.process_events():
                if gesture.type == GestureType.TAP:
                    screen.handle_tap(gesture.x, gesture.y)

            screen.render()
            clock.tick(config.display.fps)
            await asyncio.sleep(0)

    except KeyboardInterrupt:
        pass
    finally:
        log.info("Cleaning up...")
        await copilot_svc.stop()
        await db.close()
        renderer.quit()


async def _periodic_poll(github_svc, config, shutdown_event):
    """Poll GitHub API periodically in the background."""
    while not shutdown_event.is_set():
        try:
            await github_svc.poll_all()
        except Exception as e:
            log.error("GitHub poll error: %s", e)
        await asyncio.sleep(config.github.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
