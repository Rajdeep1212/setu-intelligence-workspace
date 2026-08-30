# SETU backend deployment runbook

This runbook freezes the backend contract established through Milestone 3P
and defines the gates for a vendor-neutral deployment. It does not authorize a
cloud deployment, a provider call, a database change, or a model export.

## Validated scope and architecture

The validated application is one FastAPI process, one PostgreSQL/pgvector
database, two local OpenVINO retrieval artifacts, and one configured external
LLM provider. The smallest supportable deployment is:

```text
browser or trusted client
        |
        | HTTPS, request limits, identity/rate policy
        v
managed ingress or backend-for-frontend
        |
        | private service traffic to api:8000
        v
one SETU API replica ---------> external LLM provider
        |
        | encrypted private connection
        v
managed PostgreSQL + pgvector
```

Use one API worker and one replica for the initial controlled deployment. The
in-process API-key limiter is not shared, local model memory has only been
measured for one worker, and the current API offers no durable job state.
Horizontal scaling requires a shared limiter, an explicit concurrency test,
and database connection-budget review.

The production API image must be immutable and referenced by digest. Stage the
two validated OpenVINO directories on a read-only, versioned artifact volume
before starting the API. Verify their checksums outside the container. A cloud
runtime that cannot mount this artifact set is not compatible with the current
release; choose an artifact-volume/init-job design or deliberately build a new
model-bearing image and revalidate it in a later milestone.

## Decisions required before public traffic

| Decision | Recommended default | Why it is still required |
|---|---|---|
| Audience and identity | Keep the first deployment private or access-controlled. Put a backend-for-frontend or identity-aware gateway in front before a public browser client. | A single static `SETU_API_KEY` is service authentication, not end-user identity, and must never be shipped in frontend code. |
| Long-query contract | Implement a durable asynchronous job API before unrestricted public traffic. | Milestone 3P measured 220.857 s median and 442.967 s p95; there is no end-to-end request deadline or durable resume. |
| Cloud/provider | Select a runtime that supports the required memory, private database networking, immutable image digests, and versioned read-only model artifacts. | No provider, region, domain, quota, or budget has been supplied. |
| Recovery objective | Set explicit RPO/RTO and complete a restore drill before production data is accepted. | Backups without a timed restore test are not a recovery guarantee. |
| Public CORS origin | Supply the exact HTTPS frontend origin or keep browser CORS disabled at the gateway. | The production value is deployment-specific and wildcards are rejected. |

## Latency architecture decision

The evidence is the complete Milestone 3P run: 15/15 cases completed, median
latency 220.857 seconds, p95 442.967 seconds, and one transient provider failure
with one whole-query retry. A normal request makes a route-decision completion
and an answer completion; a bounded grounding/language correction can add one
answer completion. The Groq client has an explicit 5-second connect timeout,
600-second read/write/pool timeout, and two finite SDK retries per completion.
Those settings preserve the validated behavior, but they do not create an
end-to-end deadline.

| Option | Assessment |
|---|---|
| Keep synchronous requests with aligned timeout budgets | Backward-compatible and operationally simple, but suitable only for a private, concurrency-one preview when every hop is verified and the client accepts minutes of silence. It does not solve reconnects, duplicate provider cost, or the absent total deadline. |
| Add streaming or progress responses | Improves perceived progress but does not shorten retrieval/provider work, and citations/grounding are finalized only after structured output validation. SSE also needs authorization, reconnect, and secret-safe event design. It is not sufficient alone. |
| Introduce an asynchronous job API with status polling | Recommended public contract: submit, return `202` plus an opaque job ID, process with bounded workers, and poll or retrieve the final grounded response. It adds durable state, expiry, idempotency, cancellation, authorization, and worker operations, but provides recoverable failure semantics. |
| Reduce provider/model latency | A possible later optimization, not a deployment fix. It can change routing, language, and grounding quality and therefore requires the complete controlled evaluation plus provider-specific quota/cost review. |
| Add safe caching where correctness permits | Exact-response caching could reduce repeated cost only if the key includes normalized query, language, evidence/model/prompt versions, authorization scope, and a bounded TTL. It adds invalidation and privacy risk, must never cache errors or cross security boundaries, and can follow the public API repair. |
| Use a combined staged approach | Recommended sequence: keep a controlled synchronous preview, add durable async submit/status/result, optionally add SSE status, then evaluate model optimization and tightly scoped caching. This preserves the current response schema while adding new endpoints and gives the safest rollback path. |

