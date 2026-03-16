# 🚢 Advanced Deployment Strategies Guide 🌟

This guide covers advanced deployment strategies for the Modern Data Stack, including Blue/Green, Canary, and progressive delivery patterns.

## Current Implementation Baseline

- CI/CD automation is represented by `.github/workflows/ci.yml` and `.github/workflows/cd.yml`.
- Local Kubernetes validation is implemented under `k8s/kind/` with automation scripts in `ops/deploy-kind.sh` and `ops/kind-smoke.sh`.
- Compose-based local runtime remains available under `infra/compose/docker-compose.yaml` for service-level integration tests before rollout.

## Table of Contents

1. [Overview](#overview)
1. [Architecture](#architecture)
1. [Prerequisites](#prerequisites)
1. [Installation](#installation)
1. [Deployment Strategies](#deployment-strategies)
1. [Monitoring & Observability](#monitoring--observability)
1. [Troubleshooting](#troubleshooting)
1. [Best Practices](#best-practices)

---

## Overview

| Scenario                       | Recommended Strategy   | Why                                           |
| ------------------------------ | ---------------------- | --------------------------------------------- |
| Low-risk routine release       | Blue/Green             | Fast cutover and immediate rollback           |
| High-risk or uncertain release | Canary                 | Progressive traffic shift with analysis gates |
| Mission-critical API           | Canary + auto rollback | Reduces blast radius for regressions          |
| Major platform migration       | Blue/Green + soak test | Parallel validation before full switch        |

### What Is Included

This project now includes enterprise-grade deployment capabilities:

- **Blue/Green Deployments**: Zero-downtime deployments with instant rollback capability
- **Canary Deployments**: Progressive traffic shifting with automated analysis
- **Automated Analysis**: Prometheus-based metrics analysis during deployments
- **Traffic Management**: Advanced routing with AWS ALB and Nginx Ingress
- **Monitoring**: Real-time deployment metrics and dashboards
- **GitOps Integration**: Argo CD with Argo Rollouts for continuous delivery

### Key Benefits

- **Zero Downtime**: All deployment strategies ensure no service interruption
- **Risk Mitigation**: Progressive rollouts and automated rollbacks reduce deployment risk
- **Automated Quality Gates**: Analysis templates validate deployments before promotion
- **Visibility**: Comprehensive monitoring and alerting for deployment health
- **Speed**: Faster rollbacks and controlled traffic shifting

---

## Architecture

### System Architecture Diagram

```mermaid
flowchart TB
    subgraph TM["Traffic Management"]
        ALB[AWS ALB]
        NI[Nginx Ingress]
        SM[Service Mesh]
    end

    subgraph DE["Deployment Engine"]
        subgraph AR["Argo Rollouts"]
            BG[Blue/Green Strategy]
            CS[Canary Strategy]
        end
    end

    subgraph AM["Analysis & Metrics"]
        PROM[Prometheus]
        GRAF[Grafana]
        ALERT[AlertManager]
    end

    TM --> DE
    DE --> AM
```

### Local Validation Topology

Deployment strategy documentation no longer duplicates local runtime topology.

- Use `docs/LOCAL_RUNTIME.md` for Compose, Kind, hybrid, and Java API runtime diagrams.
- Use `infra/README.md` for compose file ownership, build contexts, and container layout.
- Use this document for rollout strategies, analysis flow, promotion, and rollback mechanics.

### Deployment Flow Diagrams

#### Blue/Green Flow

```mermaid
flowchart LR
    A[1. Deploy Green<br/>Preview] --> B[2. Run Tests &<br/>Analysis]
    B --> C[3. Manual/Auto<br/>Verification]
    C --> D[4. Switch Traffic<br/>Blue → Green]
    D --> E[5. Keep Blue for<br/>Instant Rollback]
    E --> F[6. Decommission<br/>Blue]
```

#### Canary Flow

```mermaid
flowchart TB
    A[1. Deploy Canary] --> B[2. Route 10%<br/>Traffic to Canary]
    B --> C{3. Analysis Pass?}
    C -->|Yes| D[4. Increase to 25%]
    C -->|No| Z[Auto-Rollback]
    D --> E{Analysis Pass?}
    E -->|Yes| F[5. Increase to 50%]
    E -->|No| Z
    F --> G{Analysis Pass?}
    G -->|Yes| H[6. Increase to 75%]
    G -->|No| Z
    H --> I{Analysis Pass?}
    I -->|Yes| J[7. Promote to 100%]
    I -->|No| Z
```

---

## Prerequisites

### Required Tools

- **kubectl** (v1.24+)
- **helm** (v3.10+)
- **AWS CLI** (v2.0+) - for AWS deployments
- **eksctl** (optional) - for EKS management
- **jq** (optional) - for JSON parsing

### Infrastructure Requirements

- **Kubernetes**: v1.24+
- **Minimum Nodes**: 3
- **Node Size**: t3.medium or larger
- **Storage**: Support for dynamic PVC provisioning

### AWS Components (Optional)

- EKS Cluster
- VPC with public/private subnets
- IAM roles for service accounts
- ACM certificate (for HTTPS)

---

## Installation

### Quick Installation Commands

```bash
# 1. Navigate to ops directory
cd ops

# 2. Make scripts executable
chmod +x *.sh

# 3. Run setup script
./setup.sh

# 4. Verify installation
kubectl get pods -n argo-rollouts
kubectl get pods -n monitoring
```

### Detailed Installation Steps

#### 1. Install Argo Rollouts

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f \
  https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Install kubectl plugin
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts-linux-amd64
sudo mv kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts
```

#### 2. Install Prometheus & Grafana

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

#### 3. Install Nginx Ingress (Optional)

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace
```

#### 4. Apply Kubernetes Manifests

```bash
cd k8s

# Apply services
kubectl apply -f services.yaml

# Apply analysis templates
kubectl apply -f analysis-templates.yaml

# Apply ServiceMonitors
kubectl apply -f servicemonitors.yaml

# Apply Ingress
kubectl apply -f ingress.yaml
```

### Helm Usage (Environment-Based Deployments)

Use the in-repo chart at `helm/modern-data-stack` with layered values:

- Base values: `helm/modern-data-stack/values.yaml`
- Environment values: `values-dev.yaml`, `values-qa.yaml`, `values-stg.yaml`, `values-prd.yaml`

#### Validate Chart

```bash
helm lint helm/modern-data-stack
```

#### Render Per Environment (Dry Run)

```bash
helm template modern-data-stack-dev helm/modern-data-stack \
  --namespace data-stack-dev \
  -f helm/modern-data-stack/values.yaml \
  -f helm/modern-data-stack/values-dev.yaml

helm template modern-data-stack-qa helm/modern-data-stack \
  --namespace data-stack-qa \
  -f helm/modern-data-stack/values.yaml \
  -f helm/modern-data-stack/values-qa.yaml

helm template modern-data-stack-stg helm/modern-data-stack \
  --namespace data-stack-stg \
  -f helm/modern-data-stack/values.yaml \
  -f helm/modern-data-stack/values-stg.yaml

helm template modern-data-stack-prd helm/modern-data-stack \
  --namespace data-stack-prd \
  -f helm/modern-data-stack/values.yaml \
  -f helm/modern-data-stack/values-prd.yaml
```

#### Deploy / Upgrade Per Environment

```bash
helm upgrade --install modern-data-stack-qa helm/modern-data-stack \
  --namespace data-stack-qa \
  --create-namespace \
  -f helm/modern-data-stack/values.yaml \
  -f helm/modern-data-stack/values-qa.yaml \
  --wait --timeout 10m

helm upgrade --install modern-data-stack-stg helm/modern-data-stack \
  --namespace data-stack-stg \
  --create-namespace \
  -f helm/modern-data-stack/values.yaml \
  -f helm/modern-data-stack/values-stg.yaml \
  --wait --timeout 10m

helm upgrade --install modern-data-stack-prd helm/modern-data-stack \
  --namespace data-stack-prd \
  --create-namespace \
  -f helm/modern-data-stack/values.yaml \
  -f helm/modern-data-stack/values-prd.yaml \
  --wait --timeout 10m
```

#### CI/CD Branch-to-Environment Mapping

- Push to `dev` branch: CI validation and `dev` Helm render checks.
- PR to `qa` branch: CI `qa` render checks and CD deploy to `qa`.
- PR to `stg` branch: CI `stg` render checks and CD deploy to `stg`.
- PR to `prd` branch: CI `prd` render checks and CD deploy to `prd`.

---

## Deployment Strategies

### Blue/Green Rollout Steps

#### Scripted Blue/Green Rollout

```bash
cd ops
./deploy-blue-green.sh airflow v1.0.0
```

#### Manual Blue/Green Rollout

```bash
# Apply rollout manifest
kubectl apply -f k8s/rollout-blue-green.yaml

# Update image
kubectl argo rollouts set image airflow-rollout \
  airflow-webserver=myrepo/airflow-pipeline:v1.0.0

# Check status
kubectl argo rollouts get rollout airflow-rollout --watch

# Promote to production
kubectl argo rollouts promote airflow-rollout

# Rollback if needed
kubectl argo rollouts abort airflow-rollout
kubectl argo rollouts undo airflow-rollout
```

#### Access Preview Environment

```bash
# Port-forward to preview service
kubectl port-forward svc/airflow-webserver-preview 8081:8080

# Test preview
curl http://localhost:8081/health
```

### Canary Rollout Steps

#### Scripted Canary Rollout

```bash
cd ops
./deploy-canary.sh airflow v1.0.0
```

#### Manual Canary Rollout

```bash
# Apply rollout manifest
kubectl apply -f k8s/rollout-canary.yaml

# Update image (triggers canary)
kubectl argo rollouts set image airflow-canary-rollout \
  airflow-webserver=myrepo/airflow-pipeline:v1.0.0

# Monitor progress
kubectl argo rollouts get rollout airflow-canary-rollout --watch

# Manual promotion (if not using auto-promotion)
kubectl argo rollouts promote airflow-canary-rollout

# Abort and rollback
kubectl argo rollouts abort airflow-canary-rollout
```

#### Canary Traffic Weights

The default canary strategy uses progressive traffic shifting:

- **Step 1**: 10% for 2 minutes
- **Step 2**: 25% for 3 minutes
- **Step 3**: 50% for 5 minutes
- **Step 4**: 75% for 3 minutes
- **Step 5**: 100% (full promotion)

Each step includes automated analysis. Deployment auto-aborts on analysis failure.

### Rollout Management Commands

```bash
# Apply header-based canary
kubectl apply -f k8s/rollout-canary.yaml

# Access canary version with header
curl -H "X-Version: canary" http://your-domain.com

# Regular traffic goes to stable version
curl http://your-domain.com
```

---

## Monitoring & Observability

### Dashboards and UIs

#### Argo Rollouts Dashboard

```bash
kubectl port-forward -n argo-rollouts svc/argo-rollouts-dashboard 3100:3100
# Open: http://localhost:3100
```

#### Grafana

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-grafana 3000:80
# Open: http://localhost:3000
# Username: admin
# Password: admin
```

#### Prometheus

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-prometheus 9090:9090
# Open: http://localhost:9090
```

### Prometheus Alerts and Rules

```bash
# The dashboard is located at: monitoring/grafana-deployment-dashboards.json

# Import via UI:
# 1. Login to Grafana
# 2. Click "+" → Import
# 3. Upload the JSON file
# 4. Select Prometheus data source
# 5. Click Import
```

### Key Metrics to Track

#### Success Rate

```promql
sum(rate(http_requests_total{status=~"2.."}[5m])) /
sum(rate(http_requests_total[5m]))
```

#### Error Rate

```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m]))
```

#### P95 Latency

```promql
histogram_quantile(0.95,
  sum(rate(http_request_duration_milliseconds_bucket[5m])) by (le)
)
```

### Recommended Alert Policies

Alerts are automatically configured for:

- High error rate (>5%)
- High latency (P95 >1000ms)
- Rollout degraded
- Analysis run failed
- Airflow task failures
- Kafka consumer lag
- Spark job failures

Configure Slack notifications in `k8s/argo-rollouts-install.yaml`.

---

## Troubleshooting

### Rollout Issues

```bash
# Check rollout status
kubectl argo rollouts get rollout <rollout-name>

# Check analysis runs
kubectl get analysisruns

# View analysis details
kubectl describe analysisrun <analysis-run-name>

# Check pod status
kubectl get pods -l app=pipeline

# View pod logs
kubectl logs <pod-name>
```

### Monitoring Issues

```bash
# Check Prometheus connectivity
kubectl exec -it <rollout-pod> -- curl http://prometheus:9090/-/healthy

# Verify metrics exist
kubectl port-forward svc/prometheus 9090:9090
# Open Prometheus UI and run query

# Check ServiceMonitors
kubectl get servicemonitors

# View analysis template
kubectl get analysistemplate <template-name> -o yaml
```

### Ingress and Networking Issues

```bash
# Check services
kubectl get svc

# Check ingress
kubectl get ingress
kubectl describe ingress <ingress-name>

# Verify canary service selector
kubectl get svc <canary-service> -o yaml

# Check pod labels
kubectl get pods --show-labels
```

### Rollback Issues

```bash
# Abort current rollout
kubectl argo rollouts abort <rollout-name>

# Undo to previous version
kubectl argo rollouts undo <rollout-name>

# Undo to specific revision
kubectl argo rollouts undo <rollout-name> --to-revision=2
```

---

## Best Practices

### Strategy Selection Guide

| Scenario                    | Recommended Strategy       |
| --------------------------- | -------------------------- |
| Critical production service | Blue/Green                 |
| High-traffic service        | Canary                     |
| Testing new features        | Canary with header routing |
| Database migrations         | Blue/Green                 |
| Quick iterations            | Canary                     |
| Stateful applications       | Blue/Green                 |

### Analysis Configuration Tips

1. **Set appropriate thresholds**: Don't make them too strict or too loose
1. **Use multiple metrics**: Success rate + latency + errors
1. **Set failure limits**: Allow 2-3 failures before aborting
1. **Adjust intervals**: 30s for high-traffic, 60s for low-traffic

### Canary Rollout Tips

1. **Start with small percentages**: 10% for initial canary
1. **Increase gradually**: 10% → 25% → 50% → 75% → 100%
1. **Allow soak time**: Minimum 2-5 minutes per step
1. **Monitor continuously**: Watch metrics during traffic shifts

### Rollback Best Practices

1. **Set auto-rollback**: Configure analysis to auto-abort on failures
1. **Keep blue/green environments**: Maintain for quick rollback
1. **Test rollback procedures**: Practice rollbacks regularly
1. **Document rollback playbooks**: Clear steps for emergencies

### Security and Access Control

1. **Use RBAC**: Limit who can promote deployments
1. **Require approvals**: Manual gates for production
1. **Audit trails**: Track all deployment actions
1. **Network policies**: Isolate preview environments

---

## Advanced Configurations

### A/B and Experimentation Support

Test multiple versions simultaneously:

```yaml
experiments:
  - name: version-comparison
    templates:
      - name: v1
        specRef: stable
        replicas: 2
      - name: v2
        specRef: canary
        replicas: 2
    duration: 10m
```

### External Integrations

Beyond Prometheus, support for:

- Datadog
- New Relic
- CloudWatch
- Custom webhooks

### Notification Channels

Configure in `k8s/argo-rollouts-install.yaml`:

- Slack
- Email
- PagerDuty
- Webhooks

---

## Integration with Existing Infrastructure

### Terraform Integration

```bash
cd iac

# Initialize
terraform init

# Plan
terraform plan

# Apply
terraform apply

# Outputs
terraform output
```

### Infrastructure Mapping

- **EKS Cluster**: `eks.tf`
- **Load Balancer Controller**: `load-balancer-controller.tf`
- **Argo Rollouts**: `argo-rollouts.tf`
- **Networking**: `security.tf`

---

## Additional Resources

### Reference Documentation

- [Argo Rollouts](https://argoproj.github.io/argo-rollouts/)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Grafana](https://grafana.com/docs/)

### Important Project Files

| File                              | Purpose                         |
| --------------------------------- | ------------------------------- |
| `k8s/rollout-blue-green.yaml`     | Blue/Green deployment manifests |
| `k8s/rollout-canary.yaml`         | Canary deployment manifests     |
| `k8s/analysis-templates.yaml`     | Prometheus analysis templates   |
| `k8s/services.yaml`               | Kubernetes services             |
| `k8s/ingress.yaml`                | Ingress configurations          |
| `k8s/servicemonitors.yaml`        | Prometheus ServiceMonitors      |
| `ops/deploy-blue-green.sh`        | Blue/Green deployment script    |
| `ops/deploy-canary.sh`            | Canary deployment script        |
| `ops/setup.sh`                    | Infrastructure setup            |
| `iac/load-balancer-controller.tf` | AWS LB Controller               |
| `iac/argo-rollouts.tf`            | Argo Rollouts infrastructure    |

---

## Conclusion

For issues or questions:

1. Check the troubleshooting section
1. Review Argo Rollouts documentation
1. Check pod logs and events
1. Verify Prometheus metrics

---

**Last Updated**: 2026-03-11
**Version**: 1.0.0
