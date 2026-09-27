# Operations Runbook

This runbook describes the supported self-hosted Compose deployment. Production
operators must supply managed secrets, TLS termination, monitoring, and backup
storage appropriate to their environment. Never put credentials or student data
in tickets or logs.

## Readiness and diagnostics

1. Check `GET /api/v1/health` for process liveness and `GET /api/v1/ready` for
   PostgreSQL and Redis readiness. A 503 means the application is not ready.
2. Use the response `X-Correlation-ID` to find a request in API logs. Do not log
   request bodies, cookies, authorization headers, prompts, or document text.
3. Check `docker compose -f infra/docker/docker-compose.yml ps` and the relevant
   service logs. Logs and job states are diagnostics, not a substitute for
   aggregate production metrics and alerting.
4. For document jobs, inspect the owner-visible document status and worker logs;
   retry only through the authenticated API after correcting the underlying
   dependency. A malware scanner outage must never be treated as a clean scan.

## Metrics

Scrape `GET /metrics` from a trusted internal monitoring network. It exposes
Prometheus text counters for HTTP requests by normalized route/method/status,
request-duration histograms, assistant outcome routes, and aggregate assistant
feedback rating/report counts. It does not label metrics with user IDs, email,
document IDs, query strings, prompts, or response content. Counters are
process-local and reset on restart; scrape every API instance and let the
monitoring system aggregate them. The endpoint is not an admin dashboard and
must not be exposed as a public student feature. Combine it with `/api/v1/health`,
`/api/v1/ready`, worker logs/job states, and infrastructure monitoring. Feedback
is optional and stores only the response correlation, rating, and report flag;
free-form comments are not collected.

## Deploy and migrate

1. Build and review the release artifact and CI results before deployment.
2. Confirm secrets and service endpoints in the deployment environment; do not
   use repository or Compose development defaults in production.
3. Take a database backup and verify object-store recovery points before a
   schema-changing release.
4. Apply `alembic upgrade head` from `apps/api`, then deploy API and worker
   processes compatible with that schema.
5. Verify `/api/v1/health`, `/api/v1/ready`, authenticated student access,
   document processing, and AI-disabled fallback. Record the release and
   migration revision.

## Rollback

1. Stop the rollout and retain the failing release logs with correlation IDs.
2. Roll back application and worker images to the last known good release.
3. Do not downgrade a migration automatically. Restore a pre-release database
   snapshot only when forward repair is unsuitable and the data-loss impact is
   approved by the data owner.
4. Verify readiness, authentication, student content, and document ownership
   after recovery. Reconcile queued jobs before resuming workers.

## Database backup and restore exercise

Backups must be encrypted, access-restricted, retained under the deployment
policy, and stored outside the database host. The deployment owner must schedule
and record restore exercises; an untested backup is not considered recoverable.

For the Compose PostgreSQL service, create a logical backup (substitute the
deployment's protected credential mechanism; never place a real password in shell
history):

```sh
docker exec lexaware-postgres pg_dump -U lexaware -Fc -f /tmp/lexaware.dump lexaware
docker cp lexaware-postgres:/tmp/lexaware.dump ./lexaware.dump
```

Restore into a fresh, isolated PostgreSQL database with the matching pgvector
extension and verify the dump before directing application traffic to it:

```sh
docker exec lexaware-postgres createdb -U lexaware lexaware_restore
docker cp ./lexaware.dump lexaware-postgres:/tmp/lexaware.dump
docker exec lexaware-postgres pg_restore -U lexaware -d lexaware_restore /tmp/lexaware.dump
```

After verification, remove the host/container dump using the approved retention
policy and drop only the disposable restore database. Encrypt and restrict
access to any retained backup before copying it off-host.

