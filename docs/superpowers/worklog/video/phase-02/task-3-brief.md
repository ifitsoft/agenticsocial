# Task 3 Brief: `agsoc video ingest`

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** Task 2
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Written under D-064: mutants first, every rule with its negative half, every test
with a precondition. Report the **passed-on-arrival count** — it is the
transcription rate.

## What this builds

The command that makes Phase 2 usable:

```
agsoc video ingest 2026-08-17 --series the-brief --paste workspace/inbox/brief.md
agsoc video ingest 2026-08-17 --series the-brief --research "gemini 3.7 pricing"
agsoc video ingest 2026-08-17 --series the-brief --from-source 2026-08-14-kill-staging
```

## The rules, each with its negative half

- **R1** Exactly one input mode is required. **Negative:** zero modes is an
  error naming the three; two modes is an error rather than a silent preference.
- **R2** Per-source failures are reported and the command still **succeeds** —
  a corpus with three of four sources is usable. **Negative:** if *nothing* was
  ingested, that is a failure and exits 1; a silent empty corpus is
  indistinguishable from one nobody ran.
- **R3** Every operator-typable input produces a clean error. **Negative:** no
  traceback, ever — including a missing paste file, a non-UTF-8 paste file, an
  unknown source id, and an unreadable output directory.
- **R4** The command reports what landed **and** what did not. **Negative:** it
  does not report only successes; the failure count is visible without opening
  `brief.md`.

## The mutants this task must kill

Derive the assertions from these, before writing them.

| # | Weaker implementation | What must notice |
|---|---|---|
| M1 | two input modes → silently prefers one | R1 negative |
| M2 | zero input modes → does nothing, exits 0 | R1 negative |
| M3 | `--paste` on a missing file → `FileNotFoundError` escapes | R3 |
| M4 | `--paste` on a latin-1 file → `UnicodeDecodeError` escapes | R3 negative |
| M5 | `IngestError` not caught → traceback | R3 |
| M6 | failures not printed; only the success count | R4 |
| M7 | exits 0 when `keys == []` | R2 negative |
| M8 | exits 1 whenever `failures` is non-empty | R2 |
| M9 | `--from-source` with an unknown id → `WorkspaceError` escapes | R3 |

**M7 and M8 are a matched pair and easy to get backwards.** Partial failure
succeeds; total failure fails.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 18 defects across four phases.
- **No network in any test.** Patch `ingest.ingest_research` at the module
  boundary; the CLI must never be the thing that reaches out in a unit test.
- Use `run(...)` from `tests/test_video_cli.py`'s existing helper —
  `catch_exceptions=False`, so a traceback fails the test rather than looking
  like a clean exit (D-035).
- Do not add dependencies. Never stage anything under `docs/`.

## Files

- Modify: `src/agenticsocial/video/cli.py`
- Test: `tests/test_video_cli.py` (append)

---

## Step 3 is sealed until your tests are committed

**Do not read Step 3 before committing Step 2.** Task 2's implementer named the
reason and I am acting on it:

> The pull to reconcile tests toward supplied code is real and I felt it.
> Committing tests first is what made resisting it structural rather than
> discretionary.

My briefs supply an implementation, which creates pressure to write assertions
that agree with it. That is the transcription mechanism (D-064) one level up. The
ordering is now a rule, not a suggestion.

Also changed, on the same report's advice: **the metric for a new module is the
mutation score, not passed-on-arrival.** Passed-on-arrival is 0 for anything that
does not exist yet, whether the tests are excellent or worthless — it only
discriminates against pre-existing code. Report both; weight the former.

---

- [ ] **Step 0: Four carried fixes from Task 2 (own commit, before anything else)**

**0a — a whitespace-only extract becomes a cited empty document.** Task 2's own
sweep found `if not text` where `if not text.strip()` was meant; same class as M6
and untested. In `ingest.py::ingest_research`, the guard is already
`if not text or not text.strip():` — **verify that, and if it is already correct,
say so and skip to 0b.**

**0b — `brief.md` is overwritten by every ingest while the corpus accumulates.**
Task 2's verdict, which I accept:

