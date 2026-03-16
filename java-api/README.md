# Java Workflow API

Spring Boot implementation of the orchestration API.

## Implementation Context

- Compose integration profile uses hostnames and services from `infra/compose/docker-compose.yaml`.
- Local Kubernetes profile validation runs through `k8s/kind/stack.yaml` and `ops/deploy-kind.sh`.
- Repository automation is split into `.github/workflows/ci.yml` and `.github/workflows/cd.yml`.
- Branch and environment flow is standardized: push `dev` for CI/dev checks, PR to `qa`/`stg`/`prd` for env-specific CI checks and Helm CD deployment.

## Run

```bash
cd java-api
mvn spring-boot:run -Dspring-boot.run.profiles=local
```

Run with Compose network hostnames (when Java API runs in a container/network with other services):

```bash
cd java-api
mvn spring-boot:run -Dspring-boot.run.profiles=compose
```

## Build

```bash
cd java-api
mvn clean package
```

## Endpoints

- `POST /api/batch/ingest`
- `POST /api/stream/produce`
- `POST /api/stream/run`
- `POST /api/governance/lineage`
- `POST /api/ml/run`
- `POST /api/ci/trigger`
- `GET /api/monitor/health`

## Design Pattern Guide

See `DESIGN_PATTERNS.md` for the high-level architecture pattern catalog and extension guidelines.

- Layered architecture: controllers map transport concerns, services hold orchestration and integration logic.
- Dependency Injection: Spring-managed constructor injection is used across controllers/services for testability.
- Template Method (outbound HTTP): `HttpServiceClient` centralizes HTTP execution, status handling, and reachability checks while concrete services build endpoint-specific requests.
- Exception hierarchy: `IntegrationException` + specialized types (`UpstreamServiceException`, `IntegrationConnectivityException`) standardize dependency failure semantics.
- Problem response codes: dependency failures include `code` with values `INTEGRATION_UPSTREAM_ERROR` or `INTEGRATION_CONNECTIVITY_ERROR` for client-side branching.
- Facade-like orchestration at service layer: each service (`AirflowService`, `CiService`, `MlflowService`, `AtlasService`) wraps one external platform behind a narrow API.
- Strategy-ready health checks: `MonitoringService` composes dependency probes from each service and can be extended with additional probe strategies.

## Component Procedures

### Batch component

1. Call `POST /api/batch/ingest` with `sourceTable` and optional `limit`.
1. Verify response includes `objectKey` and optional `runId`.
1. Confirm raw object in MinIO and transformed records downstream.

Best practices:

- Keep `sourceTable` allow-listed in production.
- Use bounded `limit` values for test and smoke runs.

### Streaming component

1. Call `POST /api/stream/produce` with `partition` and `payload`.
1. Trigger orchestration via `POST /api/stream/run`.
1. Validate consumer lag and sink write success.

Best practices:

- Keep payload schema versioned.
- Use deterministic partition strategy for ordering-sensitive streams.

### Governance and ML components

1. Register lineage via `POST /api/governance/lineage` after data publish.
1. Start experiment run with `POST /api/ml/run`.
1. Trigger CI workflow with `POST /api/ci/trigger` for release automation.

Best practices:

- Include dataset/version metadata in lineage payloads.
- Keep ML run parameters and artifacts reproducible.

### Monitoring component

1. Poll `GET /api/monitor/health` as readiness signal.
1. Wire health status into dashboards and alerting.

Best practices:

- Alert on sustained degraded state, not transient spikes.
- Track dependency-level and overall status together.

## Configuration

See `src/main/resources/application.yml` for defaults matching the local stack:

- MySQL/Postgres connection strings
- MinIO endpoint and buckets
- Kafka broker/topic
- Airflow base URL and credentials
- Great Expectations CLI path
- Atlas/MLflow/GitHub endpoints and credentials
