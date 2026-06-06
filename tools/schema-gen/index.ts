// Re-export pi's full `--mode rpc` wire contract, both directions.
//
// pi-coding-agent does not list these types in its package `exports` (only "."
// and "./hooks"), so we reach them by their shipped declaration files. The deep
// imports only resolve under a resolution mode that ignores `exports` maps; see
// `moduleResolution` in tsconfig.json.
//
// Scope: we only ever target `pi --no-extensions --mode rpc`, so extensions never
// load and the extension-UI request/response types never appear on the wire —
// they are intentionally omitted.
//
// stdout (pi -> consumer):
//   AgentSessionEvent  async event stream (session-level superset of
//                      pi-agent-core's AgentEvent: overrides agent_end with
//                      willRetry, adds queue_update / compaction_* /
//                      auto_retry_* / session_info_changed / thinking_level_changed)
//   RpcResponse        synchronous reply to each RpcCommand (correlated by id)
//
// stdin (consumer -> pi):
//   RpcCommand         commands that drive the agent (prompt, steer, abort, …)
export type { AgentSessionEvent } from "@earendil-works/pi-coding-agent/dist/core/agent-session";
export type {
  RpcCommand,
  RpcResponse,
} from "@earendil-works/pi-coding-agent/dist/modes/rpc/rpc-types";
