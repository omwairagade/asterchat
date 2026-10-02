# Aster permanent website plan

## Scope and implementation

Deliver a permanent, responsive Aster website on Manus-managed static hosting. The page presents the upgraded AI chat product and its intended conversation experience, but live AI chat remains disabled until the owner chooses access and usage controls. The site must not call an LLM, collect prompts, or imply that a sample is a real response. The user can return later to choose the access policy and usage limits before live chat is enabled.

Use a dependency-free static HTML/CSS/JavaScript site. Preview uses the configured port 3000; production serves the committed `public/` directory through the managed static build contract. The single route is `/`; no database, provider credential, or request-handling endpoint is included in this release.

## Project structure

- `public/index.html` — responsive one-page product and disabled chat experience.
- `public/manus-routes.json` — declared page route for platform route discovery.
- `public/aster-mark.svg` — original Aster mark and favicon.
- `app.config.ts` — platform project-logo metadata.
- `README.md` — local preview and release notes.
- `plan.md` — design and implementation decisions.

## Design direction

- **Design movement:** contemporary editorial product design, softened by a botanical, paper-like calm.
- **Core principles:** clear hierarchy; generous breathing room; transparent status; calm confidence without pretending the AI is live.
- **Color philosophy:** warm paper and ivory ground the experience; a deep evergreen provides focus; pale sage surfaces give conversation elements a gentle, human feel.
- **Layout paradigm:** an editorial split hero pairs an expressive left-hand narrative with a right-hand conversation vignette; supporting sections follow the reading flow rather than a dashboard grid.
- **Signature elements:** an original four-point Aster mark; a dotted live-status treatment that explicitly reads “AI chat paused”; layered sage conversation cards.
- **Interaction philosophy:** simple anchor navigation and a disabled composer that explains why it is disabled; no fake send action or fake model output.
- **Animation:** restrained entrance and status shimmer only; honor `prefers-reduced-motion`.
- **Typography:** system sans for interface clarity with a serif display face for expressive headlines; consistent compact labels and readable body copy.
- **Brand essence:** a thoughtful AI companion for people turning tangled thoughts into a next step; **calm, candid, capable**.
- **Brand voice:** warm, direct, reassuring. Examples: “Bring the tangle. Find your next clear step.” / “Live replies are paused while access and usage controls are chosen.”
- **Wordmark and logo:** a custom four-point star/asterisk inside an open circular form, paired with a strong “Aster” wordmark.
- **Signature brand color:** evergreen `#1F6C58`.
