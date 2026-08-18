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
clears **exactly the claim it names** — a fourth state in `classify`, never a
fourth code path — and the approval record names every claim it carried, so the
bypass is as visible in the artifact as §8.4 demands it be in `script.yaml`.

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
from .episode import (
    EpisodeError,
    beats_sha256,
    load_episode,
    read_script,
    set_status,
)
from .models import Episode
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
        # attested claim is NOT verified (D-088, and D-112's overclaim), and
        # neither is one a person cleared by hand.
        "claims": verify_mod.claim_tally(records),
    }
    # §8.4's accountability, carried into the diff a human commits. The count
    # says how many sentences were spent; only this says WHICH claims are
    # standing on a person rather than on a source, and under whose name.
    # Absent when there are none: an empty list in every approval is noise, and
    # noise is what this has to cut through the one time it matters (D-040).
    cleared = _cleared_by_hand(records)
    if cleared:
        record["overrides"] = cleared
    set_status(episode, Status.APPROVED, {"approval": record})
    return record


def _cleared_by_hand(records: list[dict]) -> list[dict]:
    """Every claim §8.4's bypass carried, named with its sentence and its author.

    Read through `classify` and `override_state`, never from the raw field: the
    list in the approval record must be exactly the set of claims the gate
    cleared this way, and a second reading of the same field is where the two
    would disagree.
    """
    out = []
    for record in records:
        if verify_mod.classify(record) != "overridden":
            continue
        written, _ = verify_mod.override_state(record)
        out.append(
            {
                "id": record.get("id"),
                "by": (written or {}).get("by"),
                "reason": (written or {}).get("reason"),
            }
        )
    return out


# --- §10: an approval that stopped being true ---------------------------------------


def approval_record(episode: Episode) -> dict | None:
    """The approval written into `script.yaml`, read from DISK, or None.

    Read here rather than from `episode.meta` for the same reason `set_status`
    re-reads the status it gates on: a caller holding an object loaded before an
    edit must not be able to answer a question about the file with a snapshot of
    what the file used to say.
    """
    try:
        meta, _, _ = read_script(episode.script_path)
    except EpisodeError:
        return None
    record = meta.get("approval")
    return record if isinstance(record, dict) else None


def approval_drift(episode: Episode) -> str | None:
    """Why this approval no longer describes the script on disk, or None. §10.

        > `approve` records `script_sha256`, and `render` refuses if the script
        > has changed since approval, **naming the drift.**

    This is the refusal, as a check. `render` is Phase 8 and will call it; a
    stubbed command would be a second place the rule lives before it has a
    caller. `check` and `review` already print it, because an approval that
    stopped being true is otherwise visible to nothing until the expensive step
    §10 wrote the rule to protect.

    **Two comparisons, because one digest cannot cover both documents.**

      * `script_sha256` is the BEATS document's bytes — see `beats_sha256` for
        why it cannot be the whole file: the approval record is written *into*
        the bytes a whole-file digest would cover, so it has no fixed point, and
        `approved → rendering` would then invalidate the approval it is acting
        on. The cost of that choice is that the metadata document is outside the
        hash, which is why the second comparison exists.
      * `pace` multiplies every hold, and it lives in the metadata document.
        `approve` records it beside the digest rather than pretending the hash
        covered it, and this reads it back.

    **What the digest catches that nothing else can**: an edit that changes no
    number. A chart's `scale` shifts every bar on the frame while every claim
    still verifies, the corpus never moved, and `stale_reason` correctly answers
    "this ledger is current". `corpus_sha` cannot see it. A numeric check cannot
    see it. Phase 5 named this gap and this is the answer to it.

    **It fails closed.** No approval, an unreadable file, a script with no beats
    document: all drift. A caller that reads `None` as "fine" must never get one
    for a question this could not answer.
    """
    record = approval_record(episode)
    if record is None:
        return (
            "no approval on record — nothing in script.yaml says these bytes "
            "were ever signed. Run `agsoc video approve`"
        )
    try:
        meta, _, _ = read_script(episode.script_path)
        current = beats_sha256(episode)
    except EpisodeError as e:
        return f"the script can no longer be hashed, so nothing can be compared — {e}"

    moved: list[str] = []
    signed = record.get("script_sha256")
    if signed != current:
        moved.append(
            f"the beats document has changed: the approval covers sha256 "
            f"{signed}, the file on disk is sha256 {current}"
        )
    signed_pace = record.get("pace")
    pace = meta.get("pace", 1.0)
    if signed_pace != pace:
        moved.append(
            f"`pace` has changed from {signed_pace} to {pace}, and pace "
            "multiplies every hold, so every beat's timing moved"
        )
    if not moved:
        return None
    return (
        f"{'; and '.join(moved)} — approved by {record.get('by')} at "
        f"{record.get('at')}. Re-run `agsoc video check` and approve again, or "
        "put the script back"
    )