**Classification: ASYNC/STREAMING REQUIRED BEFORE PUBLIC DEPLOYMENT.** A
private controlled preview may remain synchronous only when ingress and client
timeouts are verified against the real platform, gateway concurrency is one,
and operators accept the absence of a guaranteed upper bound. Do not guess or
silently increase timeouts to make a platform appear compatible.

## Configuration and secrets contract

### Private Cloud Run database contract

Cloud Run uses the platform-mounted Cloud SQL Unix socket. Leave
`DATABASE_URL` unset and inject `DATABASE_USER`, `DATABASE_PASSWORD`,
`DATABASE_NAME`, and `DATABASE_UNIX_SOCKET` as separate values. The password
must come from a numerically pinned Secret Manager version. The socket value
is derived by deployment automation and must not be committed or printed.

The container listens on the runtime-provided `PORT`, runs as UID/GID
`10001:10001`, and includes the two reviewed OpenVINO artifact directories at
`/models/openvino`. Select `LOCAL_INFERENCE_BACKEND=openvino` and keep model
downloads disabled for the private preview. Application startup performs no
schema or extension DDL; database bootstrap remains an operator-only action.

The production Compose overlay resets the service `env_file`, so it does not
inject the repository's local `.env` into the container. Compose can still use
a project `.env` for interpolation unless the operator disables that behavior.
Set `COMPOSE_DISABLE_ENV_FILE=1` for every production render/deploy and inject
values through the deployment platform's secret/config mechanism. Environment
variables supplied by the container runtime are authoritative. Never render
the resolved Compose configuration in logs because it contains secrets.

