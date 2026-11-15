from __future__ import annotations
import asyncio
import uvicorn

from .admin_app import admin_app
from .config import settings
from .device_app import device_app


async def main() -> None:
    dev = uvicorn.Server(uvicorn.Config(device_app, host=settings.host, port=settings.port,
                                        log_level="info"))
    adm = uvicorn.Server(uvicorn.Config(admin_app, host="127.0.0.1", port=settings.admin_port,
                                        log_level="info"))
    await asyncio.gather(dev.serve(), adm.serve())


if __name__ == "__main__":
    asyncio.run(main())
