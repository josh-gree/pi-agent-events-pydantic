// Re-export pi's wire event type.
//
// `pi --mode rpc` streams `AgentSessionEvent` objects on stdout — pi-coding-agent's
// session-level superset of pi-agent-core's `AgentEvent` (it overrides `agent_end`
// with `willRetry` and adds queue_update, compaction_*, auto_retry_*,
// session_info_changed, thinking_level_changed). That is the type we model.
//
// pi-coding-agent does not list `AgentSessionEvent` in its package `exports`
// (only "." and "./hooks"), so we reach it by its shipped declaration file. This
// deep import only resolves under a resolution mode that ignores `exports` maps;
// see `moduleResolution` in tsconfig.json.
export type { AgentSessionEvent } from "@earendil-works/pi-coding-agent/dist/core/agent-session";