> The asymmetry is the tell — the corpus accumulates while the brief is
> truncated by whichever ingest ran last. Research-then-paste loses the record of
> three sources and the one that 403'd. The manifest already holds
> url/title/fetched_at for everything; a brief regenerated from it would be
> correct by construction.

Change `_brief` to build its "Sources in the corpus" section from
`C.read_manifest(episode)` rather than only the keys written in this call.
Failures stay per-run — they are not in the manifest. Add:

```python
def test_a_second_ingest_does_not_lose_the_first_from_the_brief(episode):
    """precondition: the corpus already contains blog-google from ingest #1.
    Kills the mutant that builds the brief from this call's keys only."""
    I.ingest_research(
        episode, "gemini",
        search=fake_search(RESULTS[:1]),
        extract=fake_extract({"https://blog.google/a": "article a"}),
    )
    res = I.ingest_paste(episode, "a pasted digest")
    brief = res.brief_path.read_text(encoding="utf-8")
    assert "blog-google" in brief
    assert "_pasted" in brief
```

**0c — the M7 survivor.** `test_documents_are_written_before_the_brief` asserts
`order[-1] == "brief.md"` but not that the brief is written *once*. A mutant that
writes a sourceless brief first and the real one last passes, leaving a
mid-run crash with a brief citing a corpus that does not exist. Append one line
to that test:

```python
    assert order.count("brief.md") == 1
```

**0d — `src-<id>` keys are unbounded.** `source.id` is `date + slugify(title)`,
and it becomes a filename, a manifest key, and a citation token. `episode.py`
caps ids with `MAX_ID_LEN` for exactly this reason. In `ingest_source`, truncate:

```python
    key = f"src-{source.id}"[:64]
```

and add:

```python
def test_a_long_source_id_produces_a_bounded_key(ws, episode):
    """precondition: corpus empty. Keys become filenames and citation tokens;
    episode ids are capped for the same reason and corpus keys were not."""
    src = ws.create_source("x" * 200, body="body")
    res = I.ingest_source(episode, src)
    assert len(res.keys[0]) <= 64
```

```bash
uv run pytest tests/test_video_ingest.py 2>&1 | tail -10
git add src/agenticsocial/video/ingest.py tests/test_video_ingest.py
git commit -m "fix: regenerate the brief from the manifest, bound source keys

Every ingest overwrote brief.md while the corpus accumulated, so a
research-then-paste run lost the record of what was fetched and what
403'd. The brief now builds its source list from the manifest, which is
correct by construction. Source keys are bounded like episode ids."
```

- [ ] **Step 1: Write the tests**

Append to `tests/test_video_cli.py`:

