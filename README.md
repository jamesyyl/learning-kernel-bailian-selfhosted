# Learning Kernel Bailian Selfhosted

An isolated self-hosted home for the new Bailian learner shell. The starting UI is the supplied **Option 2 subject-cards HTML**, kept intact at `web/index.html`.

## Current slice

This first slice packages the supplied static shell as a Linux/amd64 Docker Compose service. It is suitable for checking the layout and sample navigation locally or on the NAS.

The HTML is currently a demonstration UI. Its sample questions and interactions do not call LK, evaluate answers, or persist learner data. This repository does not yet contain the LK Runtime or SQLite learner store; those must be added as a separately verified integration before using it for real learning records.

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

The Compose project uses its own service and image names. It has no database volume yet because this static slice does not save learner data. Do not configure router port forwarding for this service; use the home network or the existing Tailscale network.

## Next integration gate

Before adding SQLite or answer submission, map the shell's actions to the accepted LK Runtime contracts. The current SDK Runtime is a Cloudflare Worker backed by D1, so self-hosting requires a deliberate storage/HTTP adapter; this repository must not silently evaluate answers or invent new learner-state rules.
