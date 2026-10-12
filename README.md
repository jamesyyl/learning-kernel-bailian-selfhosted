# Learning Kernel Bailian Selfhosted

An isolated self-hosted home for the new Bailian learner shell. The starting UI is the supplied **Option 2 subject-cards HTML**, kept intact at `web/index.html`.

## Current stage

The supplied static shell is packaged as a Linux/amd64 Docker Compose service. A small SQLite adapter now covers the D1-shaped prepared-statement calls used by the vNext Runtime glue, including atomic batches. A migration runner tracks exact migration checksums and rejects edits to migrations that have already been applied.

The four current vNext Runtime SQL migrations were applied to SQLite 3.53.1 during development; they created schema revision 4. The adapter and migration runner have focused local tests.

This is storage groundwork only. The HTML remains a demonstration UI: it does not call LK or persist learner data. The SQLite adapter is not yet connected to `VNextRuntimeService`, and Compose still runs only the static web container. Do not use this stage for real learning records.

The original `learning-kernel-bailian` repository and the canonical `learning-kernel-sdk` remain separate and are not changed by this project.

## Run locally

1. Copy `.env.example` to `.env` if you want to customize the port.
2. Start the service:

   ```sh
   docker compose up -d --build
   ```

3. Open <http://localhost:8080> (or the configured port).
4. Check service health at <http://localhost:8080/healthz>.

Stop it with:

```sh
docker compose down
```

The shell uses Google Fonts and Phosphor Icons from their public CDNs. The main hero artwork is embedded in the HTML.

## NAS

The Compose project uses its own service and image names. It has no database volume yet because the Runtime is not connected. Do not configure router port forwarding for this service; use the home network or the existing Tailscale network.

## Next integration gate

Pin the canonical SDK source, compose the existing vNext Runtime service over this SQLite adapter, and expose it through a same-origin web proxy. Then wire only the shell actions covered by the accepted Runtime contracts. The self-hosted adapter must not evaluate answers or invent learner-state rules.
