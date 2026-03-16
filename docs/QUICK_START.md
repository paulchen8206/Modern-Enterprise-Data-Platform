# ⚡ Modern Data Stack Quick Start - Advanced Deployments 🎯

This guide provides fast commands for common advanced deployment operations.

## Current Project Layout Notes

- CI and CD workflows are split into `.github/workflows/ci.yml` and `.github/workflows/cd.yml`.
- Branch and environment flow: push `dev` for CI/dev checks, PR to `qa`/`stg`/`prd` for env-specific CI checks and Helm CD deployment.
- Helm deploy source of truth: `helm/modern-data-stack` with `values.yaml` plus env overlays (`values-dev.yaml`, `values-qa.yaml`, `values-stg.yaml`, `values-prd.yaml`).
- Local Kubernetes assets are under `k8s/kind/` and operations scripts are under `ops/`.
- Docker Compose remains the default integration runtime via `infra/compose/docker-compose.yaml`.
- For full topology and component map, see `README.md` and `docs/ARCHITECTURE.md`.

## Quick Command Matrix

| Goal                       | Command                                                     |
| -------------------------- | ----------------------------------------------------------- |
| Start stack                | `make up`                                                   |
| Start hybrid local runtime | `make hybrid-up`                                            |
| Run Blue/Green automation  | `./ops/deploy-blue-green.sh airflow v1.0.0`                 |
| Run Canary automation      | `./ops/deploy-canary.sh airflow v1.0.0`                     |
| Watch rollout              | `kubectl argo rollouts get rollout airflow-rollout --watch` |
| Promote rollout            | `kubectl argo rollouts promote airflow-rollout`             |
| Abort rollout              | `kubectl argo rollouts abort airflow-rollout`               |

## Local Kubernetes (Kind) Quick Path

Use this when you want to run Docker-built containers in a local Kubernetes cluster.

```bash
make kind-deploy
make kind-status
make kind-smoke
```

Use this when you want Kind plus non-conflicting Docker Compose support services (`postgres-conduktor`, `conduktor`):

```bash
make hybrid-up
make hybrid-status
```

Default host endpoints via Kind port mappings:

- Workflow API: `http://localhost:8081`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- Kafka broker: `localhost:9092`

Cleanup:

```bash
make kind-down
make hybrid-down
```

Implementation details: `k8s/kind/README.md`

## Component Quick Procedures

### Orchestration (Airflow)

1. Start stack: `make up`
1. Open UI: `http://localhost:8080`
1. Enable and trigger `batch_ingestion_dag` once manually
1. Confirm task logs and downstream writes before enabling schedule

Best practices:

- Keep first production run manual and observable.
- Set explicit retries and task timeouts.

### Streaming (Kafka + Spark)

1. Start producer: `make run-kafka-producer`
1. Start consumer pipeline: `make run-streaming-job`
1. Validate throughput and lag in monitoring dashboards

Best practices:

- Use stable partitioning keys.
- Make write path idempotent for retries.

### Storage and Quality

1. Verify `raw-data` and `processed-data` buckets in MinIO
1. Verify transformed records in PostgreSQL
1. Review Great Expectations validation outputs

Best practices:

- Retain immutable raw records for replay.
- Treat critical expectation failures as release blockers.

### Governance and ML

1. Register lineage payloads after successful processing
1. Create MLflow runs for each experiment change

Best practices:

- Attach dataset/version metadata to lineage and experiments.
- Keep feature definitions and model metadata versioned.

## Prerequisites

### Install Required CLI Tools

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Install helm
curl https://raw.githubusercontent.com/helm/helm/main/ops/get-helm-3 | bash

# Install AWS CLI (for AWS deployments)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### Run Setup Script

```bash
cd ops
chmod +x *.sh
./setup.sh
```

### Provision Infrastructure (Optional)

```bash
cd iac
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform plan
terraform apply
```

Make-based alternative:

```bash
make terraform-init
make terraform-validate
```

---

## Blue/Green Deployment Quick Start

### Deploy Blue/Green Rollout

```bash
# Deploy new version to preview
./ops/deploy-blue-green.sh airflow v1.0.0

# Inside the script, you can:
# - View preview endpoint
# - Test preview environment
# - Compare Blue vs Green metrics
# - Promote to production
# - Rollback to Blue
```

