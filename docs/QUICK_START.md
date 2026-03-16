# Quick Start

This guide is the fast entry point for the repository. It keeps only the minimum commands needed to get started and links to the documents that own detailed runtime, rollout, and troubleshooting content.

## Use This Guide For

- Starting the default local stack quickly.
- Running local Kubernetes validation with Kind.
- Triggering Blue/Green or Canary rollout workflows.
- Finding the right source-of-truth document for deeper procedures.

## Source-of-Truth Docs

- Platform architecture: `docs/ARCHITECTURE.md`
- Local runtime procedures and diagrams: `docs/LOCAL_RUNTIME.md`
- Rollout strategy, analysis, rollback, and troubleshooting: `docs/DEPLOYMENT.md`
- Kind-specific implementation details: `k8s/kind/README.md`
- Container and compose ownership: `infra/README.md`

## Quick Command Matrix

| Goal | Command |
| --- | --- |
| Start default local stack | `make up` |
| Check local stack status | `make ps` |
| Run Java API on host | `make run-java-api-local-safe` |
| Deploy local Kind stack | `make kind-deploy` |
| Check Kind status | `make kind-status` |
| Run Kind smoke tests | `make kind-smoke` |
| Start hybrid runtime | `make hybrid-up` |
| Run Blue/Green script | `./ops/deploy-blue-green.sh airflow v1.0.0` |
| Run Canary script | `./ops/deploy-canary.sh airflow v1.0.0` |
| Watch rollout | `kubectl argo rollouts get rollout airflow-rollout --watch` |
| Promote rollout | `kubectl argo rollouts promote airflow-rollout` |
| Abort rollout | `kubectl argo rollouts abort airflow-rollout` |

## Daily Paths

### Compose-Based Local Development

Use this for day-to-day integration work:

```bash
make up
make ps
make run-java-api-local-safe
```

Then verify readiness:

```bash
curl -sS http://localhost:8081/actuator/health
curl -sS http://localhost:8081/api/monitor/health
```

For full runtime procedures, service-specific checks, and troubleshooting, use `docs/LOCAL_RUNTIME.md`.

### Local Kubernetes Validation With Kind

Use this for manifest and container-runtime validation:

```bash
make kind-deploy
make kind-status
make kind-smoke
```

Use hybrid mode when you want Kind plus Compose-hosted support services:

```bash
make hybrid-up
make hybrid-status
```

For topology, endpoints, and Kind implementation detail, use `k8s/kind/README.md` and `docs/LOCAL_RUNTIME.md`.

### Progressive Delivery Shortcuts

Use the scripts for the fastest rollout path:

```bash
./ops/deploy-blue-green.sh airflow v1.0.0
./ops/deploy-canary.sh airflow v1.0.0
```

Use these commands for active rollout control:

```bash
kubectl argo rollouts get rollout airflow-rollout --watch
kubectl argo rollouts promote airflow-rollout
kubectl argo rollouts abort airflow-rollout
kubectl argo rollouts undo airflow-rollout
```

For manual rollout steps, analysis templates, dashboard access, rollback procedures, and rollout debugging, use `docs/DEPLOYMENT.md`.

## Key Files

| File | Purpose |
| --- | --- |
| `k8s/rollout-blue-green.yaml` | Blue/Green rollout definition |
| `k8s/rollout-canary.yaml` | Canary rollout definition |
| `k8s/analysis-templates.yaml` | Analysis thresholds and gates |
| `ops/deploy-blue-green.sh` | Scripted Blue/Green workflow |
| `ops/deploy-canary.sh` | Scripted Canary workflow |
| `ops/setup.sh` | Cluster and monitoring setup |

## Next Reading

1. Read `docs/LOCAL_RUNTIME.md` if you need local runtime setup, teardown, or service checks.
1. Read `docs/DEPLOYMENT.md` if you need rollout mechanics, rollback, dashboards, or troubleshooting.
1. Read `docs/ARCHITECTURE.md` if you need platform topology or environment context.
