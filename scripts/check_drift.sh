#!/usr/bin/env bash
# Drift guard: regenerate schema + models from the pinned pi version and fail if
# the committed artifacts differ. Run in CI after `npm ci` + venv setup.
set -euo pipefail
cd "$(dirname "$0")/.."

TMP="$(mktemp -d)"
cp schema/agent-event.schema.json "$TMP/schema.before"
cp src/pi_agent_events/models.py "$TMP/models.before"

bash scripts/generate.sh >/dev/null

status=0
if ! diff -q "$TMP/schema.before" schema/agent-event.schema.json >/dev/null; then
  echo "DRIFT: schema/agent-event.schema.json changed — commit the regenerated schema."
  diff "$TMP/schema.before" schema/agent-event.schema.json || true
  status=1
fi
if ! diff -q "$TMP/models.before" src/pi_agent_events/models.py >/dev/null; then
  echo "DRIFT: src/pi_agent_events/models.py changed — commit the regenerated models."
  diff "$TMP/models.before" src/pi_agent_events/models.py || true
  status=1
fi

[ "$status" -eq 0 ] && echo "no drift: committed artifacts match generation from pinned pi."
exit "$status"
