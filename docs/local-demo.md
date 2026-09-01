# Local demo guide

The frontend’s default demo mode is the safest way to review SETU. It uses only
sanitized fixtures bundled with the application and makes no backend, database,
provider, or cloud request.

## Requirements

- Node.js 22.x
- npm from the same Node.js 22 toolchain

Verify the runtime before starting:

```bash
node --version
npm --version
```

The Node.js output must begin with `v22.` for the validated setup.

## Start the demo

```bash
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

No `.env` file is needed. With `SETU_DATA_MODE` absent, the BFF selects `demo`
mode.

Open these loopback routes:

| Route | What to review |
|---|---|
| `http://127.0.0.1:3000/` | Product framing and trust summary |
| `http://127.0.0.1:3000/workspace` | Claim-linked research demo and non-decision eligibility preview |
| `http://127.0.0.1:3000/sources` | Searchable, filterable evidence explorer |
| `http://127.0.0.1:3000/system` | Security architecture and known limits |
| `http://127.0.0.1:3000/case-study` | Controlled-query engineering evidence |

The workspace’s research interactions return deterministic demo responses. A
mode label makes that boundary visible. The eligibility workflow is a
non-decision interaction preview using unverified demonstration data; it never
sends its profile to the BFF, backend, database, or provider.

## Data modes

### Demo

`demo` is the default and needs no configuration. All answers, citations,
source summaries, and eligibility records are sanitized local fixtures.

### Controlled local integration

`local` is opt-in and intended only for an explicitly running loopback backend.
Load these values into the Next.js server process without committing them:

```dotenv
SETU_DATA_MODE=local
SETU_BACKEND_URL=http://127.0.0.1:8000
SETU_BACKEND_API_KEY=<local-only-api-key>
```

The URL validator rejects HTTPS downgrades from arbitrary hosts, non-loopback
hosts, embedded credentials, paths, query strings, and fragments. The API key
stays server-side. Do not prefix it with `NEXT_PUBLIC_`.

Local mode can make real backend and provider requests. Do not enable it for a
visual portfolio review unless that activity is separately intended and
budgeted.

### Cloud

`cloud` currently fails closed. It is a contract for a future deployed frontend
that will use a dedicated service identity and an audience-bound IAM token in
server memory. It is not a hidden or incomplete path to the existing backend.

Personal eligibility submission also fails closed in every adapter mode until
reviewed, versioned rules and official-source provenance exist. Completing the
four-step preview demonstrates form state and missing-information handling only;
it never reports a positive or negative eligibility determination.

## Validation

With the demo server running:

```bash
npm run typecheck
npm run lint
npm run test:run
npm run build
npm run test:e2e
```

The browser suite covers the portfolio routes and does not submit a real
`/query`. Stop the server with `Ctrl+C` when the review is complete.

## Safe review checklist

- Keep the URL on `127.0.0.1` or `localhost`.
- Confirm the visible mode is `demo`.
- Do not add an API key to browser storage, source code, a screenshot, or a URL.
- Do not commit `.env`, `.next`, `node_modules`, Playwright output, or arbitrary
  screenshots.
- Treat demo eligibility content as interface evidence, not current legal or
  benefits advice.