### Manage Blue/Green Manually

```bash
# Apply Blue/Green rollout manifest
kubectl apply -f k8s/rollout-blue-green.yaml

# Watch rollout status
kubectl argo rollouts get rollout airflow-rollout --watch

# Access preview service for validation
kubectl get svc airflow-preview-service

# Promote preview to stable
kubectl argo rollouts promote airflow-rollout

# Undo if needed
kubectl argo rollouts undo airflow-rollout
```

---

## Canary Deployment Quick Start

### Deploy Canary Rollout

```bash
# List all rollouts
kubectl argo rollouts list

# Get rollout status
kubectl argo rollouts get rollout airflow-rollout

# Watch rollout progress
kubectl argo rollouts get rollout airflow-rollout --watch

# Promote rollout
kubectl argo rollouts promote airflow-rollout

# Abort rollout
kubectl argo rollouts abort airflow-rollout

# Rollback to previous version
kubectl argo rollouts undo airflow-rollout

# Set new image
kubectl argo rollouts set image airflow-rollout \
  airflow-webserver=myrepo/airflow-pipeline:v2.0.0
```

### Manage Canary Manually

```bash
# Apply rollout manifests
kubectl apply -f k8s/rollout-blue-green.yaml
kubectl apply -f k8s/rollout-canary.yaml

# Get rollouts
kubectl get rollouts

# Describe rollout
kubectl describe rollout airflow-rollout

# Get analysis runs
kubectl get analysisruns

# View analysis details
kubectl describe analysisrun <analysis-run-name>

# Get pods
kubectl get pods -l app=pipeline
```

---

## Monitoring Rollouts

### Check Rollout Status

```bash
# Argo Rollouts Dashboard
kubectl port-forward -n argo-rollouts svc/argo-rollouts-dashboard 3100:3100
# Open: http://localhost:3100

# Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-grafana 3000:80
# Open: http://localhost:3000 (admin/admin)

# Prometheus
kubectl port-forward -n monitoring svc/kube-prometheus-prometheus 9090:9090
# Open: http://localhost:9090
```

### Inspect Metrics and Dashboards

```bash
# Check success rate
kubectl exec -n monitoring prometheus-0 -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=service:http_requests:success_rate'

# Check error rate
kubectl exec -n monitoring prometheus-0 -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=service:http_requests:error_rate'

# Check latency
kubectl exec -n monitoring prometheus-0 -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=service:http_request_duration:p95'
```

---

## Rollback Procedures

### Roll Back Blue/Green Deployment

```bash
kubectl argo rollouts get rollout <rollout-name>
kubectl describe rollout <rollout-name>
kubectl get events --sort-by=.metadata.creationTimestamp
```

### Abort Canary Deployment

```bash
kubectl get analysisruns
kubectl describe analysisrun <analysis-run-name>
kubectl logs -n argo-rollouts deployment/argo-rollouts
```

### Undo to Previous Revision

```bash
kubectl get svc
kubectl describe svc <service-name>
kubectl get endpoints <service-name>
```

### Emergency Full Rollback

```bash
kubectl get pods -l app=pipeline
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl logs <pod-name> --previous  # Previous container logs
```

### Verify Post-Rollback Health

```bash
# Method 1: Using Argo Rollouts
kubectl argo rollouts abort <rollout-name>
kubectl argo rollouts undo <rollout-name>

# Method 2: Using kubectl
kubectl rollout undo rollout/<rollout-name>

# Method 3: Revert to specific revision
kubectl argo rollouts undo <rollout-name> --to-revision=2
```

---

## Advanced Testing and Analysis

### Run Automated Analysis

```bash
# Apply canary rollout with auto-promotion
kubectl apply -f k8s/rollout-canary.yaml

# Update image (deployment starts automatically)
kubectl argo rollouts set image airflow-canary-rollout \
  airflow-webserver=myrepo/airflow-pipeline:v2.0.0

# Watch progress (auto-promotes if analysis passes)
kubectl argo rollouts get rollout airflow-canary-rollout --watch
```

### Execute Load Testing

