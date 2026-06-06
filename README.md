# pi-agent-events-pydantic

Typed **Pydantic v2** models for the slice of `pi --no-extensions --mode rpc` we
use — generated from pi's own TypeScript types, pinned to a fixed pi version.

There are no published Python types, so rather than hand-maintain models that
silently drift on a pi bump, we generate them. Three roots model the wire:

| Root | Direction | What |
|---|---|---|
| `AgentSessionEvent` | stdout | async event stream (`agent_start`, `message_update`, `tool_execution_*`, `agent_end`, session-level `compaction_*`/`auto_retry_*`/…) |
| `PromptResponse` | stdout | synchronous ack for a prompt command, correlated by `id` |
| `PromptCommand` | stdin | the command that drives the agent |

Deliberately minimal: pi's other ~28 commands, its generic command responses, and
the whole model/provider descriptor are out of scope — `PromptCommand` /
`PromptResponse` are derived (`Extract`) from pi's `RpcCommand` / `RpcResponse`
unions so they stay tied to pi's real types without dragging the rest in. The
extension-UI types never appear under `--no-extensions`.

## Use

Reading stdout — validate a line, then read `.root` for the concrete event:

```python
from pi_agent_events import AgentSessionEvent, PromptResponse

evt = AgentSessionEvent.model_validate_json(line).root   # e.g. AgentEndEvent
ack = PromptResponse.model_validate_json(line)           # command="prompt", success=True
```

Driving over stdin — construct a prompt and serialize it:

```python
from pi_agent_events import PromptCommand

proc.stdin.write(PromptCommand(type="prompt", id="1", message="hi").model_dump_json() + "\n")
```

The concrete event variant classes (for `isinstance` / annotations) live in
`pi_agent_events.models`.

## How it's generated

```
tools/schema-gen/index.ts      re-exports AgentSessionEvent; derives PromptCommand/PromptResponse
   │  ts-json-schema-generator  (--type '*')
   ▼
schema/pi-rpc.schema.json       raw JSON Schema (committed)
   │  tools/patch_schema.py      stable names from each event's `type` discriminant;
   │                             drop additionalProperties:false (pi emits fields
   │                             its own types omit)
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
just test      # parse the captured session fixture; exercise the prompt command
```
