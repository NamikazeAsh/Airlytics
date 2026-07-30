import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_coach.coach_service import send_message
from app.ai_coach.insights_service import generate_insights
from app.ai_coach.provider_factory import LLMNotConfiguredError
from app.core.database import get_session
from app.storage.repositories.conversation_repository import ConversationRepository
from app.storage.repositories.insight_repository import InsightRepository

router = APIRouter(prefix="/api/coach", tags=["coach"])


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str


@router.post("/chat")
async def chat(body: ChatRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return await send_message(session, body.conversation_id, body.message)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, session: AsyncSession = Depends(get_session)) -> list[dict]:
    messages = await ConversationRepository(session).get_messages(conversation_id)
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in messages
        if m.role in ("user", "assistant") and m.content
    ]


@router.get("/insights")
async def insights(days: int = 7, session: AsyncSession = Depends(get_session)) -> list[dict]:
    since = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=days)
    rows = await InsightRepository(session).get_since(since)
    return [
        {"body": r.body, "category": r.category, "generated_at": r.generated_at.isoformat()}
        for r in rows
    ]


@router.post("/insights/generate")
async def trigger_insights(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        generated = await generate_insights(session)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"generated": generated}
