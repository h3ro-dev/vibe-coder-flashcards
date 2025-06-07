import json
import httpx
from openai import APIError
import os
import anyio

os.environ["DATABASE_URL"] = "sqlite://"
from apps.worker.main import app, client as openai_client
import types
import pytest


@pytest.fixture(autouse=True)
def mock_openai(monkeypatch):
    """Patch OpenAI chat completion to avoid real API calls."""

    async def fake_create(*args, **kwargs):
        dummy = types.SimpleNamespace()
        dummy.choices = [
            types.SimpleNamespace(
                message=types.SimpleNamespace(content='[{"question":"Q","answer":"A"}]')
            )
        ]
        return dummy

    monkeypatch.setattr(openai_client.chat.completions, "create", fake_create)
    yield


async def request(method: str, url: str, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.request(method, url, **kwargs)
        return resp


def test_summarise_route():
    async def run():
        resp = await request("POST", "/summarise", json={"text": "OpenAI builds AI systems."})
        assert resp.status_code == 200
        assert resp.json()["summary"] == '[{"question":"Q","answer":"A"}]'

    anyio.run(run)


def test_summarise_validation_error():
    async def run():
        resp = await request("POST", "/summarise", json={})
        assert resp.status_code == 422

    anyio.run(run)


def test_summarise_openai_error(monkeypatch):
    async def fail_create(*args, **kwargs):
        raise APIError("boom", request=None, body=None)

    monkeypatch.setattr(openai_client.chat.completions, "create", fail_create)
    async def run():
        resp = await request("POST", "/summarise", json={"text": "hi"})
        assert resp.status_code == 502
        assert resp.json()["detail"] == "OpenAI error"

    anyio.run(run)


def test_flashcards_route_schema():
    """Ensure response model keys are correct when mocked."""
    payload = {"text": "Python is a popular programming language."}
    async def run():
        resp = await request("POST", "/flashcards", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "flashcards" in data
        for card in data["flashcards"]:
            assert set(card) == {"id", "question", "answer"}

    anyio.run(run)


def test_review_route_updates_schedule():
    async def run():
        from sqlmodel import Session
        from apps.worker import engine
        from packages.core.models import User, Feed, Post, Flashcard as DBFlashcard
        # manually create entities to avoid unique constraints
        with Session(engine) as ses:
            user = User(email="demo2@example.com")
            feed = Feed(handle="manual2")
            ses.add(user)
            ses.add(feed)
            ses.commit()
            ses.refresh(user)
            ses.refresh(feed)

            post = Post(feed_id=feed.id, tweet_id="manual2", text="hi")
            ses.add(post)
            ses.commit()
            ses.refresh(post)

            card = DBFlashcard(
                owner_id=user.id,
                post_id=post.id,
                question="Q",
                answer="A",
            )
            ses.add(card)
            ses.commit()
            ses.refresh(card)
            card_id = card.id

        resp = await request(
            "POST",
            "/review",
            json={"flashcard_id": card_id, "quality": 5},
        )
        assert resp.status_code == 200

        import datetime as dt

        with Session(engine) as ses:
            card = ses.get(DBFlashcard, card_id)
            assert card.repetitions == 1
            assert card.interval == 1
            assert round(card.ease_factor, 1) == 2.6
            assert card.next_review == dt.date.today() + dt.timedelta(days=1)

    anyio.run(run)