Check migration state with `alembic current` and `alembic check`, then run
representative account, knowledge, document metadata, and audit queries. Record
the backup timestamp, restore duration, validation, and gaps. Database restore
does not restore private document objects: use the object store's encrypted
versioned backup or replication and separately exercise recovery of the private
document bucket. Do not restore a bucket as public. Validate object keys and
owner metadata before enabling downloads. Define and document recovery point and
recovery time objectives with the deployment owner; the project does not claim
measured objectives.

## MinIO private-object backup and restore

Use a dedicated MinIO client alias configured from the deployment secret store;
do not put credentials in a script, shell history, or command output. Back up to
encrypted storage outside the MinIO host. For a simple Compose deployment, `mc
mirror --preserve` copies objects and supported metadata from the private bucket
to an operator-controlled backup path:

```sh
mc mirror --preserve local/lexaware-documents-private /secure-backup/lexaware-documents-private
```

For recovery, create an empty private destination bucket and mirror the protected
backup into it:

```sh
mc mb local/lexaware-documents-private-restore
mc mirror --preserve /secure-backup/lexaware-documents-private local/lexaware-documents-private-restore
mc anonymous set none local/lexaware-documents-private-restore
```

Compare object names and counts, then compare checksums for sampled or all
objects using the deployment's checksum-capable storage tooling. Verify the
destination anonymous policy is `none`, and retrieve a synthetic object using
the service identity. Verify anonymous retrieval is denied before considering
the restored bucket. The database stores object keys and ownership grants;
restore a matching database snapshot and check owner-scoped application
downloads before redirecting traffic. Never test recovery with a student's
document or by making a bucket public. Mirror alone is not a versioned backup:
production retention and point-in-time recovery require versioning/replication
or immutable encrypted snapshots configured by the deployment owner.

## Secret rotation

1. Prepare replacement values in the deployment secret manager. Do not rotate
   local Compose credentials as if they were production secrets.
2. Coordinate dependent API, worker, Redis, PostgreSQL, object-store, AI-provider,
   and Fabric credentials. Keep new and old credentials valid only for the
   minimum overlap needed for rollout.
3. Restart affected services, check readiness and a synthetic operation, then
   revoke old credentials. Never print secret values while diagnosing failures.

## Dependency outage and degradation

- **AI provider or embeddings:** Keep AI disabled or return the existing safe
  unavailable state. Students can continue to use governed Rights Explorer and
  verified Help Directory content. Do not retry live generation repeatedly
  during quota exhaustion.
- **PostgreSQL or Redis:** Readiness fails; restore dependency connectivity
  before accepting authenticated or state-changing traffic.
- **Object storage:** Keep documents unavailable and surface a retryable service
  failure. Do not return a successful download without the owned object.
- **ClamAV:** Keep the file unprocessed and blocked/unavailable; retry after
  scanner recovery. Never bypass scanning.
- **Fabric:** Core workflows continue and provenance remains pending for worker
  retry. Do not put document contents or personal data into an anchor.

## Harmful response, resource deactivation, and deletion request

1. Preserve the response correlation ID and minimal audit metadata. Restrict
   access to any evidence containing student content.
2. Disable the AI provider via deployment configuration if unsafe behavior may
   affect additional users. Route urgent safety concerns to the established
   local emergency or specialist service; do not wait for AI review.
3. A content/resource owner should unpublish or deactivate inaccurate guidance
   through the authorized governance workflow, then verify it is absent from
   student search and retrieval.
4. For a valid document deletion request, use the authenticated owner-scoped
   delete operation and verify the document/report are no longer retrievable and
   object cleanup is complete. Explain backup retention under the applicable
   policy; do not promise immediate erasure from retained backups.
5. Record the incident, actions, owner, and follow-up without copying prompts,
   document content, credentials, or unnecessary personal details into logs.

## Production readiness limitations

This repository does not provision production TLS, a secrets manager, aggregate
metrics/tracing/alerting, object-store backup automation, a retention schedule,
or tested recovery objectives. The deployment owner must provide and verify
these controls before a production service is represented as release-ready.
