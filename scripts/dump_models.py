"""Parse a captured session and dump the collected Pydantic models to a file.

Reads a session JSONL, validates every non-envelope line into its concrete
AgentSessionEvent model, and writes the parsed models back out as normalized
JSONL — one object per line: {"model": "<ClassName>", "data": <model_dump>}.
RPC envelopes (response / extension_ui_request) are skipped (out of scope).

    python scripts/dump_models.py sessions/local.jsonl sessions/local.parsed.jsonl

The output is the *validated, typed* view: it round-trips through the models, so
fields the models declare are normalized and any wire-only extras (e.g.
partialArgs) are preserved via extra="allow".
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pi_agent_events import parse_agent_event  # noqa: E402

ENVELOPE_TYPES = {"response", "extension_ui_request"}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: dump_models.py <session.jsonl> <out.jsonl>", file=sys.stderr)
        return 2
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    lines = [ln for ln in src.read_text().splitlines() if ln.strip()]

    counts: Counter[str] = Counter()
    skipped = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w") as out:
        for line in lines:
            obj = json.loads(line)
            if obj.get("type") in ENVELOPE_TYPES:
                skipped += 1
                continue
            evt = parse_agent_event(obj)  # -> concrete model
            counts[type(evt).__name__] += 1
            record = {"model": type(evt).__name__, "data": evt.model_dump(mode="json")}
            out.write(json.dumps(record) + "\n")

    total = sum(counts.values())
    print(f"parsed {total} events ({skipped} envelopes skipped) -> {dst}")
    for name, n in counts.most_common():
        print(f"  {n:3d}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