```python
# --- agsoc video ingest --------------------------------------------------------


@pytest.fixture()
def prepared(ws):
    """An episode ready to ingest into. precondition for every test below:
    the corpus is empty and brief.md does not exist."""
    run("series", "new", "the-brief", "--name", "The Brief")
    run("video", "new", "2026-08-17", "--series", "the-brief")
    return ws.series_dir / "the-brief" / "episodes" / "2026-08-17"


def test_ingest_requires_an_input_mode(prepared):
    """R1 negative. Kills M2 — doing nothing and exiting 0 is
    indistinguishable from success."""
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief")
    assert result.exit_code == 1
    for flag in ("--research", "--paste", "--from-source"):
        assert flag in result.output


def test_ingest_refuses_two_input_modes(prepared, tmp_path):
    """R1 negative. Kills M1 — silently preferring one hides which source the
    corpus actually came from, which is the one thing this phase exists to
    record."""
    f = tmp_path / "p.md"
    f.write_text("pasted", encoding="utf-8")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--paste", str(f), "--research", "gemini",
    )
    assert result.exit_code == 1
    assert "one" in result.output.lower()


def test_ingest_paste_writes_the_corpus(prepared, tmp_path):
    """precondition: corpus empty."""
    f = tmp_path / "p.md"
    f.write_text("the pasted digest", encoding="utf-8")
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--paste", str(f))
    assert result.exit_code == 0
    assert (prepared / "sources" / "_pasted.txt").read_text(encoding="utf-8") == (
        "the pasted digest"
    )
    assert (prepared / "brief.md").exists()


def test_ingest_paste_on_a_missing_file_is_a_clean_error(prepared, tmp_path):
    """R3. Kills M3."""
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--paste", str(tmp_path / "nope.md"),
    )
    assert result.exit_code == 1
    assert "nope.md" in result.output


def test_ingest_paste_on_a_non_utf8_file_is_a_clean_error(prepared, tmp_path):
    """R3 negative. Kills M4 — a cp1252-saved digest is the likeliest real
    input here, and it must not traceback."""
    f = tmp_path / "p.md"
    f.write_bytes(b"caf\xe9 pricing")
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--paste", str(f))
    assert result.exit_code == 1
    assert "UTF-8" in result.output


def test_ingest_reports_partial_failure_and_still_succeeds(prepared, monkeypatch):
    """R2. Kills M8 — a corpus with three of four sources is usable, and
    failing the command would throw the three away."""
    from agenticsocial.video import ingest as I

    def fake(episode, query, **kw):
        return I.IngestResult(
            ["blog-google"],
            [("https://venturebeat.com/b", "403 Forbidden")],
            episode.dir / "brief.md",
        )

    monkeypatch.setattr(I, "ingest_research", fake)
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 0
    assert "1" in result.output
    assert "venturebeat.com/b" in result.output      # R4: failures are visible
    assert "403" in result.output


def test_ingest_fails_when_nothing_was_ingested(prepared, monkeypatch):
    """R2 negative. Kills M7 — an empty corpus that exits 0 looks exactly like
    a successful run to any script that checks the exit code."""
    from agenticsocial.video import ingest as I

    def fake(episode, query, **kw):
        return I.IngestResult([], [("https://x/y", "403")], episode.dir / "brief.md")

    monkeypatch.setattr(I, "ingest_research", fake)
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 1


def test_ingest_surfaces_a_search_failure_cleanly(prepared, monkeypatch):
    """R3. Kills M5."""
    from agenticsocial.video import ingest as I

    def boom(episode, query, **kw):
        raise I.IngestError("search failed: connection refused")

    monkeypatch.setattr(I, "ingest_research", boom)
    result = run("video", "ingest", "2026-08-17", "--series", "the-brief", "--research", "x")
    assert result.exit_code == 1
    assert "connection refused" in result.output


def test_ingest_from_an_unknown_source_is_a_clean_error(prepared):
    """R3. Kills M9."""
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief", "--from-source", "nope"
    )
    assert result.exit_code == 1
    assert "nope" in result.output


def test_ingest_from_an_existing_source(prepared, ws):
    """precondition: corpus empty; the source exists with a non-empty body."""
    ws.create_source("Kill staging", body="the original reasoning", created="2026-08-14")
    result = run(
        "video", "ingest", "2026-08-17", "--series", "the-brief",
        "--from-source", "kill-staging",
    )
    assert result.exit_code == 0
    assert any((prepared / "sources").glob("*.txt"))


def test_ingest_into_an_unknown_episode_is_a_clean_error(ws):
    run("series", "new", "the-brief")
    result = run(
        "video", "ingest", "1999-01-01", "--series", "the-brief", "--research", "x"
    )
    assert result.exit_code == 1
    assert "agsoc video new" in result.output
```

- [ ] **Step 2: Run, record passed-on-arrival, commit**

```bash
uv run pytest tests/test_video_cli.py 2>&1 | tail -15
git add tests/test_video_cli.py
git commit -m "test: specify agsoc video ingest and its error surface"
```

- [ ] **Step 3: Implement**

In `src/agenticsocial/video/cli.py`, add the imports and the command:

```python
from . import ingest as ingest_mod
```

