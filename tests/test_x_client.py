import httpx
import pytest
import respx

from agenticsocial.x.client import API_URL, XApiError, XClient


@respx.mock
def test_post_tweet_returns_id():
    route = respx.post(API_URL).mock(
        return_value=httpx.Response(201, json={"data": {"id": "111", "text": "hello"}})
    )
    client = XClient("tok")
    assert client.post_tweet("hello") == "111"
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer tok"
    assert b'"text": "hello"' in sent.content or b'"text":"hello"' in sent.content


@respx.mock
def test_post_tweet_chains_replies():
    route = respx.post(API_URL).mock(
        return_value=httpx.Response(201, json={"data": {"id": "222", "text": "t"}})
    )
    XClient("tok").post_tweet("t", in_reply_to="111")
    assert b'"in_reply_to_tweet_id"' in route.calls.last.request.content


@respx.mock
def test_rate_limit_error_mentions_reset():
    respx.post(API_URL).mock(
        return_value=httpx.Response(429, headers={"x-rate-limit-reset": "1789300000"}, json={})
    )
    with pytest.raises(XApiError, match="1789300000"):
        XClient("tok").post_tweet("t")


@respx.mock
def test_unauthorized_error_suggests_auth():
    respx.post(API_URL).mock(return_value=httpx.Response(401, json={}))
    with pytest.raises(XApiError, match="agsoc auth x"):
        XClient("tok").post_tweet("t")