```bash
# Deploy blue/green with manual promotion
kubectl apply -f k8s/rollout-blue-green.yaml

# Update to new version
kubectl argo rollouts set image airflow-rollout \
  airflow-webserver=myrepo/airflow-pipeline:v2.0.0

# Test preview environment
kubectl port-forward svc/airflow-webserver-preview 8081:8080

# After testing, promote manually
kubectl argo rollouts promote airflow-rollout
```

### Execute Chaos Testing

```bash
# Apply header-based canary
kubectl apply -f k8s/rollout-canary.yaml

# Internal users get canary version
curl -H "X-Version: canary" http://your-service.com

# Regular users get stable version
curl http://your-service.com
```

### Capture Performance Benchmarks

```bash
# Immediate abort
kubectl argo rollouts abort airflow-rollout

# Rollback to previous stable version
kubectl argo rollouts undo airflow-rollout

# Verify rollback
kubectl argo rollouts get rollout airflow-rollout
```

---

## Configuration Reference

### Key Configuration Files

| File                          | Purpose                           |
| ----------------------------- | --------------------------------- |
| `k8s/rollout-blue-green.yaml` | Blue/Green rollout definitions    |
| `k8s/rollout-canary.yaml`     | Canary rollout definitions        |
| `k8s/analysis-templates.yaml` | Prometheus metrics analysis       |
| `k8s/services.yaml`           | Kubernetes services               |
| `k8s/ingress.yaml`            | Traffic routing rules             |
| `ops/deploy-blue-green.sh`    | Interactive blue/green deployment |
| `ops/deploy-canary.sh`        | Interactive canary deployment     |
| `ops/setup.sh`                | Infrastructure setup              |

### Tune Analysis Thresholds

Edit `k8s/analysis-templates.yaml`:

```yaml
# Example: Change success rate threshold
metrics:
  - name: success-rate
    successCondition: result >= 0.99 # Change from 0.95 to 0.99
    failureLimit: 2 # Reduce from 3 to 2
```

### Adjust Canary Weights

Edit `k8s/rollout-canary.yaml`:

```yaml
steps:
  - setWeight: 5 # Start with 5% instead of 10%
  - pause: { duration: 1m }
  - setWeight: 15 # Then 15%
  - pause: { duration: 2m }
  # ... customize as needed
```

---

## Troubleshooting

### Rollout Stuck Issues

```bash
# Check Argo Rollouts
kubectl get pods -n argo-rollouts

# Check Prometheus
kubectl get pods -n monitoring

# Check Ingress Controller
kubectl get pods -n ingress-nginx

# Verify all components
kubectl get all -n argo-rollouts
kubectl get all -n monitoring
```

### Analysis Failure Debugging

```bash
# Test Prometheus
kubectl exec -n monitoring prometheus-0 -- wget -qO- http://localhost:9090/-/healthy

# Test Grafana
kubectl exec -n monitoring deployment/kube-prometheus-grafana -- wget -qO- http://localhost:3000/api/health

# Test Argo Rollouts
kubectl exec -n argo-rollouts deployment/argo-rollouts -- wget -qO- http://localhost:8080/healthz
```

---

## Best Practices

### Traffic Strategy Guidance

For high-traffic services:

- Start with smaller weights (5%)
- Use shorter soak times (1-2 minutes)
- More granular steps (5%, 10%, 20%, 30%, 50%, 100%)

For critical services:

- Larger initial weight (20%)
- Longer soak times (5-10 minutes)
- Fewer steps (20%, 50%, 100%)

### Reliability and Availability Settings

```yaml
# Fast-moving services
interval: 15s
count: 4        # 1 minute total

# Stable services
interval: 60s
count: 10       # 10 minutes total
```

---

## Next Steps

1. Review [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed documentation
1. Customize analysis templates for your metrics
1. Configure Slack notifications
1. Set up custom dashboards in Grafana
1. Practice rollback procedures
1. Configure automated testing in CI/CD

---

## Resources

- **Argo Rollouts Docs**: <https://argoproj.github.io/argo-rollouts/>
- **Prometheus Docs**: <https://prometheus.io/docs/>
- **Grafana Docs**: <https://grafana.com/docs/>
- **Kubectl Cheatsheet**: <https://kubernetes.io/docs/reference/kubectl/cheatsheet/>

---

**Last Updated**: 2026-03-11
