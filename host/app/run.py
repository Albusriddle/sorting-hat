
from __future__ import annotations
import asyncio
import sys

import uvicorn

from .admin_app import admin_app
from .config import settings, validate_settings
from .device_app import device_app


def _ssl_kwargs() -> dict:
    if not settings.require_tls:
        return {}
    if not (settings.tls_cert and settings.tls_key):
        print("REQUIRE_TLS=1 but TLS_CERT/TLS_KEY missing", file=sys.stderr)
        raise SystemExit(2)
    return {"ssl_certfile": settings.tls_cert, "ssl_keyfile": settings.tls_key}


async def main() -> None:
    try:
        validate_settings()
    except ValueError as exc:
        print(f"invalid settings: {exc}", file=sys.stderr)
        raise SystemExit(2)
    ssl = _ssl_kwargs()
    dev = uvicorn.Server(uvicorn.Config(device_app, host=settings.host, port=settings.port,
                                        log_level="info", **ssl))
    adm = uvicorn.Server(uvicorn.Config(admin_app, host="127.0.0.1", port=settings.admin_port,
                                        log_level="info"))
    await asyncio.gather(dev.serve(), adm.serve())


if __name__ == "__main__":
    asyncio.run(main())
