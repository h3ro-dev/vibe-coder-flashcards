import os
import httpx
import anyio
import types
import pytest

# Use async driver for migrations
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="module")
def worker_app():
    # After migrations have run, switch to sync driver for the worker
    os.environ["DATABASE_URL"] = "sqlite://"
    from apps.worker.main import app, client as openai_client
    return app, openai_client


@pytest.fixture(autouse=True)
def reset_db(worker_app):
    from apps.worker import engine
    from sqlmodel import SQLModel
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield

@pytest.fixture(autouse=True)
def mock_openai(monkeypatch, worker_app):
    app, openai_client = worker_app

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

async def request(app, method: str, url: str, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.request(method, url, **kwargs)
        return resp

def test_deck_today_returns_cards(worker_app):
    app, _ = worker_app

    async def run():
        resp = await request(app, "POST", "/flashcards", json={"text": "hi"})
        assert resp.status_code == 200
        card_id = resp.json()["flashcards"][0]["id"]
        deck = await request(app, "GET", "/deck/today")
        assert deck.status_code == 200
        ids = [c["id"] for c in deck.json()["flashcards"]]
        assert card_id in ids
    anyio.run(run)

def test_review_updates_schedule(worker_app):
    app, _ = worker_app

    async def run():
        resp = await request(app, "POST", "/flashcards", json={"text": "hi"})
        card_id = resp.json()["flashcards"][0]["id"]
        review = await request(app, "POST", "/review", json={"flashcard_id": card_id, "quality": 5})
        assert review.status_code == 200
        data = review.json()
        assert data["id"] == card_id
        assert int(data["interval"]) >= 1
        deck = await request(app, "GET", "/deck/today")
        assert card_id not in [c["id"] for c in deck.json()["flashcards"]]
    anyio.run(run)
