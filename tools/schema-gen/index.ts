// Re-export the minimal `pi --no-extensions --mode rpc` surface we actually use.
//
// pi-coding-agent does not list these in its package `exports` (only "." and
// "./hooks"), so we reach them by their shipped declaration files; the deep
// imports only resolve under a resolution mode that ignores `exports` maps (see
// `moduleResolution` in tsconfig.json).
//
// stdout (pi -> consumer):
//   AgentSessionEvent  async event stream (session-level superset of
//                      pi-agent-core's AgentEvent)
//   PromptResponse     the synchronous ack for a prompt command (correlated by
//                      id; the work itself then streams as events to agent_end)
//
// stdin (consumer -> pi):
//   PromptCommand      the one command we send
//
// PromptCommand/PromptResponse are derived (Extract) from pi's RpcCommand /
// RpcResponse unions so they stay tied to pi's real types — rooting on the whole
// unions would drag in every other command/response plus the entire
// model/provider descriptor, none of which we need yet. (A failed prompt returns
// pi's generic error response, intentionally not modeled here.)
import type {
  RpcCommand,
  RpcResponse,
} from "@earendil-works/pi-coding-agent/dist/modes/rpc/rpc-types";

export type { AgentSessionEvent } from "@earendil-works/pi-coding-agent/dist/core/agent-session";
export type PromptCommand = Extract<RpcCommand, { type: "prompt" }>;
export type PromptResponse = Extract<RpcResponse, { command: "prompt" }>;
