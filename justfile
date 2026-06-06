# pi-agent-events-pydantic — pipeline: pinned pi TS types -> JSON Schema -> Pydantic v2.
#
# The Python lib (repo root) is the primary artifact. The JS schema generator
# lives in tools/schema-gen and exists only to emit the shared handoff artifact
# schema/agent-session.schema.json, which the Python codegen then consumes.

# List available recipes.
default:
    @just --list

# Install both toolchains (JS schema-gen + Python lib).
install:
    cd tools/schema-gen && npm install
    uv sync

# Step 1: pinned pi TS types -> schema/agent-session.schema.json
schema:
    cd tools/schema-gen && npm run --silent schema

# Step 2: schema -> src/pi_agent_events/models.py (naive; anonymous names for now)
models:
    uv run datamodel-codegen \
      --input schema/agent-session.schema.json \
      --input-file-type jsonschema \
      --output-model-type pydantic_v2.BaseModel \
      --disable-timestamp \
      --output src/pi_agent_events/models.py

# Full pipeline: regenerate schema, then models.
gen: schema models

# Typecheck the TS re-export (proves AgentSessionEvent resolves through index.ts).
typecheck:
    cd tools/schema-gen && npm run --silent typecheck
