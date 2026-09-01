# Security model

SETU uses layered identity, secret, network, application, and evidence controls.
This document describes the verified portfolio baseline and the remaining
risks; it is not a claim of formal certification.

## Trust boundaries

| Boundary | Control |
|---|---|
| Browser → Next.js | Same-site query check, typed schemas, bounded bodies, no browser credentials |
| Next.js → backend | Server-only configuration, one bounded attempt, local loopback allowlist today |
| Cloud ingress → API | IAM authentication before application API-key authentication; no public principal |
| API → secrets | Per-secret accessor bindings for the runtime identity; payloads never enter source or logs |
| API → database | Dedicated read-only database user over private networking |
| API → provider | Server-only key, structured responses, bounded SDK retry policy, safe diagnostics |
| Model output → user | Claim-specific retrieved-ID membership checks, de-duplication, numerical checks, abstention |

## Credential separation

Browser-safe values and server credentials are different configuration classes.
No credential uses a `NEXT_PUBLIC_` name. The frontend example environment file
contains blank placeholders only, and the repository ignores `.env*` except
reviewed example files.

The target cloud BFF design uses a dedicated frontend service identity to
obtain an audience-bound identity token in server memory. It will attach that
token and the SETU API key to the backend request. Persisted identity tokens and
service-account key files are explicitly outside the design.

## Verified cloud controls

The evidence freeze established:

- Cloud Run requires IAM and has zero public principals;
- the runtime identity has only the project-level Cloud SQL client role needed
  for connectivity;
- Secret Manager access is scoped on each required secret rather than granted
  project-wide;
- the runtime identity has zero user-managed keys;
- Cloud SQL is private-only, encrypted-only, deletion-protected, and has zero
  authorized networks;
- the runtime database user has the read privileges needed for retrieval and no
  role-management or schema-mutation capability; and
- the active revision uses an immutable image digest and private database
  connectivity.

Exact project, service-account, service, connection, address, and secret
identifiers are deliberately excluded from this public repository.

## Application controls

FastAPI enforces an application API key for `/query` and source APIs using
constant-time comparison. Query traffic also passes a bounded process-local
rate limiter and request-size validation. CORS accepts exact configured origins
and rejects a wildcard.

Responses use stable error envelopes and security headers. Internal exceptions,
stack traces, prompts, document bodies, tokens, and connection strings are not
returned. Structured provider diagnostics are reduced to safe categorical
tokens.

The Next.js BFF adds a second validation layer. It rejects unsafe origins,
malformed request/response bodies, oversized payloads, redirects, non-loopback
local upstreams, and unimplemented cloud mode. TanStack Query retries are
disabled so a UI action cannot silently submit a second live request.

## Database boundary

Cloud SQL is not publicly routable. The API reaches it through Direct VPC
networking, and TLS is required by the managed connection path. Deletion
protection and managed backups reduce accidental-loss risk.

Runtime queries are parameterized. Source APIs expose bounded metadata,
eligibility structures, and counts rather than unrestricted document bodies.
The deployed database user is read-only, which is why production `query_logs`
remain empty. Observability should be repaired with structured Cloud Logging,
not by granting write access solely to populate a logging table.

## Model-output controls

Retrieval passages are labelled with existing chunk identifiers before
generation. Returned citations must belong to that retrieved set. Unknown IDs,
duplicates, and exact duplicate evidence are discarded; a retrieval answer with
no valid support abstains rather than falling back to every retrieved chunk.

Digit-form numerical claims are compared with supporting evidence, and the
repository now includes a small reviewed multilingual lexicon for one to three
and first to third. Currency identity, scale, percentage, ordinal, range, and
unit cases are tested. A bounded correction path is available. This lexical
coverage is not general natural-language number understanding; unsupported
words, code-mixed input, and transliteration still require review.

These controls reduce common failure modes. They do not prove semantic truth or
replace source review.

Model-reported confidence is uncalibrated and is not presented as a primary
trust signal. It remains visible only as labeled engineering metadata.

## Eligibility quarantine

The existing eligibility criteria are illustrative and unverified. The browser
workflow is therefore a session-only interaction preview: it makes no positive
or negative determination and sends no profile to the BFF, backend, database, or
provider. Direct personal eligibility requests to the backend fail closed with
a typed, sanitized outcome before criteria lookup or answer generation. Future
activation requires reviewed, versioned rules and official-source provenance.

## Repository publication controls

Before publication, the complete reachable Git history, commit messages,
tracked files, examples, fixtures, documentation, and Git object paths were
audited for credentials and protected deployment identifiers. Real local
provider and application API-key values did not occur in reachable history.
Tracked evaluation data contains short authored queries, fact labels, and chunk
identifiers—not copied source-document bodies.

Ignored local material includes environment files, backups, private keys,
credentials, database artifacts, model artifacts, dependency directories,
framework output, caches, logs, and unselected screenshots.

## Remaining risks

- IAM-protected ingress is still internet-reachable and needs a production
  frontend session boundary before end-user exposure.
- The in-memory rate limiter is per process, not distributed or per user.
- Exact successful provider HTTP-attempt telemetry is unavailable.
- Configured SDK retries allow a theoretical attempt ceiling above the normal
  two-completion workflow.
- Word-form numbers bypass the digit-expression numeric guard.
- Dependency evidence is advisory; direct dependencies are pinned, but the full
  supply chain is not hash-locked or signed end to end.
- Scale-to-zero cold starts and the large model image affect availability and
  latency.
- An alerts-only budget does not cap spend, and trial resources require timely
  teardown.
