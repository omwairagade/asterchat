# Aster AI Chat — permanent site

This is the managed-hosting website for Aster. It is a dependency-free, responsive static site with an honest preview of the future chat experience.

**Live AI chat is intentionally disabled.** The composer is disabled, no chat API or AI service is called, and the site does not submit or persist visitor prompts. Do not enable a provider connection until the owner chooses access and usage controls.

## Local preview

```bash
python3 -m http.server 3000 --bind 0.0.0.0 --directory public
```

Visit `http://localhost:3000`. The app is served from `public/`, and `public/manus-routes.json` declares the single `/` route.

## Production

The managed static build serves the committed `public/` directory. Keep production assets in `public/`; no Node/Python application server is required to serve the deployed page.
