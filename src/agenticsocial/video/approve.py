"""The gate. Spec §8.4, §10 — `agsoc video approve`.

This is the one place the project spends its authority. Phase 5 can tell you a
claim is unsupported; nothing before this refuses to act on it.

**It takes identifiers, not objects (D-072).** `approve_episode(ws, series_slug,
ep_id)` loads the series, the episode and the ledger itself, immediately before
the transition, and there is no argument a caller can shape to change the
verdict. The standing rule exists because of D-059, the most serious defect this
project has found and one that shipped in v1: the gate was checked against an
in-memory object, a second writer stamped the gated value onto the draft, and
the closing transition then passed *legitimately*. The bypass laundered itself.

Two consequences of that, both visible here:

  * The only write is `episode.set_status`, which re-reads the value it gates on
    and performs the write in the same function. This module never touches the
    file.
  * The approval record goes in with the transition, in one write. Two writes
    means a crash between them, and an approved episode nobody signed.

**What it refuses on, and what it does not.** §8.4: any `fail`, `no_source` or
unattested `manual`. Entity misses are recorded, not gated (D-102: they would
refuse 62% of correct beats and not one measured miss was a real error). An
attested `manual` passes on a human's signed sentence (D-088). A `claim_override`
is recorded but not yet applied — Task 2 owns that, and until it lands a gate
that went quiet because someone wrote a sentence nobody consumed would be worse
than no gate at all.

**It requires a fresh ledger; it does not re-run `check`.** Argued in the Task 1
report. In short: the ledger is the artifact of record and the screen a human
read before signing, so approving against anything else means signing verdicts
nobody displayed — and a second way to produce verdicts is the D-059 shape again.
"""
from __future__ import annotations

from datetime import datetime

from ..models import Status
from ..workspace import Workspace
from . import verify as verify_mod
from .episode import beats_sha256, load_episode, set_status
from .series import load_series


class ApprovalRefused(Exception):
    """A refusal an operator can act on: why, and which claims if any.

    `kind` is `approver` · `ledger` · `claims`. R3 asks that a stale ledger be
    distinguishable from an open claim, and the distinction is not cosmetic: one
    is "re-run the check", the other is "fix the script". A single message the
    caller has to pattern-match would be one screen for two different problems.
    """

    def __init__(self, kind: str, message: str, claims: list[dict] | None = None):
        super().__init__(message)
        self.kind = kind
        self.claims = claims or []


def approve_episode(
    ws: Workspace,
    series_slug: str,
    ep_id: str,
    *,
    by: str,
    now: str | None = None,
) -> dict:
    """Approve one episode, or raise. Returns the record written to script.yaml.

    Order matters, and it is: identity, load, ledger, claims, transition. The
    loads happen after the cheap refusals so that a missing `--by` does not read
    a file, and immediately before the write so nothing can move underneath
    them.

    `ep_id` is matched exactly — `resolve_episode`'s substring matching is right
    for `review`, which shows you what it found, and wrong here, where the thing
    it might find is an approval of an episode you did not name.
    """
    approver = (by or "").strip()
    if not approver:
        raise ApprovalRefused(
            "approver",
            "an approval needs a name: pass `--by \"Your Name\"`. It is recorded "
            "in script.yaml and it is the only account of who spent this gate",
        )

    series = load_series(ws, series_slug)
    episode = load_episode(series, ep_id)

    ledger = verify_mod.read_ledger(episode)
    stale = verify_mod.stale_reason(episode, ledger)
    if stale:
        raise ApprovalRefused("ledger", stale)

    records = verify_mod.claim_records(ledger)
    blocked = verify_mod.open_claims(records)
    if blocked:
        raise ApprovalRefused(
            "claims",
            f"{len(blocked)} of {len(records)} claims are open",
            blocked,
        )

    record = {
        "by": approver,
        "at": now or datetime.now().astimezone().isoformat(timespec="seconds"),
        "script_sha256": beats_sha256(episode),
        # `script_sha256` covers the beats document only — see `beats_sha256`.
        # `pace` scales every hold and lives in the metadata document, so it is
        # recorded beside the digest rather than inside a claim it does not
        # cover.
        "pace": episode.meta.get("pace", 1.0),
        # What was approved, not merely that something was: the check's own
        # timestamp and the corpus it read. An approval that cannot name the
        # verification behind it is a signature on an unnamed document.
        "claims_checked_at": (ledger or {}).get("checked_at"),
        "corpus_sha": (ledger or {}).get("corpus_sha"),
        # Counted through `classify`, the same function that gated — so the
        # record cannot describe an episode the gate did not approve. An
        # attested claim is NOT verified: D-088, and D-112's overclaim.
        "claims": {
            "total": len(records),
            "verified": sum(1 for r in records if verify_mod.classify(r) == "verified"),
            "attested": sum(1 for r in records if verify_mod.classify(r) == "attested"),
        },
    }
    set_status(episode, Status.APPROVED, {"approval": record})
    return record
