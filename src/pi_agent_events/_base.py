"""Base class injected into the generated models.

Policy: `extra="allow"` — runtime parsing is resilient and never crashes on a
field the pinned models don't declare (pi's stdout is known to carry fields its
own types omit; see README "The pi wire-vs-types gap"). Resilience at runtime;
drift is caught in CI instead, by scripts/check_session.py, which fails when an
*unexpected* unmodeled field appears (anything outside the documented
KNOWN_WIRE_EXTRAS allowlist).

`extra="allow"` (not the Pydantic default `ignore`) is deliberate: it keeps
unknown fields in `model_extra` so the CI audit can *see* them.

protected_namespaces=() silences the warning on pi's `model` field.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AllowExtra(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())
