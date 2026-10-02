# Aster live-chat implementation plan

## Scope and implementation

Turn the public Aster site into an account-backed, live AI chat. Anyone with the site link may register through the default Manus OAuth sign-in and chat after authentication; there is no per-user allowlist. A Manus identity is the stable account key, so the daily allowance applies across browsers and devices. Each signed-in account may submit up to 100 user messages per UTC day. Enforce the limit atomically on the server and persist the account mapping and daily count in the managed MySQL database.

The browser sends chat turns to the Python application server. The server validates the Manus OAuth application session, checks and reserves quota, then streams the response from Manus's OpenAI-compatible chat-completions service. Keep all platform credentials server-side. Do not persist prompt or response text in the Aster database; conversations remain transient in the visitor's current page. Usage counts persist across restarts. Because Cloud Preview rebases request origins to its internal listener, OAuth takes the browser-visible origin and permits only the project's published and Preview origins (plus local loopback for development). Database provisioning is already approved and has been applied as an additive capability change; migrations create only the account mapping and daily-usage records.

Manus OAuth is the default provider because no alternative was requested. A visitor needs a Manus account to sign in; first successful sign-in registers them for Aster automatically. Public page routes remain static, and `/api/*` is served by the Python container. The deployment remains hybrid, with the static site in `public/` and authenticated APIs/streaming in the server container. Platform LLM calls use the project's Manus service identity and consume project AI credits.

## Project structure

- `public/index.html` — Aster landing page, sign-in state, quota display, accessible chat UI.
- `public/aster-chat.js` — browser login, session, usage, and streaming chat interactions.
- `public/manus-routes.json` — page-route declaration; API endpoints are excluded.
- `public/aster-mark.svg` — Aster mark and favicon.
- `app_server.py` — Python HTTP/API server, OAuth callbacks, session verification, quota enforcement, and AI response streaming.
- `migrations/` — idempotent, versioned MySQL schema for Manus-linked accounts and UTC daily usage counts only.
- `requirements.txt` — pinned server dependencies.
- `Dockerfile` — installs the server dependencies and runs the application on the platform `PORT`.
- `README.md` — setup, OAuth, quota, data-retention, and deployment notes.
- `TODO.md` — acceptance outcomes for open sign-in, 100/day account quota, and live AI chat.

## Design direction

- **Design movement:** contemporary editorial product design, softened by a botanical, paper-like calm.
- **Core principles:** clear hierarchy; generous breathing room; transparent access/usage status; calm confidence.
- **Color philosophy:** warm paper and ivory ground the experience; deep evergreen provides focus; pale sage surfaces give conversation elements a gentle, human feel.
- **Layout paradigm:** editorial split hero pairs the narrative with a conversation vignette; authenticated chat appears in the same surface without turning the site into a dashboard.
- **Signature elements:** the original four-point Aster mark; a clear signed-in/quota status; layered sage conversation cards.
- **Interaction philosophy:** sign-in is explicit; the daily quota is visible; messages stream as they arrive; a reached limit is explained without silently dropping input.
- **Animation:** restrained response/loading motion; honor `prefers-reduced-motion`.
- **Typography:** system sans for interface clarity with a serif display face for expressive headlines; compact labels and readable body copy.
- **Brand essence:** a thoughtful AI companion for people turning tangled thoughts into a next step; **calm, candid, capable**.
- **Brand voice:** warm, direct, reassuring. Examples: “Bring the tangle. Find your next clear step.” / “100 messages per account each UTC day. Your count follows your Manus account.”
- **Wordmark and logo:** a custom four-point star/asterisk in a rounded mark, paired with a strong “Aster” wordmark.
- **Signature brand color:** evergreen `#1F6C58`.
