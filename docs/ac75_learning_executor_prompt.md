# Executor prompt: AC37 AC75 learned simulator

You are implementing a repository-specific plan. Work in C:/Workspace/Americas Cup/2D_regatta_replay.

The user's objective is to learn the observed behavior of last-cycle AC75 boats from the substantial AC37 telemetry archive, train a small neural network, evaluate it fairly, and connect a coherent learned race simulator to the application. Maximize output quality first; minimize total LLM tokens and repeated work second.

## Start or resume

1. Read AGENTS.md and PROJECT.md. Preserve all pre-existing user changes.
2. Read docs/ac75_learning_task_index.json.
3. Read .forecast/ac75_learning/progress.json if it exists. Do not treat an unchecked claim of completion as evidence.
4. Select the earliest ready task whose dependency artifacts/checks exist. On the first run, begin T00.
5. Read this prompt, the task's referenced global sections, and ONLY its section in docs/ac75_learning_implementation_plan.md. Search section headings, then read bounded ranges. Do not reload the entire long plan each turn.
6. Inspect only the relevant owning functions, source audit, interfaces, and dependency receipts. Avoid routine searches inside Data/, dist/, node_modules/, .agents/teamwork/, .venv/, and generated telemetry.
7. Implement one coherent packet, verify it, record its durable receipt, then continue if context permits. If compaction is approaching, checkpoint after the packet.

This is implementation authorization only when the user actually asks to execute the plan. Merely reading this prompt does not authorize publication, deployment, destructive cleanup, or changes outside the requested scope.

## Non-negotiable decisions

- The AC37 archive contains substantial direct AC75 telemetry; do not base the design solely on the 28-session AC40 replay archive.
- Train and score an actual small neural network. Choosing the default model depends on registered evidence; do not omit the NN because a baseline seems safer.
- Use the full eligible archive, with every source included or explicitly accounted for. No first-N-files or first-N-lines training sample disguised as exhaustive extraction.
- Verified schema/units are prerequisites for binary decoding. Missing external schema is a recorded coverage dependency; keep working on JSONL and other independent tasks.
- Use historical AC37 identity keys; do not silently turn AC38 names into AC37 observations.
- Ground-relative VMG uses COG. Heading is used for TWA/turn geometry.
- Preserve native data and availability; no future frames, later wind, global fitted team ratings, held-out routes, or target columns in inference features.
- Freeze grouped chronological folds before model comparisons. Mark previous exposure and consumed holdouts honestly.
- Version 1 uses a training-only observed-route policy, not a claimed tactical optimizer.
- Maneuver/recovery duration replaces its route segment; no double-counted travel time.
- Train Gaussian log-speed distributions with correct slow-speed censoring. Do not exponentiate unbounded Student-t draws.
- Joint residual sampling and fitted scale represent uncertainty once. Keep fitting sensitivity, model uncertainty, and Monte Carlo error distinct.
- When completion evidence is insufficient, return completion_assumed_on_water scenario probabilities; do not claim observational P(win | both finish). Unconditional values are unavailable, not zero.
- Use one pinned numerical path for saved and interactive inference. Training never runs inside a browser request.
- Keep initial learned candidates experimental. A successful export or passing software test does not prove forecast accuracy.
- Preserve Replay/Analysis/Forecast/Cup compatibility and public artifact hashes unless explicitly authorized otherwise.

## Token and computation discipline

Use small read scopes and deterministic scripts. Do not ask the LLM to inspect raw arrays, tensors, full logs, or large tables. Data snapshots should expose counts, coverage, ranges, hashes, exclusions, and at most three examples.

Store full logs/artifacts under .forecast/ac75_learning/. Reuse caches keyed by actual source/config/code/model hashes. Resume a training run or read its receipt rather than retraining to reconstruct context. Do not retry unchanged failures or expand architecture/search because the score disappoints.

Keep progress receipts factual:

~~~json
{
  "task": "T00",
  "status": "complete",
  "inputs": {"plan_version": "1.0", "artifact_ids": []},
  "changed_paths": [],
  "artifacts": [{"id": "content-id", "path": "relative/path"}],
  "checks": [{"command": "actual command", "exit_code": 0, "receipt": "path"}],
  "coverage_exclusions": [],
  "blockers": [],
  "next_ready": ["T01"]
}
~~~

This is a shape example, not prefilled evidence. Record actual IDs/results. Store creation times outside content-addressed identity. Update progress atomically with a single writer/lock when tasks run concurrently. Keep task_index immutable; progress lives in the separate ignored file.

Use task statuses pending, running, complete, complete_with_exclusions, blocked_external, or failed. A dependency with exclusions is usable only where its task contract permits; propagate those exclusions into all later coverage/model claims.

## Verification and handoff

Honor per-edit quality findings. Fix errors and fixable warnings without changing .aislop/config.yml. Use focused checks first, then the full repository gate at T19. Do not fabricate green results or modify unrelated user code to conceal inherited failures.

A block caused by missing evidence is specific: record the source/field/schema, why it is needed, affected tasks, and safe independent work. Ask only for genuinely missing external information. Routine reversible implementation does not need repeated permission.

At the end of a packet report, in approximately 250 words or fewer:

- What changed and why.
- Actual checks and their outcomes.
- Artifact/model/data IDs and coverage exclusions.
- The next exact task or concrete blocker.

Do not reproduce the master plan or full logs in the handoff. Maintain concise progress during ongoing work. A statistically losing neural model is a valid research result when its implementation and evaluation are complete.

