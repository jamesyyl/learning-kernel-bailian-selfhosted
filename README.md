# Learning Kernel Bailian Selfhosted

An isolated self-hosted home for the new Bailian learner shell. The starting UI is the supplied **Option 2 subject-cards HTML**, kept intact at `web/index.html`.

## Current stage

The supplied static shell and a Python Runtime host are packaged as separate Linux/amd64 Compose services. The Python host loads the canonical vNext Runtime glue from the pinned SDK submodule and gives it a SQLite adapter for prepared statements and atomic batches. The migration runner records exact checksums and rejects edits to migrations that have already been applied.

The SDK's four vNext Runtime SQL migrations were applied to SQLite 3.53.1 during development; they created schema revision 4. The adapter, migration runner, and learner-route allowlist have focused local tests.

Windows 11 + WSL2 validation passed on 2026-10-12 with Docker 29.8.2 and Compose 5.5.1: both images built, both services became healthy, `/healthz` returned `ok`, and Runtime readiness stayed at schema revision 4 after restarting Runtime. The mounted `data/learning-kernel.sqlite3` file was present after restart. After initializing the pinned private SDK submodule, the complete local unittest suite passed: 11 tests, 0 skipped, including the canonical SDK migration test.

The HTML remains a demonstration UI: it does not call LK or persist learner data. No Pack is installed, and no validated Activity Pool entry is available. The SDK's current U1 Activity Pool supply gate is still open; do not insert unverified sample activities as a shortcut. Do not use this stage for real learning records.

The original `learning-kernel-bailian` repository and the canonical `learning-kernel-sdk` remain separate and are not changed by this project.

The self-hosted Runtime consumes the SDK through a pinned Git submodule at `b63404173e39a37685e9914523ba3704ac1664ad`; cloning for a Runtime build requires read access to that private repository. No SDK source is copied into this repository.

## Run locally

1. Clone the work branch with the SDK submodule initialized (the GitHub account needs read access to `learning-kernel-sdk`):

   ```sh
   git clone --recurse-submodules --branch feat/option2-docker-shell https://github.com/jamesyyl/learning-kernel-bailian-selfhosted.git
   ```

2. Copy `.env.example` to `.env`.
3. Generate a secret with `openssl rand -hex 32` and paste it into `BAILIAN_SERVICE_BINDING_SECRET` in `.env`.
4. Keep `BAILIAN_ORIGIN` equal to the exact origin used in the browser, including scheme and port. For NAS access, replace the local default with the NAS/Tailscale URL.
5. Start the services:

   ```sh
   docker compose up -d --build
   ```

6. Open <http://localhost:8080> (or the configured address).
7. Check web health at <http://localhost:8080/healthz> and Runtime schema status at <http://localhost:8080/api/ready>.

Stop it with:

```sh
docker compose down
```

The shell uses Google Fonts and Phosphor Icons from their public CDNs. The main hero artwork is embedded in the HTML.

## NAS

Set `BAILIAN_DATA_PATH` to a NAS directory outside the checkout, for example `/vol1/docker/bailian-selfhosted/data`, and create that directory before starting Compose. SQLite lives at `learning-kernel.sqlite3` in that directory. Do not configure router port forwarding: this first version has no user login and is intended for the trusted home network or existing Tailscale network.

## Next integration gate

See [the ordered Dockerization TODO](docs/DOCKERIZATION_TODO.md). The next product gate is an accepted Pack plus exact-release, validated Activity Pool supply; the SDK's U1 supply Gate B is still open. Only after that can the shell render a real LK Surface and submit raw observations. Keep the SQLite data directory outside the checkout on FnOS. Local network use and LK wiring are the immediate priorities; backups can be added after the learning loop works. The browser boundary must not submit trusted evaluation results or invent learner-state rules.
