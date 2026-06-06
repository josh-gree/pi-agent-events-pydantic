# pi-agent-events-pydantic

Typed **Pydantic v2** models for the full `pi --no-extensions --mode rpc`
contract — both directions of the stream — generated from pi's own TypeScript
types, pinned to a fixed pi version.

There are no published Python types, so rather than hand-maintain models that
silently drift on a pi bump, we generate them. Three `RootModel` union roots
model the wire:

| Root | Direction | What |
|---|---|---|
| `AgentSessionEvent` | stdout | async event stream (`agent_start`, `message_update`, `tool_execution_*`, `agent_end`, session-level `compaction_*`/`auto_retry_*`/…) |
| `RpcResponse` | stdout | synchronous reply to each command, correlated by `id` |
| `RpcCommand` | stdin | commands that drive the agent (`prompt`, `steer`, `abort`, …) |

The extension-UI request/response types are intentionally omitted: with
`--no-extensions` they never appear on the wire.

## Use

Reading stdout — validate a line, then read `.root` for the concrete model:

```python
from pi_agent_events import AgentSessionEvent, RpcResponse

evt  = AgentSessionEvent.model_validate_json(line).root   # e.g. AgentEndEvent
resp = RpcResponse.model_validate_json(line).root         # e.g. PromptResponse
```

Driving over stdin — construct a concrete command and serialize it:

```python
from pi_agent_events.models import PromptCommand

proc.stdin.write(PromptCommand(type="prompt", id="1", message="hi").model_dump_json() + "\n")
```

The three roots are the public API; the concrete variant classes — events and
responses (for `isinstance` narrowing) and the commands you send — live in
`pi_agent_events.models`.

## How it's generated

```
tools/schema-gen/index.ts      re-exports AgentSessionEvent + RpcCommand + RpcResponse
   │  ts-json-schema-generator  (--type '*')
   ▼
schema/pi-rpc.schema.json       raw JSON Schema (committed)
   │  tools/patch_schema.py      stable names from each union's discriminant
   │                             (type / command); name response payloads; rename
   │                             Model<any>; drop additionalProperties:false
   │                             (pi emits fields its own types omit)
   ▼
src/pi_agent_events/models.py   Pydantic v2 (committed; do not hand-edit)
```

The pinned pi version lives in `tools/schema-gen/package.json` (the three
`@earendil-works` packages, currently **0.78.1**). To bump pi: change the pins,
`just gen`, review the diff, run `just test`.

## Tasks

```bash
just install   # JS schema-gen + Python lib toolchains
just gen       # regenerate schema + models from the pinned pi types
just test      # parse the captured session fixture; exercise commands/responses
```
