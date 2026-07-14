import base64
import hashlib

import httpx
import pytest
import respx

from agenticsocial.x import auth


@pytest.fixture()
def fake_keyring(monkeypatch):
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        auth.keyring, "set_password", lambda svc, acct, val: store.__setitem__((svc, acct), val)
    )
    monkeypatch.setattr(
        auth.keyring, "get_password", lambda svc, acct: store.get((svc, acct))
    )
    return store


def test_pkce_pair_is_valid_s256():
    verifier, challenge = auth.pkce_pair()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    assert challenge == expected
    assert 43 <= len(verifier) <= 128


def test_token_roundtrip_via_keyring(fake_keyring):
    assert auth.load_token() is None
    auth.save_token({"access_token": "abc", "refresh_token": "r1"})
    assert auth.load_token() == {"access_token": "abc", "refresh_token": "r1"}
    assert ("agenticsocial", "x") in fake_keyring


@respx.mock
def test_refresh_exchanges_and_saves(fake_keyring):
    respx.post(auth.TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "new", "refresh_token": "r2", "expires_in": 7200}
        )
    )
    token = auth.refresh("client123", {"refresh_token": "r1"})
    assert token["access_token"] == "new"
    assert auth.load_token()["refresh_token"] == "r2"


@respx.mock
def test_refresh_failure_raises_autherror(fake_keyring):
    respx.post(auth.TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(auth.AuthError, match="agsoc auth x"):
        auth.refresh("client123", {"refresh_token": "r1"})