```python
@video_app.command("ingest")
def video_ingest(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
    research: Optional[str] = typer.Option(None, "--research", help="search query"),
    paste: Optional[Path] = typer.Option(None, "--paste", help="file whose text becomes the corpus"),
    from_source: Optional[str] = typer.Option(None, "--from-source", help="an existing agsoc source id"),
) -> None:
    """Build this episode's verification corpus from research, a paste, or a source."""
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")

    modes = [m for m in (research, paste, from_source) if m is not None]
    if not modes:
        raise _fail(
            "nothing to ingest — pass one of --research \"<query>\", "
            "--paste <file>, or --from-source <id>"
        )
    if len(modes) > 1:
        raise _fail("pass exactly one of --research, --paste or --from-source")

    try:
        s = load_series(ws, series)
        ep = load_episode(s, episode)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))

    try:
        if research is not None:
            result = ingest_mod.ingest_research(ep, _text(research, "The query"))
        elif paste is not None:
            try:
                text = paste.read_text(encoding="utf-8")
            except FileNotFoundError:
                raise _fail(f"cannot read --paste {paste}: no such file")
            except UnicodeDecodeError:
                raise _fail(
                    f"cannot read --paste {paste}: the file is not valid UTF-8. "
                    "Re-save it as UTF-8."
                )
            except OSError as e:
                raise _fail(f"cannot read --paste {paste}: {e}")
            result = ingest_mod.ingest_paste(ep, text)
        else:
            try:
                src = ws.resolve_source(from_source)
            except WorkspaceError as e:
                raise _fail(str(e))
            result = ingest_mod.ingest_source(ep, src)
    except ingest_mod.IngestError as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot write the corpus: {e}")

    for url, reason in result.failures:
        typer.secho(f"  failed: {url or '(pasted)'} — {reason}", fg=typer.colors.YELLOW)

    if not result.keys:
        raise _fail(
            f"nothing was ingested ({len(result.failures)} failed) — "
            f"see {result.brief_path}"
        )

    typer.echo(
        f"ingested {len(result.keys)} source(s), {len(result.failures)} failed → "
        f"{result.brief_path}"
    )
    typer.echo(f"next: draft beats into {ep.script_path}")
```

`raise _fail(...)` inside a `try` that catches `OSError` is safe — `typer.Exit`
is not an `OSError` — but **verify that rather than trusting me**; if `typer.Exit`
is being swallowed anywhere, that is a finding.

Import `WorkspaceError` and `Path` at the top of `cli.py` if not already present.

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/cli.py
git commit -m "feat: add agsoc video ingest

Exactly one input mode is required -- silently preferring one would hide
where the corpus came from, which is what this phase exists to record.
Partial failure still succeeds and prints what failed; a wholly empty
corpus exits 1, since exiting 0 would be indistinguishable from success."
```

- [ ] **Step 5: Kill the nine mutants**, then your own sweep.

- [ ] **Step 6: Real end-to-end, no stubs**

```bash
export AGSOC_WORKSPACE=/tmp/ing/workspace && rm -rf /tmp/ing
uv run agsoc init /tmp/ing/workspace && uv run agsoc series new the-brief --name "The Brief"
uv run agsoc video new 2026-08-17 --series the-brief
printf 'Gemini 3.7 Flash costs $0.75 per 1M input tokens.\nDeepSeek raised prices by 1,100%%.\n' > /tmp/ing/paste.md
uv run agsoc video ingest 2026-08-17 --series the-brief --paste /tmp/ing/paste.md
echo "--- corpus ---" && ls /tmp/ing/workspace/series/the-brief/episodes/2026-08-17/sources/
echo "--- manifest ---" && cat /tmp/ing/workspace/series/the-brief/episodes/2026-08-17/sources/_manifest.json
echo "--- brief ---" && cat /tmp/ing/workspace/series/the-brief/episodes/2026-08-17/brief.md
```

Paste all of it.

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-3-report.md`:

1. **What I implemented.**
2. **TDD evidence** — RED (piped), GREEN, and the **passed-on-arrival count**.
3. **Mutation results** for all nine, plus your own sweep.
4. **Step 6's real run**, pasted in full.
5. **Files changed**, both commit SHAs.
6. **Issues or concerns**, including:
   - Anything an operator can type at `agsoc video ingest` that still tracebacks.
   - `--research` reaches the real network when run for real. Is the failure
     surface right when there is no connection at all?
   - Did this brief's tests read as derived-from-mutants or as transcriptions?
