#!/usr/bin/env bash
# Full generation pipeline: pinned pi TS types -> JSON Schema -> Pydantic v2.
#
#   TS .d.ts (node_modules, pinned)
#     -> ts-json-schema-generator  -> schema/agent-event.schema.json   (raw, committed)
#     -> scripts/patch_schema.py   -> $TMP/patched.schema.json         (names + extra policy)
#     -> datamodel-codegen         -> src/pi_agent_events/models.py    (committed)
#
# Run from the repo root. Requires `npm install` and the .venv (see README).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
CODEGEN=".venv/bin/datamodel-codegen"
RAW="schema/agent-event.schema.json"
# Stable path (not mktemp): datamodel-codegen embeds the input filename in the
# generated header, so a random name would defeat the drift guard.
PATCHED="build/patched.schema.json"
OUT="src/pi_agent_events/models.py"
mkdir -p build

echo "[1/3] TS -> JSON Schema (ts-json-schema-generator)"
npm run --silent schema

echo "[2/3] patch schema (names + forward-compat extra policy)"
"$PY" scripts/patch_schema.py "$RAW" "$PATCHED"

echo "[3/3] JSON Schema -> Pydantic v2 (datamodel-codegen)"
"$CODEGEN" \
  --input "$PATCHED" \
  --input-file-type jsonschema \
  --output-model-type pydantic_v2.BaseModel \
  --class-name AgentSessionEvent \
  --target-python-version 3.10 \
  --base-class pi_agent_events._base.AllowExtra \
  --use-title-as-name \
  --use-annotated \
  --enum-field-as-literal all \
  --collapse-root-models \
  --use-schema-description \
  --disable-timestamp \
  --formatters black isort \
  --output "$OUT"

echo "done -> $OUT"
