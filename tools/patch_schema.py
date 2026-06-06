"""Inject stable class-name titles into the generated JSON Schema, and drop the
closed-object constraint, between the TS->schema and schema->Pydantic hops.

ts-json-schema-generator emits pi's unions as anonymous inline objects, so
datamodel-codegen names the resulting classes positionally (``RpcCommand1`` …) —
ugly, and unstable because the numbers track *array order*. We give each union
member a ``title`` derived from its discriminant, so ``datamodel-codegen
--use-title-as-name`` produces stable names keyed on the literal
(``tool_execution_start`` -> ``ToolExecutionStartEvent``), regardless of order.

Different unions discriminate on different things — events on ``type``, command
responses on ``command``, extension UI requests on ``method``, and the extension
UI *responses* only by which field is present — so naming is configured per
union (see NAMING). We also strip ``additionalProperties: false`` so models are
not ``extra='forbid'``: pi emits fields its own TS types omit
(partialArgs/streamIndex on tool-call blocks), which forbidding would reject.

This is a Python-side codegen concern, so it lives here and not in the JS
generator: the committed handoff schema (``schema/pi-rpc.schema.json``) stays
faithful/raw; this writes a derived, build-only patched schema.

Usage: python tools/patch_schema.py <in.schema.json> <out.schema.json>
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Naming:
    """How to title the members of one union definition.

    - ``discriminant``: property whose const literal names the member.
    - ``prefix``/``suffix``: wrapped around PascalCase(<discriminant const>).
    - ``fallback``: name for a member lacking the discriminant const (e.g. the
      catch-all error response, whose ``command`` is an open ``string``).
    - ``data_names``: title a member's inline ``data`` payload object, keyed by
      the member's discriminant const (response bodies are anonymous inline
      objects in the TS).
    """

    discriminant: str = "type"
    prefix: str = ""
    suffix: str = ""
    fallback: str | None = None
    data_names: dict[str, str] = field(default_factory=dict)


# datamodel-codegen mangles generic-instantiation definition names like
# `Model<any>` into junk (`Model3Cany3E`). Rename such keys (and rewrite $refs)
# to something legible before codegen.
RENAME: dict[str, str] = {"Model<any>": "Model"}

# RpcResponse `data` payloads are anonymous inline objects; name them by command
# so a consumer reads e.g. `MessagesResult`, not `Data10`. Commands whose data is
# already a named type (get_state->RpcSessionState, bash->BashResult,
# compact->CompactionResult, set_model->Model, get_session_stats->SessionStats)
# are absent here — nothing to name.
DATA_NAMES: dict[str, str] = {
    "new_session": "NewSessionResult",
    "cycle_model": "CycleModelResult",
    "get_available_models": "AvailableModelsResult",
    "cycle_thinking_level": "ThinkingLevelResult",
    "export_html": "ExportHtmlResult",
    "switch_session": "SwitchSessionResult",
    "fork": "ForkResult",
    "clone": "CloneResult",
    "get_fork_messages": "ForkMessagesResult",
    "get_last_assistant_text": "LastAssistantTextResult",
    "get_messages": "MessagesResult",
    "get_commands": "CommandsResult",
}


# Per-union naming. Anything not listed falls back to DEFAULT (type-discriminated,
# `Event` suffix) — which only ever matches event-shaped unions, since titling
# requires a discriminant const the member actually carries.
NAMING: dict[str, Naming] = {
    "AgentSessionEvent": Naming(suffix="Event"),
    "AssistantMessageEvent": Naming(prefix="AssistantMessage"),
    "RpcCommand": Naming(suffix="Command"),
    "RpcResponse": Naming(
        discriminant="command",
        suffix="Response",
        fallback="RpcErrorResponse",
        data_names=DATA_NAMES,
    ),
}
DEFAULT = Naming(suffix="Event")

# Inline value enums pi authors without a named type, keyed on (owning variant's
# discriminant const, property name). Identical value sets sharing one name
# collapse to a single enum class. Named TS enums (StopReason, ThinkingLevel, …)
# already carry their name and are left alone.
ENUM_NAMES: dict[tuple[str, str], str] = {
    ("compaction_start", "reason"): "CompactionReason",
    ("compaction_end", "reason"): "CompactionReason",
    ("done", "reason"): "AssistantFinishReason",
    ("error", "reason"): "AssistantErrorReason",
    ("prompt", "streamingBehavior"): "StreamingBehavior",
    ("set_steering_mode", "mode"): "QueueMode",
    ("set_follow_up_mode", "mode"): "QueueMode",
}


def pascal(s: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[_\-]+", s) if p)


def const_of(member: dict, prop: str) -> str | None:
    """The discriminant const of a union member on ``prop``, if it has one."""
    t = member.get("properties", {}).get(prop, {})
    if "const" in t:
        return t["const"]
    enum = t.get("enum")
    if isinstance(enum, list) and len(enum) == 1:
        return enum[0]
    return None


def strip_additional_properties_false(node) -> int:
    """Remove every ``additionalProperties: false`` so generated models inherit
    pydantic's permissive default instead of ``extra='forbid'``. Returns count."""
    n = 0
    if isinstance(node, dict):
        if node.get("additionalProperties") is False:
            node.pop("additionalProperties")
            n += 1
        for v in node.values():
            n += strip_additional_properties_false(v)
    elif isinstance(node, list):
        for v in node:
            n += strip_additional_properties_false(v)
    return n


