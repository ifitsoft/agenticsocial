from agenticsocial import frontmatter


def test_parse_splits_meta_and_body():
    text = "---\nplatform: x\nstatus: draft\n---\nHello world\n"
    meta, body = frontmatter.parse(text)
    assert meta == {"platform": "x", "status": "draft"}
    assert body == "Hello world\n"


def test_parse_without_frontmatter_returns_empty_meta():
    meta, body = frontmatter.parse("just text\n")
    assert meta == {}
    assert body == "just text\n"


def test_parse_unclosed_frontmatter_treated_as_body():
    text = "---\nbroken: yes\nno closing delimiter\n"
    meta, body = frontmatter.parse(text)
    assert meta == {}
    assert body == text


def test_roundtrip_preserves_meta_and_body():
    meta = {"platform": "x", "status": "draft", "posted_ids": [], "posted_url": None}
    body = "Tweet one\n\n---tweet---\n\nTweet two\n"
    meta2, body2 = frontmatter.parse(frontmatter.dump(meta, body))
    assert meta2 == meta
    assert body2 == body


def test_dump_preserves_key_order():
    meta = {"z": 1, "a": 2}
    assert frontmatter.dump(meta, "").index("z:") < frontmatter.dump(meta, "").index("a:")


def test_parse_malformed_yaml_degrades_to_body():
    text = "---\nstatus: [draft\n---\nbody\n"
    assert frontmatter.parse(text) == ({}, text)


def test_parse_non_dict_yaml_degrades_to_body():
    text = "---\n- a\n- b\n---\nbody\n"
    assert frontmatter.parse(text) == ({}, text)
