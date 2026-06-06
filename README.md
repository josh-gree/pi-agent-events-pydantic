# pi-agent-events-pydantic

Typed **Pydantic v2** models for the event stream `pi --mode rpc` writes to
stdout — generated from pi's own TypeScript types, pinned to a fixed pi version.

The wire type is pi-coding-agent's **`AgentSessionEvent`**: a `RootModel` union of
every event pi emits (`agent_start`, `message_update`, `tool_execution_*`,
`agent_end`, the session-level `compaction_*`/`auto_retry_*`/…). There are no
published Python types, so rather than hand-maintain models that silently drift,
we generate them.

## Use

```python
from pi_agent_events import AgentSessionEvent

evt = AgentSessionEvent.model_validate_json(line).root   # one stdout line
# evt is the concrete event, e.g. AgentEndEvent / ToolExecutionStartEvent
```

`AgentSessionEvent` is the single public type; the concrete variant classes (for
`isinstance` / annotations) live in `pi_agent_events.models`.

## How it's generated

```
tools/schema-gen/index.ts          re-exports pi's AgentSessionEvent
   │  ts-json-schema-generator
   ▼
schema/agent-session.schema.json   raw JSON Schema (committed)
   │  tools/patch_schema.py         stable names from the `type` discriminant;
   │                                drop additionalProperties:false (pi emits
   │                                fields its own types omit)
   ▼
src/pi_agent_events/models.py       Pydantic v2 (committed; do not hand-edit)
```

The pinned pi version lives in `tools/schema-gen/package.json` (the three
`@earendil-works` packages, currently **0.78.1**). To bump pi: change the pins,
`just gen`, review the diff, run `just test`.

## Tasks

```bash
just install   # JS schema-gen + Python lib toolchains
just gen       # regenerate schema + models from the pinned pi types
just test      # parse the captured session fixture through the models
```
