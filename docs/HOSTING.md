# SETU hosting (zero cost)

How the public SETU site is hosted without spending money, and what a
visitor is really looking at. Owner decisions of 8 Oct 2026; the reasoning
for the backend is in [DEPLOYMENT.md](DEPLOYMENT.md).

## The free setup

| Part | Where | Plan | Limits to remember |
|---|---|---|---|
| Website (Next.js, `frontend/`) | Vercel | Hobby (free) | Personal, non-commercial use |
| Database (PostgreSQL + pgvector) | Supabase | Free | 500 MB; the project pauses after 7 idle days |
| Backend (FastAPI, local models) | The owner's laptop | none | Not reachable from the internet |

Rules that keep it free and safe:

- Free tiers only. If any step asks for a card, a paid plan or a trial,
  stop and ask the owner.
- The public site runs in demo mode (`SETU_DATA_MODE=demo`) until the owner
  approves live answers.
- No secret or connection string goes into the repository, into logs or
  into Vercel. The database connection string lives only in the local
  `.env` on the laptop.
- The security update ([#13](https://github.com/Rajdeep1212/setu-intelligence-workspace/pull/13))
  must be merged before the first public deploy.

## Vercel settings

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Next.js |
| Build Command | default (`npm run build`, which runs `next build --webpack`) |
| Production Branch | `master` |
| Environment variable, Production | `SETU_DATA_MODE` = `demo` |
| `SETU_BACKEND_URL` | must not be set |
| `SETU_BACKEND_API_KEY` | must not be set |

`SETU_DATA_MODE` is read on the server only. When it is missing or has any
value other than `local` or `cloud`, the site falls back to `demo`, so a
mistake in this setting cannot switch on live answers. Setting it anyway
makes the choice visible. `local` only accepts a loopback backend address,
so it cannot work on Vercel; `cloud` is switched off in code.

## What is real and what is illustrative on the demo site

| Page | Status | What the visitor sees |
|---|---|---|
| Roadside Mode (`/roadside`) | Real data | The reviewed offence tables in `data/traffic_offences`, with the official source link for each verified amount. Rows without a verified amount say so and show no number. Works offline after one visit. |
| Workspace answers (`/workspace`) | Illustrative | One fixed example answer about India's digital public infrastructure, in English, Hindi or Bengali to match the question. **The answer does not change with the question.** Every answer is headed "Illustrative example: not a retrieved answer" and the page shows a DEMO badge. |
| Eligibility mode | Illustrative | A preview of the experience only. It makes no eligibility decision. |
| Sources (`/sources`) | Illustrative | Four sample source records marked as demo fixtures. |
| System trust, Case study | Static text | Descriptions of the design and of one past controlled run. |

In demo mode the site makes no request to a backend, a database, a model
provider or any other host.

Checked on 8 Oct 2026 against a local production build with
`SETU_DATA_MODE=demo`:

- an English, a Hindi and a Bengali question each returned `data_mode: demo`
  and showed the "Illustrative example" heading;
- the only API call from the browser was `POST /api/query` on the same site;
  no request went to any other host;
- `/roadside` reloaded with the network off and still showed the West Bengal
  amounts and stayed interactive.

Screenshots from that build are in [images/](images/).
