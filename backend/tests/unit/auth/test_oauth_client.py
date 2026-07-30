from urllib.parse import parse_qs, urlparse

import respx
from httpx import Response

from app.auth import oauth_client


def test_build_authorize_url_includes_required_params():
    url = oauth_client.build_authorize_url("state-123")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.netloc == "accounts.google.com"
    assert params["access_type"] == ["offline"]
    assert params["prompt"] == ["consent"]
    assert params["state"] == ["state-123"]
    assert params["response_type"] == ["code"]
    for scope in oauth_client.SCOPES:
        assert scope in params["scope"][0]


@respx.mock
async def test_exchange_code_parses_response():
    respx.post(oauth_client.TOKEN_URL).mock(
        return_value=Response(
            200,
            json={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "scope": "activity_and_fitness.readonly",
            },
        )
    )

    tokens = await oauth_client.exchange_code("auth-code")

    assert tokens.access_token == "access-1"
    assert tokens.refresh_token == "refresh-1"
    assert tokens.scope == "activity_and_fitness.readonly"


@respx.mock
async def test_refresh_access_token_falls_back_to_existing_refresh_token():
    respx.post(oauth_client.TOKEN_URL).mock(
        return_value=Response(200, json={"access_token": "access-2", "expires_in": 3600})
    )

    tokens = await oauth_client.refresh_access_token("existing-refresh-token")

    assert tokens.access_token == "access-2"
    assert tokens.refresh_token == "existing-refresh-token"
