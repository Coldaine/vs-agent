# Task 3 Report: Runtime wiring and invalid-adapter removal

## Result

Task 3 is implemented. The goal entry point now owns one official
`CodexAgentClient` for each complete graph invocation/resume, restores only the
typed leader/follower bindings from the selected LangGraph checkpoint, checks
the SDK account during `start()`, and deterministically neutralizes/closes on
success or failure. Compatibility helpers expose async `acall_*` APIs and allow
their legacy synchronous entry points only when no event loop is running.

The no-game smoke now executes both compiled child graphs through that SDK
boundary. `spine/oauth_codex.py` and its two obsolete test modules are deleted.

## Red evidence

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_run_goal tests.test_model_client_oauth -v
```

Observed before production changes: 12 tests ran with the new cases failing on
the missing `run.CodexAgentClient`, missing
`model_client.set_client_factory_for_testing`/`acall_planner`, and the sync
planner not rejecting use inside a live event loop. The smoke-specific RED test
then failed with `run_smoke() got an unexpected keyword argument
'codex_factory'`.

## Green evidence

Focused runtime and compatibility command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_run_goal tests.test_model_client_oauth -v
```

Result: 13 tests passed.

Complete suite command:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Result: 79 tests passed.

Dependency and compile checks:

```powershell
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m compileall -q spine
git diff --check
```

Result: no broken requirements, compilation succeeded, and the diff check was
clean.

Required removal search:

```powershell
rg -n "CodexOAuthRunner|codex exec|oauth_codex" spine tests
```

Result: no active runtime matches (`rg` exit 1, expected for no matches).

## Commit

Planned commit subject: `refactor: run LangGraph agents through Codex SDK`.

## Self-review

- The same runtime client handles leader and follower turns; no per-node SDK
  client is created.
- Resume initialization goes through `AgentRuntime.from_checkpoint`, whose
  typed binding extractor rejects ambiguous, duplicate, blank, or cross-role
  state.
- `run_langgraph_goal` and the smoke are async. `asyncio.run` appears only at
  CLI/legacy synchronous boundaries, and compatibility sync helpers reject a
  currently running event loop before creating a coroutine.
- The shutdown nesting still closes the SDK and closes game tools if explicit
  neutralization raises, and still closes game tools if SDK close raises.
- No API key or HTTP transport was added. Compatibility calls retain the
  inherited-key fail-closed guard and use `CodexAgentClient` exclusively.
- Existing dirty `GOAL.md`, `status/HUMAN_NEEDED.md`, and
  `status/g0_capture.jpg` were neither edited nor staged by Task 3.

## Concerns

- The live ChatGPT OAuth/image smoke and machine-readable model/thread metadata
  are intentionally Task 4, so Task 3 verification uses a lifecycle-faithful
  fake SDK client and deterministic no-game tools.
- Context7 documentation lookup was attempted but its monthly quota was
  exhausted. The installed `AsyncSqliteSaver` and `AsyncCodex` signatures were
  inspected locally instead.
