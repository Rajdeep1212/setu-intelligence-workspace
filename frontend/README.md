# SETU Intelligence Workspace

Evidence-backed intelligence for India’s digital public infrastructure.

This Next.js App Router frontend is the local-only Milestone 4A-1 foundation. It ships with a sanitized demo adapter and a fail-closed server-side BFF boundary; it does not connect to the deployed SETU backend.

## Local development

Node.js 20.9 or newer is required (Node.js 22 LTS recommended).

```bash
npm install
npm run dev
```

Copy `.env.example` to `.env.local` only when local configuration is needed. Demo mode is the safe default. Never use a `NEXT_PUBLIC_` variable for credentials.

## Verification

```bash
npm run typecheck
npm run lint
npm run test:run
npm run build
```

For browser checks, start the app on `http://127.0.0.1:3000` and run `npm run test:e2e`.

## Architecture

- Server Components render the landing, sources, trust, and case-study shells.
- Focused Client Components own workspace and source-explorer interactions.
- Zod validates query and response boundaries.
- TanStack Query manages the staged demo mutation lifecycle.
- `POST /api/query` accepts only validated browser input and remains fail-closed for live mode.
- No cloud URL, API key, identity token, or secret is included in browser code.
