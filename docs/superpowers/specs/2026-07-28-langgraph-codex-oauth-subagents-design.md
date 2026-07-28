# LangGraph Codex OAuth Subagents Design

## Objective

Run the Vampire Survivors agent as a real LangGraph multi-agent workflow. A
deterministic parent graph supervises separately compiled leader and follower
subgraphs. Both model roles use the official `openai-codex` Python SDK and its
Codex-managed ChatGPT login. Repository code never reads or owns OAuth tokens.

## Corrected boundaries

- `openai-codex==0.144.4` owns one process-lifetime `codex app-server` client,
  authentication state, token refresh, Codex threads, turns, images, and
  schema-constrained output.
- The SDK's pinned Codex CLI runtime is the supported default. The separately
  installed `codex-cli 0.145.0` is not selected implicitly.
- A parent `StateGraph` owns preparation, screen routing, checkpointing,
  retries, evaluation, and all side-effect boundaries.
- Leader and follower are separately compiled child `StateGraph` instances,
  not labels for two closures in one graph. Each child has a narrow state
  schema and produces one structured proposal.
- `SpineGameTools` and `Controller` remain the only game-input path. Neither
  Codex child receives shell, filesystem-write, web-search, or game tools.
- Codex threads provide model conversation continuity; LangGraph checkpoints
  provide workflow continuity. Their identifiers are stored separately.

## Runtime shape

```text
LangGraph GoalState thread (SQLite)
  prepare -> observe -> deterministic route
                  |-> leader child subgraph -> validated intent
                  |-> follower child subgraph -> movement proposal
                  |-> deterministic menu/control/level-up action
                  `-> deterministic evaluator -> achieved/not_met/blocked

Process-lifetime AsyncCodex
  account metadata check (authMode == chatgpt)
  leader Codex thread <-> leader child state
  follower Codex thread <-> follower child state
```

## Authentication and safety invariants

1. Use `AsyncCodex` from the official published Python SDK.
2. Accept only public account metadata proving managed ChatGPT authentication.
3. Never read token files, request experimental `chatgptAuthTokens`, copy an
   access token, or inject an API key.
4. Start/resume Codex threads with read-only sandboxing and deny-all approval.
5. Disable web search and the native shell tool through documented Codex
   configuration. Reject any unexpected side-effect item in a completed turn.
6. Parse and locally validate every schema-constrained final response.
7. Neutralize game input on provider failure, invalid output, timeout,
   checkpoint ambiguity, or rejected proposal.

## Subagent state and context

- Leader input: goal, current observation/image, fixed evaluation contract.
- Leader output: high-level or menu decision plus its Codex thread ID.
- Follower input: goal, compact observation/image, leader intent.
- Follower output: one bounded direction plus its Codex thread ID.
- Child graphs compile with the default inherited per-invocation checkpoint
  mode so the parent provides durability while child calls remain isolated.
- Parent and child schemas are mapped explicitly in wrapper nodes. Tests must
  prove child checkpoint namespaces are discoverable and role state does not
  leak across agents.

## Verification ladder

1. Unit tests with a fake SDK prove lifecycle, account checks, thread reuse,
   images, structured output, and fail-closed behavior.
2. Graph tests prove separately compiled child graphs, state isolation,
   checkpoint resume, deterministic routing, and neutralization.
3. A real no-game OAuth smoke proves one SDK client, two child agents, and
   persistent role threads using the existing ChatGPT login.
4. A bounded live vertical slice proves OAuth -> child subgraph -> validated
   proposal -> exactly one allowed game action -> re-observe -> neutralize.
5. G0 is complete only when the repository's explicit live modifier, attach,
   entry, and movement stop conditions all pass. No screenshot or unit test may
   substitute for that runtime proof.

## Removal criteria

Delete `spine/oauth_codex.py` and its one-shot smoke/tests only after the SDK
client and real OAuth smoke pass. Rewrite all docs that claim `codex exec` is a
LangGraph model provider. Preserve the deterministic G0 harness work committed
in `9acf694` while replacing its model boundary.
