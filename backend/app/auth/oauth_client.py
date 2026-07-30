import datetime
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import get_settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
]


@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_at: datetime.datetime
    scope: str


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _parse_token_response(payload: dict, fallback_refresh_token: str | None = None) -> TokenResponse:
    expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(
        seconds=payload["expires_in"]
    )
    return TokenResponse(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token", fallback_refresh_token),
        expires_at=expires_at,
        scope=payload.get("scope", ""),
    )


async def exchange_code(code: str) -> TokenResponse:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
    return _parse_token_response(response.json())


async def refresh_access_token(refresh_token: str) -> TokenResponse:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
    return _parse_token_response(response.json(), fallback_refresh_token=refresh_token)
