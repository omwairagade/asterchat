# Aster — account-backed live AI chat

Aster is a responsive chat website with open registration through Manus sign-in. Anyone with the site link can join using a Manus account; the first successful sign-in automatically creates their Aster account. There is no Aster invite list.

Each account can submit **100 user messages per UTC day**, shared across browsers and devices. The server reserves each message atomically in the managed database, so simultaneous requests cannot exceed the cap. The database stores only a SHA-256 pseudonymous account key and daily counts. It does not store chat prompts or replies. The current transcript exists in the page's memory and is lost on reload or sign-out.

Aster streams replies from the Manus AI chat-completions service. Provider credentials stay server-side. AI requests use the project's service identity and consume the project's AI credits. Aster applies a 4,000-character per-message limit and a bounded recent conversation context.

## Local development

The platform supplies Manus OAuth, AI-service, and managed-database environment variables to the bound project environment. Do not copy those values into source files or `.env` files.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python scripts/migrate.py
uvicorn app_server:app --host 0.0.0.0 --port 3000 --no-access-log
```

Use the managed Cloud Preview or published URL for a real OAuth callback. A plain loopback URL is not automatically accepted by the Manus sign-in portal. OAuth callbacks are allowlisted in `PUBLIC_APP_ORIGINS` to the current published and managed Preview origins; add any custom domain there before using it. The migration creates only Aster account and daily-usage tables, plus migration history; development and production share the managed database.

## Application structure

- `public/index.html` and `public/aster-chat.js` provide the landing page, Manus sign-in, quota display, and streaming chat UI.
- `app_server.py` provides OAuth callback/session APIs, quota enforcement, health checks, and static files for development.
- `aster/auth.py` validates the `webdev_app_session` HS256 project JWT and implements the OAuth state/identity flow.
- `aster/db.py` stores opaque account keys and enforces per-day quotas using atomic MySQL updates.
- `aster/llm.py` streams Manus AI responses and sanitizes rendered Markdown.
- `migrations/` and `scripts/migrate.py` define and apply the additive schema.
- `Dockerfile` builds the hosted Python server. Published routes send `/api/*` to the server and page/assets to the static build.

## Privacy and limits

Aster persists account-key hashes and per-account UTC daily message counts only. It does not persist conversation text in its database. Messages are sent to Manus AI to generate replies; this statement describes Aster's storage, not the AI service's separate handling. Sign out clears the browser session cookie. A new UTC allowance begins at 00:00 UTC.
