"""Thin client for the X API v2 tweets endpoint."""
from __future__ import annotations

import httpx

API_URL = "https://api.x.com/2/tweets"


class XApiError(Exception):
    pass


class XClient:
    def __init__(self, access_token: str, http: httpx.Client | None = None):
        self._http = http or httpx.Client(timeout=30)
        self._headers = {"Authorization": f"Bearer {access_token}"}

    def post_tweet(self, text: str, in_reply_to: str | None = None) -> str:
        payload: dict = {"text": text}
        if in_reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": in_reply_to}
        resp = self._http.post(API_URL, json=payload, headers=self._headers)
        if resp.status_code == 429:
            reset = resp.headers.get("x-rate-limit-reset", "unknown")
            raise XApiError(f"rate limited by X; retry after unix time {reset}")
        if resp.status_code == 401:
            raise XApiError("X rejected the token (401) — reconnect with `agsoc auth x`")
        if resp.status_code >= 400:
            raise XApiError(f"X API error {resp.status_code}: {resp.text}")
        return resp.json()["data"]["id"]