def rename_definitions(schema: dict, defs: dict) -> dict[str, str]:
    """Rename mangled definition keys (and rewrite every $ref) per RENAME."""
    applied: dict[str, str] = {}
    for old, new in RENAME.items():
        if old in defs:
            defs[new] = defs.pop(old)
            applied[old] = new

    def fix(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/definitions/"):
                name = urllib.parse.unquote(ref[len("#/definitions/") :])
                if name in applied:
                    node["$ref"] = "#/definitions/" + applied[name]
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(schema)
    return applied


def title_object(node, name: str) -> int:
    """Title an inline object schema, or the object arm of a `{...}|null` union."""
    if not isinstance(node, dict):
        return 0
    if "properties" in node or node.get("type") == "object":
        node["title"] = name
        return 1
    for key in ("anyOf", "oneOf"):
        for sub in node.get(key, []):
            if isinstance(sub, dict) and ("properties" in sub or sub.get("type") == "object"):
                sub["title"] = name
                return 1
    return 0


def title_inline_enums(member: dict, const: str | None) -> int:
    """Title inline value enums on a variant's properties per ENUM_NAMES."""
    if const is None:
        return 0
    n = 0
    for prop, schema in (member.get("properties") or {}).items():
        if not isinstance(schema, dict) or "$ref" in schema or "const" in schema:
            continue
        if isinstance(schema.get("enum"), list):
            name = ENUM_NAMES.get((const, prop))
            if name:
                schema["title"] = name
                n += 1
    return n


def title_members(members: list, naming: Naming) -> tuple[int, int]:
    """Title each union member (and its inline value enums); recurse into members
    that are themselves inline unions (the core AgentEvent union is inlined inside
    AgentSessionEvent). Returns (member_titles, enum_titles)."""
    members_n = enums_n = 0
    for m in members:
        c = const_of(m, naming.discriminant)
        if c is not None:
            m["title"] = f"{naming.prefix}{pascal(c)}{naming.suffix}"
            members_n += 1
            enums_n += title_inline_enums(m, c)
            if c in naming.data_names:
                data = (m.get("properties") or {}).get("data")
                if data is not None:
                    title_object(data, naming.data_names[c])
        elif naming.fallback:
            m["title"] = naming.fallback
            members_n += 1
        else:
            sub = m.get("anyOf") or m.get("oneOf")
            if sub:
                mn, en = title_members(sub, naming)
                members_n += mn
                enums_n += en
    return members_n, enums_n


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    schema = json.load(open(src))
    defs = schema.get("definitions") or schema.get("$defs") or {}

    stripped = strip_additional_properties_false(schema)
    renamed = rename_definitions(schema, defs)

    titled: dict[str, int] = {}
    enums = 0
    for name, node in defs.items():
        members = node.get("anyOf") or node.get("oneOf")
        if not members:
            continue
        member_n, enum_n = title_members(members, NAMING.get(name, DEFAULT))
        enums += enum_n
        if member_n:
            titled[name] = member_n

    json.dump(schema, open(dst, "w"), indent=2)
    print(
        f"patched {src} -> {dst}: stripped {stripped} additionalProperties:false; "
        f"renamed {renamed}; titled members {titled}; inline enums {enums}"
    )


if __name__ == "__main__":
    main()
