# Runtime Contract

Use a long-running file-backed workflow.

- Keep state in `state/`, logs in `logs/`, and article outputs in `outputs/`.
- Start each pass from files, not chat memory.
- Update progress after major passes.
- Use fresh sessions for long tasks and record decisions.
- If a direction stalls, pivot the structure or source route.
- Verify citation identity continuously and record source evidence.

Runtime success means the run can be resumed from disk without relying on conversation history.

Use `runner.py --run-until-complete` as the global public resume point. It delegates to the hardened `survey_driver.py`, then refreshes `state/tasks.jsonl`, `state/run_state.json`, and the paper-card mirror. Runtime action files such as `discovery_runtime_action.json`, `topic_relevance_runtime_action.json`, `paper_understanding_runtime_action.json`, and `gate7_runtime_action.json` are queue state, not completed work; a phase advances only after the corresponding executor records validated worker output.

`state/tasks.jsonl` is the compact public queue view. It is derived from dispatcher rows and should be used for debugging and resume decisions. The dispatcher queue remains the compatibility execution log until the legacy spawn-request files are retired.

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

`phase_generation` covers semantic phase inputs and the current spawn-request file only. It must not include `runtime_dispatch_queue.jsonl`, `runtime_agent_sessions.jsonl`, or `runtime_agent_results.jsonl`; those files are progress evidence for repeated-blocker detection, not request identity. A driver must write active intent before considering a repeated no-progress blocker, and worker-spawn states are never terminal no-progress states while the dispatcher has pending, spawned, invalid, or rebalance-required runtime rows.

Request type mapping:

- `spawn_topic_relevance_agents` -> `topic_relevance`
- `spawn_topic_profile_agents` -> `topic_profile`
- `spawn_topic_relevance_second_audit_agents` -> `topic_relevance_second_audit`
- `spawn_paper_understanding_agents` -> `paper_understanding`
- `spawn_knowledge_tree_agents` -> `knowledge_tree`
- `spawn_spine_planner_agents` -> `spine_planner`
- `spawn_reviewers` -> `gate7_reviewer`
- `spawn_repair_agents` -> `gate7_repair`
- `spawn_targeted_rereviewers` -> `gate7_targeted_rereview`
- `spawn_discovery_agents` -> `discovery`

When the driver rolls back from a downstream phase to source verification/topic relevance, it clears downstream active spawn files and supersedes old pending rows. Historical session/result logs remain append-only.

## Dispatcher Rules

When the runner or driver asks for workers, use the public `task_queue.py` facade. It syncs compact tasks from the compatibility dispatcher and delegates mark/record operations to the hardened dispatcher checks. The dispatcher still reads `topic_profile_spawn_requests.json`, `discovery_spawn_requests.json`, `topic_relevance_spawn_requests.json`, `paper_understanding_spawn_requests.json`, `knowledge_tree_spawn_requests.json`, and `gate7_spawn_requests.json`, writes normalized rows to `state/runtime_dispatch_queue.jsonl`, records spawn sessions in `state/runtime_agent_sessions.jsonl`, and routes returned worker JSON to the correct recorder.

Main-agent loop:

1. `python3 scripts/runner.py --task-dir <run> --target <target> --run-until-complete`
2. If a worker-spawn status is returned, `python3 scripts/task_queue.py --task-dir <run> --collect-pending`
3. Spawn each pending request with `multi_agent_v1.spawn_agent(fork_context=false)`
4. `python3 scripts/task_queue.py --task-dir <run> --mark-spawned <request-id> --agent-id <subagent-session-id>`
5. Save each worker response and record it with `python3 scripts/task_queue.py --task-dir <run> --record-agent-output <request-id> --output-file <file>`
6. Rerun the public runner.

The task queue must expose only request types allowed by the current active intent. If no active intent exists, `--collect-pending` returns `blocked_runtime_intent_required`; the user must rerun `runner.py`.

If an unspawned queue row does not match the current intent, mark it `stale_superseded`. If the same legal source request reappears under the current intent, reactivate an unspawned stale row as `pending_spawn`; if the old row had already spawned, keep it as stale audit history and create a new retry attempt. If a spawned row no longer matches, do not record its output into research state; return `stale_request_rejected` and append an audit entry. `--mark-spawned` and `--record-agent-output` must reject any request whose `phase_generation` differs from the current intent.

The task queue never edits paper, article, or Gate 7 state directly. Non-JSON worker output is `invalid_result`. Topic-boundary output is routed to `topic_profile.py --record-result`. Discovery output is routed to `discovery_runtime_executor.py --record-result`; full/CSUR discovery records route-level results first and writes canonical `raw_candidates`, `search_routes`, `lqs_scores`, and `corpus_expansion` only after the route results merge and pass discovery sufficiency. Optional `discovery_runtime_executor.py --prefetch-active` snapshots real public metadata into the worker request, but those snapshots are not canonical corpus state until a worker result is recorded. Topic-relevance primary output is routed to `topic_relevance_runtime_executor.py --record-result`; independent second-audit output is routed to `topic_relevance_runtime_executor.py --record-second-audit`. Paper-reading output is routed through the public `paper_reader.py --record-result` facade, which delegates compatibility merging and then mirrors validated cards to `state/paper_cards/{paper_id}.json`. Knowledge-tree output is routed to `knowledge_tree_builder.py --record-result`, which validates traceability to public paper cards before writing `outputs/knowledge_tree.yml`, `state/paper_clusters.jsonl`, `state/taxonomy_candidates.yml`, and an initial `state/spine_decision.md`. Spine-planner output is routed to `spine_planner.py --record-result`, which validates the selected spine against public paper cards, the knowledge tree, taxonomy candidates, and related-survey alignment before updating `state/spine_decision.md` and selected taxonomy metadata. Source verification can proceed only after the executor records audit rows that cover the real raw candidates, retained papers, and A/B papers, plus valid second-audit rows for high-risk A/B core decisions. Primary topic-audit rows must carry the actual `subagent_session_id` that produced them. Secondary audit rows must reference that primary session and must use a different `subagent_session_id`; missing or same-session evidence cannot clear a second-audit blocker. If paper-understanding output reports unavailable A/B papers, the dispatcher marks `rebalance_required`; the survey driver handles downgrade/replacement and rebuilds paper-understanding batches.
