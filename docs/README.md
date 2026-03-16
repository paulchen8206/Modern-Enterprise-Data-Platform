# Documentation Index

This folder contains the shared, cross-cutting documentation for the Modern Enterprise Data Platform.

## Files in This Folder

| File | Scope | Contents |
| --- | --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Cross-cutting | Platform topology, layered system design, component architecture, security, scalability, observability, and disaster recovery |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Cross-cutting | Rollout strategies (Blue/Green, Canary), analysis gates, promotion, rollback mechanics, and deployment troubleshooting |
| [QUICK_START.md](QUICK_START.md) | Entry point | Minimum startup commands, daily-path shortcuts, and routing to the right source-of-truth doc |
| [LOCAL_RUNTIME.md](LOCAL_RUNTIME.md) | Operator | Local runtime setup, Docker Compose, Kind, hybrid mode, health checks, and operational troubleshooting |
| [AWS_WELL_ARCHITECTED.md](AWS_WELL_ARCHITECTED.md) | Cross-cutting | Well-Architected Framework alignment, cloud design review, and compliance notes |
| [DATA_LAKEHOUSE.md](DATA_LAKEHOUSE.md) | Cross-cutting | Apache Iceberg integration, data lakehouse patterns, and storage format guidance |

## Documentation Ownership Rules

| Type | Location | Rule |
| --- | --- | --- |
| Platform-wide and cross-cutting | `docs/` | If the document describes the whole platform or spans multiple modules, put it here |
| Module-specific | Beside the module | Implementation and design docs should live next to the code they describe |
| Operator runtime | `docs/LOCAL_RUNTIME.md` | Compose, Kind, hybrid setup, health checks, operational procedures |
| Entry point | `README.md` (root) | Repo overview, high-level navigation, and source-of-truth links only |

## Module-Level Docs (Outside This Folder)

These docs stay next to their implementation:

- `java-api/README.md` — Java API build, run, and endpoint overview
- `java-api/DESIGN_PATTERNS.md` — Java API structural patterns and class-level design
- `pipelines/DESIGN_PATTERNS.md` — Pipeline patterns, smoke-test harness architecture
- `infra/README.md` — Container inventory, compose ownership, and image build conventions
- `k8s/kind/README.md` — Kind cluster setup and local Kubernetes implementation details
