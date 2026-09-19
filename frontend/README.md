# Browser product

Node.js 22 and npm are required. From this directory run `npm ci`, `npm run generate`, and `npm run build`.
Types in src/api/schema.d.ts are generated from the actual FastAPI OpenAPI export; never edit them by hand.
From repository root run scripts/product/generate-client.sh after route/DTO changes and inspect regeneration drift.

## Directory layout

- `index.html` is the Vite source template. Edit this file when changing page metadata or the application entry point.
- `src/` contains the browser application, styles, and generated API types.
- `dist/` is the generated production bundle served by FastAPI. Its `index.html` is build output; do not edit it directly.
- `package-lock.json` pins dependencies. `node_modules/` is local, ignored, and recreated with `npm ci`.

Workspace pages use stable routes without project identifiers: `/documents`, `/search`, `/chat`, `/overview`,
`/visualization`, and `/administration`. The active project is selected with the workspace picker and remains
in memory while the app is open. Exact source-receipt links retain project and record identifiers because they
must address one authorized source version.

The browser uses same-origin cookie/CSRF protected APIs. No database/provider configuration belongs in frontend builds.
Production composition serves frontend/dist. For Vite development, run npm run dev and include its loopback origin
in RELEX_TRUSTED_ORIGINS. Source deep links are backed by independently authenticated APIs.
Private project data stays in memory; no localStorage, service worker or private browser cache is used.

The browser verification driver is scripts/product/browser-live.mjs, launched by scripts/product/verify-live.sh
against real A/B services. Playwright Chromium must be installed (`npx playwright install chromium`).
Tests and fixture results do not establish real backend acceptance.
