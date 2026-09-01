# SETU Intelligence Workspace

Evidence-backed intelligence for India’s digital public infrastructure.

This Next.js App Router frontend is a local-first workspace. It ships with a sanitized demo adapter, a loopback-only local adapter, and a fail-closed future cloud contract. It does not connect to the deployed SETU backend during local validation. Its eligibility flow is an illustrative, non-decision preview: no profile is submitted and unverified demonstration criteria cannot produce an eligibility determination.

## Local development

Node.js 20.9 or newer is required (Node.js 22 LTS recommended).

```bash
npm install
npm run dev
```

Demo mode is the safe default and needs no environment file. For controlled local integration, load `SETU_DATA_MODE=local`, a loopback `SETU_BACKEND_URL`, and the existing API key into the Next.js server process without persisting them. Never use a `NEXT_PUBLIC_` variable for credentials.

`SETU_DATA_MODE=cloud` is an interface contract only and fails closed. A later deployment will use a dedicated frontend service identity to obtain an audience-bound Google identity token server-side and attach it alongside the SETU API key held in process memory. Service-account keys and persisted identity tokens are not part of this design.

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
- Zod validates query, claim-to-citation, and response boundaries. Unknown claim citation IDs fail closed.
- TanStack Query manages query and source state with retries disabled.
- `POST /api/query` accepts validated same-site browser input and makes at most one bounded upstream attempt in explicitly enabled local mode.
- `GET /api/sources` and `GET /api/sources/[id]` expose only bounded, validated source contracts.
- The FastAPI source endpoints are API-key authenticated, parameterized, and read-only; they never return full documents or unrestricted chunks.
- No cloud URL, API key, identity token, or secret is included in browser code.

Citation validation proves that an ID belongs to the retrieved response and
passes deterministic de-duplication. It does not prove semantic entailment.
Model-reported confidence is uncalibrated and appears only in engineering
details. The input is deliberately preserved after success for edit-and-resubmit.
