from __future__ import annotations

import asyncio

from app.services import ingest


def main() -> int:
    result = asyncio.run(ingest.run_ingest())
    if result.get("locked"):
        print("lock held, skipping")
        return 0
    print(f"ingest ok: {result['totals']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
