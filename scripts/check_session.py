"""Replay a captured pi session and act as the drift CI gate.

Policy (chosen): models are extra="allow", so parsing never crashes. Drift is
caught HERE instead: every agent event is validated, and we audit each parsed
model for fields present on the wire that the pinned models don't declare
(Pydantic's model_extra). Such a field FAILS the check — UNLESS it is:
  * inside a free-form `arguments` mapping (Record<string, any> — keys are data), or
  * in KNOWN_WIRE_EXTRAS: fields pi is known to emit but not type at the pinned
    version (a pi type/impl gap, documented in the README). New ones beyond this
    list are real drift and fail.

    python scripts/check_session.py sessions/local.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydantic import BaseModel, ValidationError  # noqa: E402

from pi_agent_events import parse_agent_event  # noqa: E402

ENVELOPE_TYPES = {"response", "extension_ui_request"}

# Fields pi emits on stdout but does NOT declare in its TypeScript types at the
# pinned version (verified absent from the .d.ts). Acknowledged here so they
# don't trip the gate; any field NOT in this set is treated as real drift.
# Re-verify (and trim) when bumping the pin. See README "The pi wire-vs-types gap".
KNOWN_WIRE_EXTRAS = {
    # NOTE: willRetry is no longer here — it's a typed field on AgentEndEvent /
    # CompactionEndEvent now that we generate from AgentSessionEvent.
    "partialArgs",   # on tool-call content blocks (streaming partials)
    "streamIndex",   # on tool-call content blocks (streaming partials)
}


def unmodeled_leaves(m, path: str = "") -> list[tuple[str, str]]:
    """(leaf_name, full_path) for every wire field our models didn't declare."""
    out: list[tuple[str, str]] = []
    if isinstance(m, BaseModel):
        for k in (m.model_extra or {}):
            out.append((k, f"{path}.{k}".lstrip(".")))
        for name in m.__class__.model_fields:
            out += unmodeled_leaves(getattr(m, name), f"{path}.{name}".lstrip("."))
    elif isinstance(m, list):
        for x in m:
            out += unmodeled_leaves(x, path + "[]")
    return out


def classify(leaf: str, full_path: str) -> str:
    if ".arguments." in full_path or full_path.endswith(".arguments"):
        return "expected"          # free-form Record<string, any>
    if leaf in KNOWN_WIRE_EXTRAS:
        return "known"             # documented pi type gap
    return "drift"                 # NEW — fails the gate


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_session.py <session.jsonl>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]

    envelopes: Counter[str] = Counter()
    events: Counter[str] = Counter()
    known: Counter[str] = Counter()
    drift: Counter[str] = Counter()
    failures: list[tuple[int, str, str]] = []

    for n, line in enumerate(lines, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            failures.append((n, "<json>", str(e)))
            continue
        t = obj.get("type")
        if t in ENVELOPE_TYPES:
            envelopes[t] += 1
            continue
        try:
            evt = parse_agent_event(obj)
        except ValidationError as e:
            failures.append((n, str(t), repr(e.errors(include_url=False)[:1])))
            continue
        events[type(evt).__name__] += 1
        for leaf, full in unmodeled_leaves(evt):
            kind = classify(leaf, full)
            if kind == "known":
                known[leaf] += 1
            elif kind == "drift":
                drift[leaf] += 1

    total, n_env, n_evt = len(lines), sum(envelopes.values()), sum(events.values())
    print(f"session: {path}  ({total} lines)")
    print(f"  RPC envelopes : {n_env}  {dict(envelopes)}")
    print(f"  agent events  : {n_evt}")
    for name, count in events.most_common():
        print(f"      {count:3d}  {name}")
    if known:
        print(f"  known pi wire-only fields (allowlisted): {dict(known)}")

    status = 0
    if failures:
        print(f"\n  VALIDATION FAILED on {len(failures)} line(s):")
        for n, t, detail in failures[:10]:
            print(f"      line {n} type={t}: {detail}")
        status = 1
    if drift:
        print(f"\n  DRIFT — unmodeled fields NOT in the allowlist:")
        for leaf, count in drift.most_common():
            print(f"      {count:3d}  {leaf}")
        print("  -> investigate: add to KNOWN_WIRE_EXTRAS (pi type gap) or fix the pin/models.")
        status = 1
    if status == 0:
        print(f"\n  OK — {n_evt} events parsed; only expected/known extras present.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
