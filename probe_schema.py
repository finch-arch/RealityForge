#!/usr/bin/env python3
"""Connect to LingBot World 2 and dump the server-provided command schema.

Cheap: connects and asks for the schema, never calls `start`, so no
generation is billed. Resolves the `set_image` param shape that the
public docs don't document for Python.
"""

import asyncio
import json
import pathlib
import sys

from reactor_sdk import Reactor, ReactorStatus

ROOT = pathlib.Path(__file__).parent
MODEL = "reactor/lingbot-world-2"
CONNECT_TIMEOUT = 60.0


def read_api_key() -> str:
    key = (ROOT / "api.js").read_text().strip()
    if not key.startswith("rk_"):
        sys.exit(f"api.js does not look like a Reactor key (got {key[:8]!r}...)")
    return key


async def main() -> None:
    reactor = Reactor(model_name=MODEL, api_key=read_api_key())
    ready = asyncio.Event()

    @reactor.on_status(ReactorStatus.READY)
    async def on_ready(status):
        ready.set()

    @reactor.on_message
    def on_message(msg):
        print(f"[msg] {json.dumps(msg)[:400]}")

    @reactor.on_error
    def on_error(err):
        print(f"[error] {err.operation}: [{err.code}] {err.message}")

    try:
        print(f"connecting to {MODEL} ...")
        await reactor.connect()
        await asyncio.wait_for(ready.wait(), timeout=CONNECT_TIMEOUT)
        print(f"READY  session={reactor.get_session_id()}")

        schema = await reactor.request_schema()
        out = ROOT / "out" / "schema.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(schema, indent=2))
        print(f"\nschema written to {out}  ({len(json.dumps(schema))} bytes)")

        print("\n=== tracks ===")
        for t in reactor.tracks:
            print(f"  {t}")
    finally:
        # Never leave a session open — it bills per second.
        await reactor.disconnect()
        print("disconnected")


if __name__ == "__main__":
    asyncio.run(main())
