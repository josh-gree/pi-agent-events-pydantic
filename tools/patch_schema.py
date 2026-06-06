"""Inject stable class-name titles into the generated JSON Schema.

ts-json-schema-generator emits pi's event unions as anonymous inline objects, so
datamodel-codegen names the resulting classes positionally
(``AgentSessionEvent1``, ``AgentSessionEvent2``, ...) — ugly, and unstable
because the numbers track *array order*. We give each union member a ``title``
derived from its ``type`` discriminant const, so ``datamodel-codegen
--use-title-as-name`` produces stable names keyed on the literal
(``tool_execution_start`` -> ``ToolExecutionStartEvent``), regardless of order.

This is a Python-side codegen concern, so it lives here and not in the JS
generator: the committed handoff schema (``schema/agent-session.schema.json``)
stays faithful/raw; this writes a derived, build-only patched schema that feeds
datamodel-codegen.

Usage: python tools/patch_schema.py <in.schema.json> <out.schema.json>
"""

from __future__ import annotations

import json
import re
import sys

# Per-union (prefix, suffix) wrapped around PascalCase(<type const>). The event
# unions get an `Event` suffix; AssistantMessageEvent's consts are generic
# (start/done/error/text_delta...) and would collide or read badly bare, so they
# get an `AssistantMessage` prefix instead.
NAMING: dict[str, tuple[str, str]] = {
    "AgentSessionEvent": ("", "Event"),
    "AssistantMessageEvent": ("AssistantMessage", ""),
}
DEFAULT = ("", "Event")

# Some value enums are authored inline in pi's TS (no named type), so they have
# no title to carry through and datamodel-codegen names them positionally
# (Reason, Reason2, Reason3). Name them explicitly, keyed on (owning variant's
# `type` const, property name). Identical (const-agnostic) value sets that share
# one name — e.g. the compaction reason on both start and end — collapse to a
# single enum class. Named TS enums (StopReason, ThinkingLevel, ...) are left
# alone; they already carry their name.
ENUM_NAMES: dict[tuple[str, str], str] = {
    ("compaction_start", "reason"): "CompactionReason",
    ("compaction_end", "reason"): "CompactionReason",
    ("done", "reason"): "AssistantFinishReason",
    ("error", "reason"): "AssistantErrorReason",
}


def strip_additional_properties_false(node) -> int:
    """Remove every ``additionalProperties: false`` so datamodel-codegen does not
    emit ``extra='forbid'`` models. pi's stdout carries fields its own TS types
    omit (e.g. partialArgs/streamIndex on tool-call blocks), so forbidding would
    make pi's real output unparseable. Returns how many were removed."""
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


def pascal(s: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[_\-]+", s) if p)


def const_of(member: dict) -> str | None:
    """The `type` discriminant const of a union member, if it has one."""
    t = member.get("properties", {}).get("type", {})
    if "const" in t:
        return t["const"]
    enum = t.get("enum")
    if isinstance(enum, list) and len(enum) == 1:
        return enum[0]
    return None


def title_inline_enums(member: dict, const: str) -> int:
    """Title inline value enums on a variant's properties per ENUM_NAMES."""
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


def title_members(members: list, prefix: str, suffix: str) -> tuple[int, int]:
    """Title each union member carrying a `type` const (and its inline value
    enums); recurse into members that are themselves inline unions (the core
    AgentEvent union is inlined inside AgentSessionEvent). Returns
    (member_titles, enum_titles)."""
    members_n = enums_n = 0
    for m in members:
        c = const_of(m)
        if c is not None:
            m["title"] = f"{prefix}{pascal(c)}{suffix}"
            members_n += 1
            enums_n += title_inline_enums(m, c)
        else:
            sub = m.get("anyOf") or m.get("oneOf")
            if sub:
                mn, en = title_members(sub, prefix, suffix)
                members_n += mn
                enums_n += en
    return members_n, enums_n


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    schema = json.load(open(src))
    defs = schema.get("definitions") or schema.get("$defs") or {}

    stripped = strip_additional_properties_false(schema)

    titled: dict[str, int] = {}
    enums = 0
    for name, node in defs.items():
        members = node.get("anyOf") or node.get("oneOf")
        if not members:
            continue
        member_n, enum_n = title_members(members, *NAMING.get(name, DEFAULT))
        enums += enum_n
        if member_n:
            titled[name] = member_n

    json.dump(schema, open(dst, "w"), indent=2)
    print(
        f"patched {src} -> {dst}: stripped {stripped} additionalProperties:false; "
        f"titled members {titled}; inline enums {enums}"
    )


if __name__ == "__main__":
    main()
