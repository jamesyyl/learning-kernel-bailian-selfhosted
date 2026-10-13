# LK Trusted Evaluation Feedback + Retry Implementation Plan

**Goal:** Show the canonical LK verdict for each U1 raw observation and let the learner retry an incorrect answer without breaking Attempt Chain lineage or duplicating a network-uncertain submission.

**Architecture:** Keep the pinned SDK and its `evaluate_raw_observation` semantics unchanged. A Python host adapter captures the verdict from the SDK's existing evaluation call, maps only an allowlisted verdict/action/message to the learner response, and persists exact-request response replay data in the existing SQLite file. The browser renders those fields only; it never calculates correctness. New learner retries create new capture IDs and monotonically increasing ordinal/count/retry fields, while transport retries reuse the pending capture unchanged.

**Tech Stack:** Python 3.12, canonical vNext Runtime SDK submodule, SQLite adapter, vanilla JavaScript, CSS, unittest.

---

## Tasks

1. [x] **Pin the behavior contract with tests.** Root tests cover all three verdicts, Runtime directives, fail-closed behavior, exact request replay without another SDK call, changed-body/origin handling, and learner-safe output fields. Pinned SDK tests remain the source for evaluation/lineage semantics; its evaluator was also run locally for correct, incorrect, and indeterminate.
2. [x] **Add the Python feedback adapter.** Capture the verdict returned by the one canonical evaluation inside the existing observation path. The browser route allowlist and SDK receipt/evidence flow remain unchanged. SQLite stores only the response needed for exact-request replay, keyed by method/path/origin/body digest.
3. [x] **Update the learner interaction.** Correct and indeterminate results follow the Runtime directive; incorrect stays on the current step and clears the selection for a new attempt. A pending request retains the exact capture for transport retry. The browser does not score.
4. [x] **Preserve attempt lineage.** Each observation point starts at ordinal/count 1; a committed incorrect verdict increments both and sets retryCount to ordinal minus one. A new learner attempt gets a new attemptId, while a transport replay reuses the pending capture and capturedAt.
5. [x] **Validate and document.** Windows 11 + Docker Desktop/WSL2 local suite: 17 passed; Node syntax, Python compileall, Ruff, diff check, Docker health/readiness/schema rev4, repeated U1 seed, actual SDK verdicts, real browser single/multi retry, SQLite persistence/restart and exact-request replay passed. Current isolated test DB has 10 observations, attempt chains, trusted evidence rows, and response-cache entries. Updated README, Docker TODO, and local handoff. No canonical SDK change was needed.
