import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import oauth_client
from app.auth.token_service import PROVIDER
from app.core.database import get_session
from app.core.security import encrypt
from app.ingestion.backfill_service import start_backfill
from app.storage.repositories.token_repository import TokenRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])

STATE_COOKIE = "google_oauth_state"

# Google Health API resolves the authenticated caller as "users/me" — there is
# no separate user id to look up for a single-account personal app.
EXTERNAL_USER_ID = "me"


@router.get("/status")
async def status(session: AsyncSession = Depends(get_session)) -> dict:
    token = await TokenRepository(session).get(PROVIDER)
    if token is None:
        return {"connected": False}
    return {"connected": True, "scope": token.scope, "expires_at": token.expires_at.isoformat()}


@router.get("/google/login")
async def login() -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(oauth_client.build_authorize_url(state))
    response.set_cookie(STATE_COOKIE, state, httponly=True, max_age=600)
    return response


@router.get("/google/callback")
async def callback(
    request: Request, code: str, state: str, session: AsyncSession = Depends(get_session)
) -> RedirectResponse:
    expected_state = request.cookies.get(STATE_COOKIE)
    if expected_state is None or state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    tokens = await oauth_client.exchange_code(code)
    if tokens.refresh_token is None:
        raise HTTPException(status_code=502, detail="Google did not return a refresh token")

    await TokenRepository(session).upsert(
        provider=PROVIDER,
        access_token_encrypted=encrypt(tokens.access_token),
        refresh_token_encrypted=encrypt(tokens.refresh_token),
        scope=tokens.scope,
        expires_at=tokens.expires_at,
        external_user_id=EXTERNAL_USER_ID,
    )
    await start_backfill(session)

    response = RedirectResponse("/")
    response.delete_cookie(STATE_COOKIE)
    return response


@router.post("/google/disconnect")
async def disconnect(session: AsyncSession = Depends(get_session)) -> dict:
    await TokenRepository(session).delete(PROVIDER)
    return {"connected": False}
