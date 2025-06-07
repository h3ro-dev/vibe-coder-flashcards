"""APScheduler cron jobs for spaced repetition."""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import date
from typing import Iterable

from packages.core.spaced_repetition import Card, schedule_cards

# In-memory card store used for demo & tests
CARDS: list[Card] = []


def daily_job(today: date | None = None, cards: Iterable[Card] | None = None) -> None:
    """Run daily scheduling for all cards."""
    if today is None:
        today = date.today()
    if cards is None:
        cards = CARDS
    schedule_cards(cards, today)


def start_scheduler() -> None:
    """Start APScheduler with daily job at midnight."""
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(daily_job, "cron", hour=0, minute=0)
    scheduler.start()


def main(argv: list[str] | None = None) -> None:
    """Simple CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Worker scheduler utilities")
    parser.add_argument("command", choices=["daily", "run"], help="Run once or start scheduler")
    args = parser.parse_args(argv)

    if args.command == "daily":
        daily_job()
    elif args.command == "run":
        start_scheduler()


if __name__ == "__main__":
    main()
