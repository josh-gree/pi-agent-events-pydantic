# pi-agent-events-pydantic — pipeline: pinned pi TS types -> JSON Schema -> Pydantic v2.
#
# The Python lib (repo root) is the primary artifact. The JS schema generator
# lives in tools/schema-gen and exists only to emit the shared handoff artifact
# schema/pi-rpc.schema.json, which the Python codegen then consumes.

# List available recipes.
default:
    @just --list

# Install both toolchains (JS schema-gen + Python lib).
install:
    cd tools/schema-gen && npm install
    uv sync

# Step 1: pinned pi TS types -> schema/pi-rpc.schema.json (raw, committed)
schema:
    cd tools/schema-gen && npm run --silent schema

# Step 2: inject stable class-name titles -> build/patched.schema.json (derived)
patch:
    mkdir -p build
    uv run python tools/patch_schema.py schema/pi-rpc.schema.json build/patched.schema.json

# Step 3: patched schema -> src/pi_agent_events/models.py (stable names via titles)
models: patch
    uv run datamodel-codegen \
      --input build/patched.schema.json \
      --input-file-type jsonschema \
      --output-model-type pydantic_v2.BaseModel \
      --use-title-as-name \
      --collapse-root-models \
      --class-name _RpcSchema \
      --disable-timestamp \
      --output src/pi_agent_events/models.py

# Full pipeline: regenerate schema, then patch + models.
gen: schema models

# Typecheck the TS re-export (proves AgentSessionEvent resolves through index.ts).
typecheck:
    cd tools/schema-gen && npm run --silent typecheck

# Run the unit suite (offline; parses the committed fixture through the models).
test:
    uv run pytest -q -m "not integration"

# Run the live integration test: drive a real `pi --no-extensions --mode rpc`
# session and parse it (needs pi on PATH + auth; makes a real model call).
test-live:
    PI_RPC_LIVE=1 uv run pytest -q -m integration
