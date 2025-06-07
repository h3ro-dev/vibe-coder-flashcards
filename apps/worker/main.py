"""FastAPI worker entrypoint for Vibe Coder Flashcards.

Provides a simple health-check route for now.
"""
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI, OpenAIError
import os
from sqlmodel import Session, select
import datetime as dt

from .schemas import (
    TextIn,
    SummaryOut,
    Flashcard,
    FlashcardsOut,
    FlashcardsDBOut,
    ReviewIn,
    ReviewOut,
    FlashcardDB,
)
from packages.core.models import User, Feed, Post, Flashcard as DBFlashcard
from packages.core.spaced_repetition import sm2
from . import engine, init_db

init_db()

app = FastAPI(title="Vibe Coder Flashcards Worker")

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "test"))


@app.get("/", include_in_schema=False)
async def root_health() -> dict[str, str]:
    """Health-check endpoint used by tests & uptime monitors."""
    return {"status": "ok"}


@app.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    """Health-check endpoint used by uptime monitors."""
    return {"status": "ok"}


@app.post("/summarise", response_model=SummaryOut)
async def summarise(payload: TextIn) -> SummaryOut:
    """Return a concise summary of the provided text."""
    try:
        chat = await client.chat.completions.create(
            model="gpt-3.5-turbo",  # small cheap model
            messages=[{"role": "user", "content": f"Summarise:\n{payload.text}"}],
            max_tokens=128,
        )
    except OpenAIError as exc:  # pragma: no cover - network errors are mocked
        raise HTTPException(status_code=502, detail="OpenAI error") from exc
    return SummaryOut(summary=chat.choices[0].message.content.strip())


@app.post("/flashcards", response_model=FlashcardsDBOut)
async def generate_flashcards(payload: TextIn) -> FlashcardsDBOut:
    """Generate Q/A flashcards from input text."""
    prompt = (
        "Convert the following text to <=5 study flashcards in JSON array of objects "
        "with \"question\" & \"answer\" keys only. No extra keys. Text:\n" + payload.text
    )
    try:
        chat = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            response_format={"type": "json_object"},
        )
    except OpenAIError as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail="OpenAI error") from exc
    cards_data = chat.choices[0].message.content
    # simple parse – assumes correct JSON
    import json

    decoded = json.loads(cards_data)
    cards = [Flashcard(**c) for c in decoded]

    with Session(engine) as ses:
        # ensure demo user/feed/post exist
        user = ses.exec(select(User).where(User.id == 1)).first()
        if not user:
            user = User(id=1, email="demo@example.com")
            ses.add(user)
        feed = ses.exec(select(Feed).where(Feed.id == 1)).first()
        if not feed:
            feed = Feed(id=1, handle="manual")
            ses.add(feed)
        post = Post(feed_id=feed.id, tweet_id="manual", text=payload.text)
        ses.add(post)
        ses.commit()
        ses.refresh(post)

        out_cards: list[FlashcardDB] = []
        for c in cards:
            db_card = DBFlashcard(
                owner_id=user.id,
                post_id=post.id,
                question=c.question,
                answer=c.answer,
            )
            ses.add(db_card)
            ses.commit()
            ses.refresh(db_card)
            out_cards.append(
                FlashcardDB(id=db_card.id, question=db_card.question, answer=db_card.answer)
            )
    return FlashcardsDBOut(flashcards=out_cards)


@app.get("/deck/today", response_model=FlashcardsDBOut)
async def deck_today(user_id: int = 1) -> FlashcardsDBOut:
    """Return flashcards due for review today."""
    today = dt.date.today()
    with Session(engine) as ses:
        cards = ses.exec(
            select(DBFlashcard).where(
                DBFlashcard.owner_id == user_id,
                DBFlashcard.next_review <= today,
            ).limit(30)
        ).all()
        out = [
            FlashcardDB(id=c.id, question=c.question, answer=c.answer) for c in cards
        ]
    return FlashcardsDBOut(flashcards=out)


@app.post("/review", response_model=ReviewOut)
async def review(payload: ReviewIn) -> ReviewOut:
    """Update flashcard scheduling based on recall quality."""
    with Session(engine) as ses:
        card = ses.get(DBFlashcard, payload.flashcard_id)
        if not card:
            raise HTTPException(status_code=404, detail="Flashcard not found")

        reps, interval, ease = sm2(
            card.repetitions,
            card.interval,
            card.ease_factor,
            payload.quality,
        )
        card.repetitions = reps
        card.interval = interval
        card.ease_factor = ease
        card.next_review = dt.date.today() + dt.timedelta(days=interval)
        ses.add(card)
        ses.commit()
        ses.refresh(card)
    return ReviewOut(id=card.id, next_review=str(card.next_review), interval=card.interval)
