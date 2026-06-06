// NOTE: the generator (see `npm run schema`) points directly at
//   node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.d.ts
// and walks the `AgentSessionEvent` type, because that is what `pi --mode rpc`
// actually emits on stdout — NOT pi-agent-core's `AgentEvent`.
//
// `AgentSessionEvent` is a superset of the core `AgentEvent`: it overrides
// `agent_end` to add `willRetry`, and adds session-level events (queue_update,
// compaction_start/end, auto_retry_start/end, session_info_changed,
// thinking_level_changed). pi-coding-agent does not export this type from its
// package root (only "." and "./hooks"), but ships the .d.ts in the tarball, so
// we resolve it by file path.
//
// This file is kept for documentation; the deep import below would be blocked by
// the package's `exports` map under bundler/node resolution, which is exactly why
// the generator targets the file path instead.
export type { AgentSessionEvent } from "@earendil-works/pi-coding-agent/dist/core/agent-session";
