# Alibaba Cloud deployment proof

Status: **awaiting account credentials and first production deployment**

This document is intentionally not pre-filled with unverifiable claims. Replace
each `PENDING` value during the deployment run and commit the redacted evidence.

| Evidence | Value |
|---|---|
| Production URL | PENDING |
| Alibaba Cloud region | PENDING |
| ECS instance | PENDING — record only a redacted ID |
| OSS bucket | PENDING — private bucket |
| Deployment commit | PENDING |
| `GET /healthz` | PENDING |
| `GET /readyz` | PENDING |
| Persistence after restart | PENDING |
| Replay object key and ETag | PENDING |

## Architecture

Five Docker Compose services run on one ECS instance: Caddy, Next.js, FastAPI,
the scheduler worker, and PostgreSQL 16/pgvector. FastAPI calls Qwen Cloud and
uploads replay/benchmark bundles to a private OSS bucket.

## Source evidence

- ECS deployment: [`deploy_ecs.sh`](deploy_ecs.sh)
- Production topology: [`docker-compose.prod.yml`](../docker-compose.prod.yml)
- OSS SDK use: [`alibaba_oss.py`](../backend/app/integrations/alibaba_oss.py)
- Health endpoints: [`main.py`](../backend/app/main.py)
- Deployment diagram: [`deployment.mmd`](../docs/architecture/deployment.mmd)

## OSS behavior

`POST /v1/replays/{run_id}/export` serializes the immutable timeline and sends it
to `ALIBABA_CLOUD_OSS_PREFIX/{run_id}.json`. The response records the bucket,
region, object key, ETag, request ID, and timestamp without exposing credentials.
Grant only `oss:PutObject`, `oss:GetObject`, and `oss:ListObjects` for the scoped
bucket prefix, preferably through an ECS instance RAM role.

## Evidence to capture

1. Redacted ECS Overview showing region, running status, and public IP.
2. Redacted OSS bucket Overview showing the bucket and region.
3. Browser screenshot of the System screen at the production URL.
4. Terminal output from `/healthz` and `/readyz`.
5. OSS object details for one replay bundle.
6. Container restart followed by the same active intention ID/version.

Store screenshots under `deployment/proof/`. Do not include account IDs, private
IPs, AccessKey IDs, security-group details, or secrets.

