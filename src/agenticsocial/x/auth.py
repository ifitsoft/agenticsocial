"""OAuth 2.0 PKCE flow for X. Tokens live only in the OS keychain."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import keyring

SERVICE = "agenticsocial"
ACCOUNT = "x"
AUTH_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REDIRECT_PORT = 8721
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SCOPES = "tweet.read tweet.write users.read offline.access"


class AuthError(Exception):
    pass


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def save_token(token: dict) -> None:
    keyring.set_password(SERVICE, ACCOUNT, json.dumps(token))


def load_token() -> dict | None:
    raw = keyring.get_password(SERVICE, ACCOUNT)
    return json.loads(raw) if raw else None


def _exchange(data: dict) -> dict:
    resp = httpx.post(TOKEN_URL, data=data, timeout=30)
    if resp.status_code != 200:
        raise AuthError(
            f"token request failed ({resp.status_code}): {resp.text} — run `agsoc auth x` to reconnect"
        )
    token = resp.json()
    save_token(token)
    return token


def refresh(client_id: str, token: dict) -> dict:
    if "refresh_token" not in token:
        raise AuthError("stored token has no refresh_token — reconnect with `agsoc auth x`")
    return _exchange(
        {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": client_id,
        }
    )


def _parse_callback(path: str, expected_state: str) -> str:
    params = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    state = (params.get("state") or [None])[0]
    if state != expected_state:
        raise AuthError("state mismatch in OAuth callback — rejecting; run `agsoc auth x` again")
    code = (params.get("code") or [None])[0]
    if not code:
        raise AuthError("no authorization code in callback — denied or cancelled; run `agsoc auth x` again")
    return code


class _CallbackHandler(BaseHTTPRequestHandler):
    received_path: str | None = None

    def do_GET(self):  # noqa: N802 (http.server API)
        _CallbackHandler.received_path = self.path
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>agsoc: authorized</h1>You can close this tab.")

    def log_message(self, *args):  # silence request logging
        pass


def authorize(client_id: str) -> dict:
    """Interactive: open the browser, catch the callback, exchange the code."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    server = HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
    print(f"opening browser to authorize (or visit):\n{url}")
    webbrowser.open(url)
    _CallbackHandler.received_path = None
    server.handle_request()  # blocks for exactly one callback
    server.server_close()
    if _CallbackHandler.received_path is None:
        raise AuthError("no callback received — flow cancelled? run `agsoc auth x` again")
    code = _parse_callback(_CallbackHandler.received_path, state)
    return _exchange(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
    )
