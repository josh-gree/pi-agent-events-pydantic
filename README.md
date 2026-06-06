# pi-agent-events-pydantic

Generate **Pydantic v2 models** for the event stream `pi --mode rpc` writes to
stdout — straight from pi's own TypeScript types, **pinned to a fixed pi
version**, with a drift guard so the generated code stays honest.

This is the automated realization of the generation pipeline sketched in
`../pi-agent-explore/PORTING-TO-PYTHON.md`.

## Why this type, specifically

The events on the wire are pi-coding-agent's **`AgentSessionEvent`**, *not*
pi-agent-core's `AgentEvent`. `AgentSessionEvent` is a superset: it overrides
`agent_end` to add `willRetry`, and adds session-level events (`queue_update`,
`compaction_start`/`compaction_end`, `auto_retry_start`/`auto_retry_end`,
`session_info_changed`, `thinking_level_changed`). Generating from `AgentEvent`
(the obvious-looking choice — it's what `rpc-mode.js` imports for *commands*)
silently misses all of that. `rpc-mode.js` even says so in a comment: *"Events:
AgentSessionEvent objects streamed as they occur."*

These types are authored in TypeScript across `@earendil-works/pi-coding-agent`
(the `AgentSessionEvent` root), `pi-agent-core` (the core event tree,
`AgentMessage`), and `pi-ai` (content blocks, `Model`). There are no published
Python types — so rather than hand-maintain Pydantic that silently drifts on a pi
bump, we **generate** from the pinned `.d.ts` and **diff on every change**.

## Pipeline

```
node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.d.ts  (pinned)
   │  ts-json-schema-generator   (--type AgentSessionEvent, follows imports
   │                              into pi-agent-core + pi-ai)
   ▼
schema/agent-event.schema.json   (raw, committed)
   │  scripts/patch_schema.py     (rename mangled Exclude<…> def → CoreAgentEvent;
   │                               title union variants → stable names;
   │                               drop additionalProperties:false → extra=allow)
   ▼
<patched schema>                 (temp, build/)
   │  datamodel-code-generator    (pydantic_v2, literal enums, AllowExtra base,
   │                               --class-name AgentSessionEvent)
   ▼
src/pi_agent_events/models.py    (committed)
```

`AgentSessionEvent` isn't in pi-coding-agent's package `exports`, but its `.d.ts`
ships in the tarball, so the generator targets it by file path (see `ts/entry.ts`).

The two hand-finishing edits in `patch_schema.py` are what the porting doc warned
discriminated-union codegen needs: **stable names** (`tool_execution_start` →
`ToolExecutionStartEvent`, keyed on the discriminant, not array order) and the
**extra policy** (`extra="allow"` via the `AllowExtra` base — see the policy
section below).

## The pinned version

`pi_version.txt` and the `devDependencies` in `package.json` pin the three pi
packages — `pi-coding-agent`, `pi-agent-core`, `pi-ai` — all currently **0.78.1**.
Set them to the **same version the sandbox image installs**
(`@earendil-works/pi-coding-agent@X` → pin all three to `X`). To bump pi: change
the pins, `make gen`, review the diff, re-verify `KNOWN_WIRE_EXTRAS` (below),
commit.

> Note the npm scope: the agent ships under **`@earendil-works/...`** (repo
> `earendil-works/pi`), which is the line that reaches 0.78.x. The older
> `@mariozechner/...` scope caps at 0.73.1. Pin and install the `@earendil-works`
> scope so the CLI, the sandbox, and these models all match.

## Usage

```bash
make install        # node + python toolchains (pinned)
make gen            # regenerate schema + models
make test           # pytest over the committed session fixture
make drift          # CI gate: fail if committed artifacts != fresh generation
```

Parsing in your control plane:

```python
from pi_agent_events import parse_agent_event, AgentEndEvent

# each stdout line that is NOT an RPC envelope (response/extension_ui_request):
evt = parse_agent_event(line)            # -> typed event, e.g. AgentEndEvent
if isinstance(evt, AgentEndEvent):
    for m in evt.messages:
        ...
```

## Extra-field policy: allow at runtime, fail CI on new drift

Models are `extra="allow"`, so parsing **never crashes** on a field the pinned
models don't declare — important because pi's stdout carries fields its own types
omit (next section). Drift is caught **in CI** instead of at parse time:
`check_session.py` validates every event and audits each model for wire fields the
models didn't declare (Pydantic `model_extra`). Such a field **fails the gate**
unless it is either:

- inside a free-form `arguments` mapping (`Record<string, any>` — keys are data), or
- in `KNOWN_WIRE_EXTRAS` (the documented pi gap below).

Anything else is real drift and fails. `extra="allow"` (not the Pydantic default
`ignore`) is deliberate: it keeps unknown fields visible in `model_extra` so the
gate can see them.

## The pi wire-vs-types gap

While building this we found pi emitting fields its `.d.ts` didn't declare. Most
of that turned out to be **us generating from the wrong type**: `willRetry` (and
7 whole event types) were missing only because we first targeted `AgentEvent`
instead of `AgentSessionEvent`. Switching the root type made `willRetry` a
*typed* field on `AgentEndEvent` / `CompactionEndEvent` and added the session
events natively.

What remains is a genuine content-level gap — two fields pi emits on tool-call
content blocks that pi-ai's `ToolCall` type does not declare:

| Field | Where | Note |
|---|---|---|
| `partialArgs` | tool-call content blocks | raw JSON args as they stream in |
| `streamIndex` | tool-call content blocks | streaming order index |

These are allowlisted in `KNOWN_WIRE_EXTRAS` (`scripts/check_session.py`).
Re-verify that list on every pin bump; a test (`test_known_extras_are_actually_exercised`)
fails if an entry stops appearing, so the allowlist can't silently rot. Anything
new beyond the allowlist fails the drift gate.

## Verifying coverage against a real session

```bash
export OPENROUTER_API_KEY=sk-or-...
make capture        # drives local `pi --no-extensions --mode rpc` → sessions/local.jsonl
make check          # validate + drift gate (exit nonzero on un-allowlisted extras)
```

`capture_session.py` sends one or more JSONL prompts in order (stdin in rpc mode
is JSON, not free text), each running to its own `agent_end`; `--no-extensions`
means no `extension_ui_request` lines to answer. The committed
`sessions/local.jsonl` is a **two-turn** session (248 events, 2 `agent_end`s:
create a file, then rewrite it in alternating case) captured from **0.78.1**,
matching the pin — `make check` is green with only the two known extras present.

## Layout

| Path | What |
|---|---|
| `ts/entry.ts` | Documents the generator root (`AgentSessionEvent`); the generator targets its `.d.ts` by file path. |
| `scripts/generate.sh` | The full TS → schema → Pydantic pipeline. |
| `scripts/patch_schema.py` | Schema hand-finishing (names + extra policy). |
| `scripts/check_drift.sh` | Regenerate-and-diff CI gate. |
| `scripts/capture_session.py` | Drive local `pi --mode rpc`, save raw JSONL. |
| `scripts/check_session.py` | Validate a session + the drift CI gate (`KNOWN_WIRE_EXTRAS`). |
| `schema/agent-event.schema.json` | Generated JSON Schema (committed). |
| `src/pi_agent_events/models.py` | Generated Pydantic models (committed; do not edit). |
| `src/pi_agent_events/__init__.py` | Public API: `parse_agent_event`, event classes. |
| `sessions/local.jsonl` | A real captured session, used as the test fixture. |
