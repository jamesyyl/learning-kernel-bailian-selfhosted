# Learning Kernel Bailian Selfhosted

An isolated self-hosted home for the new Bailian learner shell. The starting UI is the supplied **Option 2 subject-cards HTML**, kept intact at `web/index.html`.

## Current stage

The supplied static shell and a Python Runtime host are packaged as separate Linux/amd64 Compose services. The Python host loads the canonical vNext Runtime glue from the pinned SDK submodule and gives it a SQLite adapter for prepared statements and atomic batches. The migration runner records exact checksums and rejects edits to migrations that have already been applied.

The SDK's four vNext Runtime SQL migrations were applied to SQLite 3.53.1 during development; they created schema revision 4. The adapter, migration runner, and learner-route allowlist have focused local tests.

Windows 11 + WSL2 validation passed on 2026-10-12 with Docker 29.8.2 and Compose 5.5.1. Both services build and become healthy; `/healthz` and `/api/ready` return HTTP 200 with schema revision 4. The Math U1 seed succeeded on its first run and on a repeat run. The Nginx same-origin route returns the pinned Pack's real `learning-kernel.surface-ir@1` response.

The Option 2 shell runs a local Math U1 activity. It renders the Runtime-issued prime/composite and divisibility steps, accepts single and multiple selections, and submits only `bailian.observation-capture@1` raw responses. PR #2 is merged: trusted evaluation in the canonical SDK is the only source of correct/incorrect/indeterminate feedback; the browser only renders that result and follows Runtime directives. Incorrect answers stay on the same question for another attempt, and exact observation-request replays return the cached response without another Runtime evaluation.

Issue #4 expands Math U1 through all five Regions, 17 Places, 37 Roads, and 26 Task Families in Pack 0.3.4. The canonical Runtime makes Next Decisions from persisted Evidence and the selected Map Place; Map exploration asks the same Runtime for a Family Surface. The SDK registers a deterministic generator for each Family, independently verifies ten distinct variants per Family, and admits all 260 candidates through the protected Activity Pool boundary. The browser renders learner-safe Surfaces and submits raw responses; it does not grade answers or recommend activities.

The complete local Runtime acceptance passed with 19 root tests. A same-learner sequence completed 10 distinct generated activities; all 17 Places returned canonical Surfaces, and each of the 26 Families returned a Surface and trusted Evidence. A real in-app browser exercised single-choice, multi-choice, multi-classification, integer, structured factorization, and text responses, including wrong-answer retry and a distinct canonical next prompt. The reproducible coverage matrix and trace are in [the evidence folder](docs/evidence/); see [the handoff](docs/LOCAL_CODEX_HANDOFF.md) for test scope, known baseline test failures, publication status, and remaining work.

Other subjects, growth summaries, parent summaries, and targeted/custom modes are labeled as unavailable until they are connected to LK. The SQLite database is the local persistent store; the browser cannot call Pack management or trusted-evaluation routes.

The original `learning-kernel-bailian` repository is unchanged. The canonical SDK change is isolated on the separate, unmerged SDK branch for PR #335; SDK `main` is unchanged.

The self-hosted Runtime consumes the SDK through a pinned Git submodule; cloning for a Runtime build requires read access to that private repository. No SDK source is copied into this repository. Root PR #3 remains Draft, and SDK PR #335 remains unmerged; merge order is SDK #335 before Root #3. Neither PR has been merged.

## Run locally

1. Clone the latest published `main` branch with the SDK submodule initialized (the GitHub account needs read access to `learning-kernel-sdk`):

   ```sh
   git clone --recurse-submodules --branch main https://github.com/jamesyyl/learning-kernel-bailian-selfhosted.git
   ```

2. Copy `.env.example` to `.env`.
3. Generate a secret with `openssl rand -hex 32` and paste it into `BAILIAN_SERVICE_BINDING_SECRET` in `.env`.
4. Keep `BAILIAN_ORIGIN` equal to the exact origin used in the browser, including scheme and port. For NAS access, replace the local default with the NAS/Tailscale URL.
5. Start the services:

   ```sh
   docker compose up -d --build
   ```

6. Seed the first local Math U1 activity after pulling this branch and rebuilding:

   ```sh
   docker compose exec runtime python -m api.seed_u1
   ```

   A successful run prints the installed Math U1 Pack version and learner/environment. It is safe to rerun; the command verifies that Surface is available.

7. Open <http://localhost:8080> (or the configured address).
8. Check web health at <http://localhost:8080/healthz> and Runtime schema status at <http://localhost:8080/api/ready>.

Stop it with:

```sh
docker compose down
```

The shell uses Google Fonts and Phosphor Icons from their public CDNs. The main hero artwork is embedded in the HTML.

## NAS

Set `BAILIAN_DATA_PATH` to a NAS directory outside the checkout, for example `/vol1/docker/bailian-selfhosted/data`, and create that directory before starting Compose. SQLite lives at `learning-kernel.sqlite3` in that directory. Do not configure router port forwarding: this first version has no user login and is intended for the trusted home network or existing Tailscale network.

## Continue development locally

For the WSL Codex handoff, local verification evidence, and remaining work, read [docs/LOCAL_CODEX_HANDOFF.md](docs/LOCAL_CODEX_HANDOFF.md).

## Current limits and next work

See [the ordered Dockerization TODO](docs/DOCKERIZATION_TODO.md). PR #1 and PR #2 are merged; Issue #4's full Math U1 Map, generator, Pool, and Surface path is implemented and locally verified. Keep Root PR #3 Draft and SDK PR #335 unmerged for user review. Other subjects, growth/parent summaries, custom practice modes, FnOS/NAS deployment, NAS access boundaries, and database backups remain future work. Keep the browser boundary limited to Surface reads and raw-observation writes, and do not infer progress in the page.
