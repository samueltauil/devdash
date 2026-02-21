"""DevDash entry point — allows `python -m devdash`."""

from devdash.main import main
import asyncio

asyncio.run(main())