Production Compose refuses to render unless these values are present:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`
- `DATABASE_URL` using `postgresql+asyncpg`, with a private host and a
  least-privilege application role
- `SETU_API_KEY`, generated randomly and held only by trusted server-side
  clients/gateways
- `CORS_ALLOWED_ORIGINS`, as exact HTTPS origins
- `SETU_API_IMAGE` and `SETU_DB_IMAGE`, as approved immutable image references

At least one of `GROQ_API_KEY` or `GEMINI_API_KEY` must also be non-empty.
Compose cannot express this one-of rule, so `/ready` is the final fail-closed
gate. Groq takes precedence when both exist. The current live quality evidence
is for Groq; the Gemini path requires separate provider verification.

The following bounded operational values have code defaults and can be
overridden deliberately:

| Variable | Default | Meaning |
|---|---:|---|
| `GROQ_CONNECT_TIMEOUT_SECONDS` | 5 | Per-attempt connection timeout. |
| `GROQ_REQUEST_TIMEOUT_SECONDS` | 600 | Per-attempt read/write/pool timeout. |
| `GROQ_MAX_RETRIES` | 2 | SDK retries for eligible transient provider failures. |
| `DATABASE_POOL_SIZE` | 5 | Persistent connections per API process. |
| `DATABASE_MAX_OVERFLOW` | 10 | Temporary connections above the pool size. |
| `DATABASE_POOL_TIMEOUT_SECONDS` | 30 | Pool checkout wait. |
| `DATABASE_POOL_RECYCLE_SECONDS` | 1800 | Maximum pooled connection age before replacement. |

With one replica, the configured database connection ceiling is 15. Recompute
the total before adding workers or replicas and reserve capacity for operations,
backups, and migrations.

## Security boundary

- Terminate TLS at managed ingress and redirect HTTP to HTTPS. Add HSTS at the
  TLS boundary after the production domain is confirmed.
- Keep PostgreSQL private. The production Compose overlay publishes no API or
  database host ports; ingress reaches `api:8000` on a private network.
- Validate host headers and trusted proxy ranges at ingress. The application
  does not use forwarded client IPs for authorization or rate limiting.
- Keep `/health`, `/health/db`, and `/ready` unauthenticated for probes, but
  restrict their network exposure where the platform permits.
- Do not put `SETU_API_KEY` in browser bundles, URLs, logs, or monitoring labels.
- The current static key and process-local global rate limiter are acceptable
  only for a single-replica trusted-client deployment.
- The built-in OpenAPI/docs endpoints disclose the public API shape but not
  credentials. Restrict them at ingress if the deployment policy requires it.

## Health and dependency semantics

- `/health` is process liveness only. It intentionally does not touch the
  database, provider, or model files.
- `/health/db` checks a real PostgreSQL connection with `SELECT 1`.
- `/ready` checks authentication/provider configuration, PostgreSQL, and the
  presence of required OpenVINO files. It does not call the LLM provider or
  compile/run the large local models.

Route liveness to `/health` and readiness to `/ready`. Do not use a live
provider completion as a probe. Alert separately on sustained 502 provider
errors, 503 readiness/retrieval/database errors, elevated 429s, restart/OOM
events, and latency distributions.

## Database change policy, backup, and restore

`db/init.sql` initializes a brand-new volume; it is not a migration system and
is not rerun against an existing database. Before every deployment, compare
the release with the deployed revision:

```bash
git diff --exit-code "$DEPLOYED_REVISION".."$RELEASE_REVISION" -- db/init.sql
```

If that command reports a schema change, stop. Add an ordered, reviewed,
forward-compatible migration and a tested rollback/roll-forward plan in a
separate milestone. Application deployment must not improvise DDL.

Prefer managed encrypted backups and point-in-time recovery. For the reference
Compose database, an operator can create and validate a restricted custom-format
backup before deployment:

```bash
umask 077
mkdir -p backups
BACKUP_FILE="backups/setu-pre-${RELEASE_REVISION}-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db sh -c 'pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$BACKUP_FILE"
pg_restore --list "$BACKUP_FILE" >/dev/null
sha256sum "$BACKUP_FILE" > "$BACKUP_FILE.sha256"
```

Do not test a restore over the live database. Create an isolated target with
the required `vector` and `pgcrypto` extensions, restore there, then verify
schema, counts, sampled retrieval, and permissions. A database owner must
approve any restore command because `--clean` or target replacement is
destructive. Record the measured restore time and set RPO/RTO from that result.

The application currently reads source documents, chunks, and eligibility
criteria. It does not write `query_logs`, feedback, or evaluation rows during
`/query`. If future code starts storing citizen queries or answers, define
data classification, retention, deletion, and access controls first.

## Build and pre-deployment gates

Run these offline gates at the exact release revision:

```bash
git status --short
python -m compileall -q app ingestion eval tests
python -m unittest discover -s tests -v
python -m pip check
docker compose config --quiet
docker compose -f docker-compose.yml -f compose.production.yml config --quiet
git diff --check
```

The production Compose validation assumes all required deployment values are
already injected. Use non-secret placeholders only in CI. Do not print the
resolved configuration.

Build exactly once from the clean revision, scan the resulting image/SBOM,
push it to the selected registry, and deploy by immutable digest:

```bash
docker compose build api
docker image inspect --format '{{.Id}}' setu-api:latest
```

The registry push, signing/attestation mechanism, and cloud image scan depend
on the selected platform and must be documented before execution. The current
CI pins direct Python dependencies but not transitive hashes, base-image
digests, operating-system packages, or GitHub Actions by commit SHA. Treat its
SBOM and non-blocking `pip-audit` result as evidence to review, not a release
signature.

## Deploy procedure

1. Confirm the release commit is reviewed, CI is green, the image digest is
   approved, and the working tree is clean.
2. Confirm an isolated restore drill and the pre-deploy backup meet the chosen
   RPO/RTO.
3. Confirm the database schema comparison above is clean.
4. Stage the exact OpenVINO artifact version read-only and verify checksums.
5. Inject secrets/config and the immutable `SETU_API_IMAGE`/`SETU_DB_IMAGE`
   values through the platform. Do not create a production `.env` in the image.
6. Render only the quiet production configuration check.
7. Start or replace only the API workload. Do not recreate the database.
8. Wait for `/health`, `/health/db`, and `/ready` to return 200.
9. Verify missing and invalid API authentication return safe 401 responses,
   response security headers and `X-Request-ID` are present, restart count is
   zero, and `OOMKilled` is false.
10. Route only controlled traffic. A successful `/query` smoke test is a live
    provider operation and needs separate explicit authorization and a recorded
    request budget.
11. Watch error classes, latency, memory, database connections, and provider
    quota through the observation window before increasing traffic.

For the reference Compose runtime, after the immutable image values and all
required environment values are injected:

```bash
COMPOSE_DISABLE_ENV_FILE=1 docker compose -f docker-compose.yml -f compose.production.yml config --quiet
COMPOSE_DISABLE_ENV_FILE=1 docker compose -f docker-compose.yml -f compose.production.yml up -d --no-deps --no-build --force-recreate api
docker compose ps api db
```

The cloud provider's equivalent rollout command cannot be finalized until a
provider and service are selected. Do not substitute guessed flags.

## Rollback procedure

Keep the previously healthy API digest available. Because this release makes
no database schema or data change, rollback is an API-only replacement:

1. Stop routing new requests to the failed revision.
2. Set `SETU_API_IMAGE` to the previously approved immutable digest.
3. Replace only the API workload; do not rebuild or recreate PostgreSQL.
4. Require `/health`, `/health/db`, and `/ready` 200, then repeat the safe auth
   and runtime checks.
5. Reopen controlled traffic and monitor the same observation window.

Reference Compose command after setting the previous digest:

```bash
COMPOSE_DISABLE_ENV_FILE=1 docker compose -f docker-compose.yml -f compose.production.yml up -d --no-deps --no-build --force-recreate api
```

If a future release includes a schema change, code rollback is permitted only
when the old code is forward-compatible with the migrated schema. Prefer a
forward fix; never restore an old database over current production without a
declared data-loss decision, owner approval, and a verified backup.

## Resource and cost gates

Milestone 3K observed approximately 2.70 GiB for one real OpenVINO query, the
two FP32 artifact directories total approximately 4.28 GiB, and the validated
API image is approximately 646 MB. Use at least a 4 GiB memory class for the
first single worker, then measure peak RSS, CPU saturation, cold-start time,
and disk use on the selected runtime before setting production limits. CPU,
autoscaling, and concurrency values are not yet evidence-backed.

Primary cost drivers are the always-on API memory class, PostgreSQL storage and
backups, model-artifact storage/transfer, logs, and two normal LLM completions
per query plus bounded correction/SDK retries. Provider prices, quotas, regions,
egress, and data-processing terms require external verification after the
provider and account are selected.

## Known limitations at freeze

- Public traffic needs a durable async job contract (optionally SSE status).
- Static service authentication is not end-user identity.
- Rate limiting is process-local and global, not per user or distributed.
- Provider configuration readiness does not prove provider reachability.
- OpenVINO readiness checks file presence, not checksums or a warm inference.
- Database migrations are not implemented; `init.sql` is bootstrap-only.
- Restore time, RPO, and RTO are not yet measured.
- Logs are correlation-friendly text on stdout, not a defined centralized
  schema/retention pipeline.
- Base images, transitive Python dependencies, OS packages, and CI actions are
  not fully digest/hash pinned; dependency audit is non-blocking.
- The 2026-08-29 audit reported nine advisory records across installer tooling
  `pip 24.0` and `setuptools 79.0.1` (including duplicate records from the
  system-site-packages audit environment). The hardened runtime cannot modify
  its virtual environment and exposes no package-install endpoint, but the
  tools remain present. Upgrade or remove them only in a separately tested
  dependency/image change.
- No provider/runtime/domain/budget has been chosen, so platform limits and
  commands remain an explicit deployment decision.
