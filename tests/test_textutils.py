from agenticsocial.textutils import (
    TWEET_LIMIT,
    URL_WEIGHT,
    slugify,
    split_thread,
    weighted_length,
)


def test_slugify_basic():
    assert slugify("The Staging Environment is a LIE!") == "the-staging-environment-is-a-lie"


def test_slugify_truncates_and_never_empty():
    assert len(slugify("x " * 100)) <= 60
    assert slugify("!!!") == "untitled"


def test_split_thread_on_delimiter():
    body = "Tweet one\n\n---tweet---\n\nTweet two\n\n---tweet---\nTweet three"
    assert split_thread(body) == ["Tweet one", "Tweet two", "Tweet three"]


def test_split_thread_single_tweet():
    assert split_thread("Just one post\n") == ["Just one post"]


def test_split_thread_ignores_empty_segments():
    assert split_thread("A\n\n---tweet---\n\n\n---tweet---\n\nB") == ["A", "B"]


def test_weighted_length_plain_text():
    assert weighted_length("hello") == 5


def test_weighted_length_counts_urls_as_23():
    text = "read this: https://example.com/a-very-long-path-that-goes-on-forever"
    assert weighted_length(text) == len("read this: ") + URL_WEIGHT


def test_tweet_limit_constant():
    assert TWEET_LIMIT == 280
