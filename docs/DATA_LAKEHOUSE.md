# 🧊 Apache Iceberg Tables Guide

This project supports writing Spark batch output to Apache Iceberg tables.

## Current Architecture Context

- Spark implementation lives in `pipelines/spark/` and image definitions are in `infra/dockerfiles/`.
- Iceberg batch writes are validated first in Compose-based local runtime (`make up`) and can be smoke-tested in Kind after `make kind-deploy`.
- CI/CD orchestration for changes is split between `.github/workflows/ci.yml` and `.github/workflows/cd.yml`.
- Branch and environment flow follows `dev` push (CI/dev checks) and PR promotion to `qa`/`stg`/`prd` (env CI checks plus Helm CD deployment).

## What Was Added

- Iceberg runtime JAR in Spark image:
  - `infra/dockerfiles/spark.Dockerfile`
- Optional Iceberg write path in batch job:
  - `pipelines/spark/spark_batch_job.py`
- Make target for Iceberg demo run:
  - `make run-iceberg-demo`

## Default Iceberg Settings

The batch job reads these environment variables:

- `ENABLE_ICEBERG` (default: `false`)
- `ICEBERG_CATALOG` (default: `local`)
- `ICEBERG_NAMESPACE` (default: `analytics`)
- `ICEBERG_TABLE` (default: `orders`)
- `ICEBERG_WAREHOUSE` (default: `file:///tmp/iceberg_warehouse`)

## Run Iceberg Demo

1. Rebuild/start the stack so Spark has the Iceberg JAR:

```bash
make up
```

1. Run batch job with Iceberg enabled:

```bash
make run-iceberg-demo
```

The job still writes CSV outputs as before, and additionally writes to Iceberg table:

- `local.analytics.orders`

## Production Procedure

1. Validate local run with `make run-iceberg-demo` and inspect Spark logs.
1. Choose warehouse path strategy (`local` file path or object storage path).
1. Define namespace/table naming convention by domain/environment.
1. Validate read queries from downstream engines before rollout.
1. Promote configuration to higher environments with the same table contract.

## Best Practices

- Use partitioning aligned to dominant query filters.
- Keep schema evolution backward-compatible; avoid destructive column changes.
- Use snapshot retention and compaction maintenance to control storage costs.
- Separate dev/test/prod namespaces to avoid accidental cross-environment reads.
- Capture table metadata checks in CI to prevent accidental contract breakage.

## Validation Checklist

- Confirm demo command exits successfully:

  ```bash
  make run-iceberg-demo
  ```

- Confirm logs include:
  - `Iceberg write complete: local.analytics.orders`
  - `Batch ETL process completed successfully`

- Confirm Spark image includes required jars:
  - Iceberg runtime jar
  - Hadoop AWS + AWS SDK bundle jars

## Run Without Iceberg

To use legacy behavior (CSV outputs only):

```bash
make run-batch-job
```

## Notes

- Iceberg is implemented with Spark Catalog type `hadoop` and a local warehouse by default.
- You can switch to object storage-backed warehouse paths by setting `ICEBERG_WAREHOUSE` and related Spark/Hadoop settings for your environment.

## Troubleshooting

- `spark-submit` not found:
  - Use explicit binary path `/opt/spark/bin/spark-submit` in container commands.
- `S3AFileSystem not found`:
  - Ensure Spark image includes `hadoop-aws` and `aws-java-sdk-bundle` jars.
- MinIO bucket not found:
  - Ensure `raw-data` and `processed-data` buckets exist before running batch jobs.
