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
