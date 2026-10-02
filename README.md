# Aster AI Chat — permanent site

This is the managed-hosting website for Aster. The visitor-facing experience is a dependency-free, responsive static site in `public/`; a small Python standard-library server provides the health endpoint required by the managed container deployment.

**Live AI chat is intentionally disabled.** The composer is disabled, the server exposes no chat or model-provider endpoint, and the site does not submit or persist visitor prompts. Do not add an AI provider connection until the owner chooses access and usage controls.

## Local preview

The project preview runs on port 3000:

```bash
python3 app_server.py
```

Visit `http://localhost:3000`. The server serves the files in `public/` and returns `200 ok` from `/api/healthz`.

## Production shape

The managed static build publishes the committed `public/` directory. The container starts `app_server.py` on the platform-provided `PORT` (default `3000`) and serves `/api/healthz`; published routing sends `/api/*` to the container and visitor-facing website paths to the static output. The server has no AI, prompt submission, session, or persistence API.

## Project files

- `public/index.html` — responsive Aster website with an explicitly paused chat composer.
- `public/manus-routes.json` — the `/` page route declaration.
- `public/aster-mark.svg` — original wordmark mark and favicon.
- `app_server.py` — static-file server and health endpoint only.
- `Dockerfile` — minimal production container.
- `app.config.ts` — platform project-logo metadata.
