"""Patch the raw JSON Schema between the TS->schema and schema->Pydantic hops.

ts-json-schema-generator emits faithful but unfriendly schema for our purposes:
its discriminated unions are anonymous (members get numbered class names like
`AgentEvent8`) and every object is `additionalProperties: false`. Two surgical
edits fix both, deterministically:

  1. Title each member of a const-discriminated union (a `type: <const>` tag) so
     datamodel-codegen --use-title-as-name produces stable, readable class names
     keyed on the *literal* (`tool_execution_start` -> `ToolExecutionStartEvent`).
     Stable across regenerations: names track the discriminant, not array order.
  2. Strip `additionalProperties: false` so generated models do not carry
     `extra="forbid"`; they inherit `extra="allow"` from the AllowExtra base
     instead. Policy is allow-at-runtime + fail-CI-on-new-extras (see _base.py
     and README "The pi wire-vs-types gap") — pi emits fields its own types omit,
     so forbidding would make pi's *current* output unparseable.

Usage: python scripts/patch_schema.py <in.schema.json> <out.schema.json>
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse

# Per-union naming: (prefix, suffix) applied to PascalCase(<type const>).
# Default is bare PascalCase; these get qualified for readability /
# collision-avoidance (assistant deltas have generic consts like "start"/"done").
NAMING: dict[str, tuple[str, str]] = {
    "AgentSessionEvent": ("", "Event"),   # the root union (pi --mode rpc wire)
    "CoreAgentEvent": ("", "Event"),      # the renamed Exclude<AgentEvent, agent_end>
    "AssistantMessageEvent": ("AssistantMessage", ""),
}

# ts-json-schema-generator names the `Exclude<AgentEvent, {type:"agent_end"}>`
# member with an unusable mangled definition key; rename it to something legible.
RENAME_PREFIXES: dict[str, str] = {
    "Exclude<AgentEvent": "CoreAgentEvent",
}


def pascal(s: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[_\-]+", s) if p)


def const_of(member: dict) -> str | None:
    """Return the `type` discriminant const of a union member, if it has one."""
    t = member.get("properties", {}).get("type", {})
    if "const" in t:
        return t["const"]
    enum = t.get("enum")
    if isinstance(enum, list) and len(enum) == 1:
        return enum[0]
    return None


def strip_additional_properties_false(node) -> None:
    if isinstance(node, dict):
        if node.get("additionalProperties") is False:
            node.pop("additionalProperties")
        for v in node.values():
            strip_additional_properties_false(v)
    elif isinstance(node, list):
        for v in node:
            strip_additional_properties_false(v)


def rename_definitions(schema: dict, defs: dict) -> dict[str, str]:
    """Rename mangled definition keys (and rewrite every $ref to them) to legible
    names per RENAME_PREFIXES. Returns the applied {old: new} map."""
    applied: dict[str, str] = {}
    for old in list(defs):
        for prefix, new in RENAME_PREFIXES.items():
            if old.startswith(prefix):
                defs[new] = defs.pop(old)
                applied[old] = new

    def fix(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/definitions/"):
                name = urllib.parse.unquote(ref[len("#/definitions/"):])
                if name in applied:
                    node["$ref"] = "#/definitions/" + applied[name]
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(schema)
    return applied


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    schema = json.load(open(src))
    defs = schema.get("definitions") or schema.get("$defs") or {}

    strip_additional_properties_false(schema)
    renamed = rename_definitions(schema, defs)

    # Title every union member that carries a `type` const, even if a sibling
    # member doesn't (e.g. AgentSessionEvent mixes a $ref to the core union with
    # inline const variants). Members without a const (refs, role-discriminated,
    # plain types) are left for datamodel-codegen's own naming.
    titled = {}
    for name, node in defs.items():
        members = node.get("anyOf") or node.get("oneOf")
        if not members:
            continue
        prefix, suffix = NAMING.get(name, ("", ""))
        count = 0
        for member in members:
            c = const_of(member)
            if c is None:
                continue
            member["title"] = f"{prefix}{pascal(c)}{suffix}"
            count += 1
        if count:
            titled[name] = count

    json.dump(schema, open(dst, "w"), indent=2)
    print(f"patched {src} -> {dst}: renamed {renamed}; titled unions {titled}")


if __name__ == "__main__":
    main()
