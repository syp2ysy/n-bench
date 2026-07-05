# Runtime Contract

Use a long-running file-backed workflow.

- Keep state in `state/`, logs in `logs/`, and article outputs in `outputs/`.
- Start each pass from files, not chat memory.
- Update heartbeat and progress after major passes.
- Use fresh sessions for long tasks and record decisions.
- If a direction stalls, pivot the structure or source route.
- Guardian/heartbeat workers inspect liveness only; they do not edit research content.
- Verify citation identity continuously and record source evidence.

Runtime success means the run can be resumed from disk without relying on conversation history.

Use `survey_driver.py --run-until-complete` as the global resume point. Runtime action files such as `discovery_runtime_action.json`, `topic_relevance_runtime_action.json`, `paper_understanding_runtime_action.json`, and `gate7_runtime_action.json` are queue state, not completed work; a phase advances only after the corresponding executor records validated worker output.

## Active Intent

`survey_driver.py` is the only script that activates runtime dispatch. Before returning a worker-spawn status it writes `state/runtime_active_intent.json`:

```json
{
  "schema_version": 1,
  "active_phase": "<phase>",
  "next_action": "<spawn action>",
  "allowed_request_types": ["<request type>"],
  "phase_generation": "<stable hash>",
  "source_hashes": {"<state file>": "<sha256>"},
  "generated_at": "<iso timestamp>"
}
```

`phase_generation` is a stable hash of `active_phase`, `next_action`, `allowed_request_types`, and `source_hashes`. Every normalized queue row must carry the current `phase_generation`.

Request type mapping:

- `spawn_topic_relevance_agents` -> `topic_relevance`
- `spawn_topic_relevance_second_audit_agents` -> `topic_relevance_second_audit`
- `spawn_paper_understanding_agents` -> `paper_understanding`
- `spawn_reviewers` -> `gate7_reviewer`
- `spawn_repair_agents` -> `gate7_repair`
- `spawn_targeted_rereviewers` -> `gate7_targeted_rereview`
- `spawn_discovery_agents` -> `discovery`

When the driver rolls back from a downstream phase to source verification/topic relevance, it clears downstream active spawn files and supersedes old pending rows. Historical session/result logs remain append-only.

## Dispatcher Rules

When the driver asks for workers, always route through `runtime_dispatcher.py`. The dispatcher reads `discovery_spawn_requests.json`, `topic_relevance_spawn_requests.json`, `paper_understanding_spawn_requests.json`, and `gate7_spawn_requests.json`, writes normalized rows to `state/runtime_dispatch_queue.jsonl`, records spawn sessions in `state/runtime_agent_sessions.jsonl`, and routes returned worker JSON to the correct recorder. Main-agent loop:

1. `python3 scripts/survey_driver.py --task-dir <run> --target <target> --run-until-complete`
2. If a worker-spawn status is returned, `python3 scripts/runtime_dispatcher.py --task-dir <run> --collect-pending`
3. Spawn each pending request with `multi_agent_v1.spawn_agent(fork_context=false)`
4. `python3 scripts/runtime_dispatcher.py --task-dir <run> --mark-spawned <request-id> --agent-id <subagent-session-id>`
5. Save each worker response and record it with `python3 scripts/runtime_dispatcher.py --task-dir <run> --record-agent-output <request-id> --output-file <file>`
6. Rerun the survey driver.

The dispatcher must expose only request types allowed by the current active intent. If no active intent exists, `--collect-pending` returns `blocked_runtime_intent_required`; the user must rerun `survey_driver.py`.

If an unspawned queue row does not match the current intent, mark it `stale_superseded`. If the same legal source request reappears under the current intent, reactivate an unspawned stale row as `pending_spawn`; if the old row had already spawned, keep it as stale audit history and create a new retry attempt. If a spawned row no longer matches, do not record its output into research state; return `stale_request_rejected` and append an audit entry. `--mark-spawned` and `--record-agent-output` must reject any request whose `phase_generation` differs from the current intent.

The dispatcher never edits paper, article, or Gate 7 state directly. Non-JSON worker output is `invalid_result`. Discovery output is routed to `discovery_runtime_executor.py --record-result`. Topic-relevance primary output is routed to `topic_relevance_runtime_executor.py --record-result`; independent second-audit output is routed to `topic_relevance_runtime_executor.py --record-second-audit`. Source verification can proceed only after the executor records audit rows that cover the real raw candidates, retained papers, and A/B papers, plus valid second-audit rows for high-risk A/B core decisions. If paper-understanding output reports unavailable A/B papers, the dispatcher marks `rebalance_required`; the survey driver handles downgrade/replacement and rebuilds paper-understanding batches.
