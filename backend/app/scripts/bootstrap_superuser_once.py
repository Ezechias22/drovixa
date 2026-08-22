from __future__ import annotations

import asyncio

from app.core.database import dispose_database
from app.scripts.bootstrap_superuser import bootstrap


async def main() -> None:
    try:
        await bootstrap(reset_existing_password=False)
    finally:
        await dispose_database()


if __name__ == "__main__":
    asyncio.run(main())
