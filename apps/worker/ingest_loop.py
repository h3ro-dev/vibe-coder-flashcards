"""AnyIO loop for daily feed ingestion."""
from __future__ import annotations

import anyio
from loguru import logger

from apps.worker.ingestors.twitter import ingest_handles
from apps.worker import init_db

HANDLES = [
    "dr_cintas",
    "GoogleLabs",
    "kregenrek",
    "GeminiApp",
    "OpenAI",
    "AnthropicAI",
    "GoogleAI",
]


async def job() -> None:
    """Run a single ingestion job."""
    logger.info("Running ingest job…")
    ingest_handles(HANDLES)


async def main() -> None:
    """Run ingestion job once per day."""
    init_db()
    while True:
        await job()
        await anyio.sleep(60 * 60 * 24)


if __name__ == "__main__":
    anyio.run(main)
