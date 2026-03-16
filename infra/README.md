# 🏗️ Infrastructure Containers Layout 🟠

This folder centralizes container definitions for the Modern Data Stack.

## Directory Layout

- `compose/`
  - `docker-compose.yaml`: canonical local/development stack used by default
  - `docker-compose.ci.yaml`: CI-oriented/legacy lightweight compose definition
- `dockerfiles/`
  - `airflow.Dockerfile`: Airflow image definition
  - `spark.Dockerfile`: Spark image definition
  - `workflow-api.Dockerfile`: Java workflow API image definition

## Current Runtime Topology

- Main local stack is defined in `compose/docker-compose.yaml`.
- Core services in the local stack:
  - `zookeeper` (`2181`)
  - `kafka` (`9092`)
  - `mysql` (`3306`)
  - `postgres` (`5432`) for project data
  - `postgres-conduktor` (`5433` on host, container `5432`) for Conduktor metadata
  - `minio` (`9000` API, `9001` console)
  - `airflow-webserver` (`8080`)
  - `airflow-scheduler`
  - `spark`
  - `workflow-api` (`${WORKFLOW_API_PORT:-8081}`)
  - `conduktor` (`8085`)
- Named volumes in the local stack:
  - `minio_data`
  - `postgres_data`
  - `postgres_conduktor_data`

## Ownership Boundaries

- Use this document for compose file ownership, image build paths, and container inventory.
- Use `RUNBOOK.md` for startup, shutdown, health checks, and local troubleshooting procedures.
- Use `docs/DEPLOYMENT.md` for rollout strategy, promotion, and rollback flows.

## Build and Path Conventions

- Build contexts in `compose/docker-compose.yaml`:
  - `airflow-webserver` and `airflow-scheduler`: context `./pipelines/airflow`, Dockerfile `../../infra/dockerfiles/airflow.Dockerfile`
  - `spark`: context `./pipelines/spark`, Dockerfile `../../infra/dockerfiles/spark.Dockerfile`
  - `workflow-api`: context `.`, Dockerfile `./infra/dockerfiles/workflow-api.Dockerfile`
- Dockerfiles are intentionally separated from service code to keep image definitions centralized.
- Local initialization data for MySQL is mounted from `./ops/init_db.sql`.
- For local troubleshooting, run `make ps` and `make logs` before restarting services.

## CI Compose Notes

- `compose/docker-compose.ci.yaml` defines a smaller CI-oriented stack (`airflow`, `kafka`, `spark`, `mongodb`, `hadoop`, `influxdb`).
- The CI compose file currently references local build contexts (`./airflow`, `./kafka`, `./spark`, `./hadoop`) and should be treated as separate from the default local runtime topology.

For compose validation and day-to-day verification commands, follow `RUNBOOK.md`.
