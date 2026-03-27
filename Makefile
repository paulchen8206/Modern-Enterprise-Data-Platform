SHELL := /bin/bash

PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
COMPOSE_MAIN ?= docker-compose --project-directory . -f infra/compose/docker-compose.yaml
COMPOSE_CI ?= docker-compose --project-directory . -f infra/compose/docker-compose.ci.yaml
TERRAFORM ?= terraform
PRETTIER ?= prettier
WIKI_PORT ?= 8000
WEB_PORT ?= 8080
KIND ?= kind
KUBECTL ?= kubectl
HELM ?= helm
KIND_CLUSTER ?= modern-data-stack
KIND_NAMESPACE ?= data-stack-local
HELM_CHART ?= helm/modern-data-stack
HELM_ENV ?= qa
HELM_NAMESPACE_PREFIX ?= data-stack
HELM_RELEASE_PREFIX ?= modern-data-stack
HELM_NAMESPACE ?= $(HELM_NAMESPACE_PREFIX)-$(HELM_ENV)
HELM_RELEASE ?= $(HELM_RELEASE_PREFIX)-$(HELM_ENV)
HELM_VALUES ?= $(HELM_CHART)/values-$(HELM_ENV).yaml
HELM_REVISION ?= 1
WORKFLOW_API_PORT_START ?= 8081
WORKFLOW_API_PORT_END ?= 8099
HYBRID_SUPPORT_SERVICES ?= postgres-conduktor conduktor
PYTHON_SRC ?= pipelines/airflow pipelines/bi_dashboards pipelines/governance pipelines/great_expectations pipelines/kafka pipelines/ml pipelines/monitoring pipelines/spark pipelines/storage devtools/serve_wiki.py
TEXT_FILE_TYPES ?= \( -name '*.md' -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' -o -name '*.js' -o -name '*.css' -o -name '*.html' \)
YAML_FILE_TYPES ?= \( -name '*.yml' -o -name '*.yaml' \)
COMMON_EXCLUDES ?= ! -path './.venv/*' ! -path './.git/*' ! -path './java-api/target/*'
SPARK_SERVICE_RUNNING ?= $(COMPOSE_MAIN) ps --services --filter status=running | grep -qx spark
SPARK_SUBMIT_BASE ?= /opt/spark/bin/spark-submit --master local[2]
SEED_DEMO_DATA_PY ?= import os,boto3; endpoint=os.getenv("MINIO_ENDPOINT","http://minio:9000"); s3=boto3.client("s3", endpoint_url=endpoint, aws_access_key_id="minio", aws_secret_access_key="minio123"); existing={b["Name"] for b in s3.list_buckets().get("Buckets", [])}; [s3.create_bucket(Bucket=b) for b in ("raw-data","processed-data") if b not in existing]; data="order_id,customer_id,amount\n1,1001,120.5\n2,1002,75.0\n3,1001,30.0\n4,1003,200.0\n"; s3.put_object(Bucket="raw-data", Key="orders/orders.csv", Body=data.encode("utf-8")); print("Seeded MinIO demo data at s3://raw-data/orders/orders.csv via " + endpoint)

.PHONY: help up down restart ps logs clean \
	format format-python format-text terraform-fmt \
	validate validate-compose validate-shell validate-python validate-json validate-yaml validate-notebook validate-format validate-terraform \
	terraform-init terraform-validate \
	helm-lint helm-check-all helm-template helm-template-qa helm-template-stg helm-template-prd \
	helm-deploy helm-deploy-qa helm-deploy-stg helm-deploy-prd \
	helm-status helm-history helm-rollback helm-uninstall \
	helm-rollback-qa helm-rollback-stg helm-rollback-prd \
	run-kafka-producer run-streaming-job run-batch-job run-iceberg-demo prepare-demo-data \
	run-java-api-local run-java-api-compose run-java-api-local-safe \
	build-java-api-container run-java-api-container stop-java-api-container logs-java-api-container \
	run-web run-wiki run-devtools \
	kind-up kind-deploy kind-status kind-smoke kind-down \
	hybrid-up hybrid-status hybrid-down

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; print "Available targets:"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-26s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start full platform with Docker Compose
	$(COMPOSE_MAIN) up --build -d

down: ## Stop platform containers
	$(COMPOSE_MAIN) down

restart: ## Restart platform containers
	$(COMPOSE_MAIN) restart

ps: ## List platform container status
	$(COMPOSE_MAIN) ps

logs: ## Tail logs for core services
	$(COMPOSE_MAIN) logs --tail=200 airflow-webserver spark kafka postgres mysql

clean: ## Stop containers and remove volumes
	$(COMPOSE_MAIN) down -v

format: format-python format-text terraform-fmt ## Run all formatters

format-python: ## Format Python source files with Black
	$(PYTHON) -m black $(PYTHON_SRC)

format-text: ## Format markdown/yaml/json/js/css/html with Prettier
	find . -type f $(TEXT_FILE_TYPES) \
		$(COMMON_EXCLUDES) \
		-print0 | xargs -0 $(PRETTIER) --write

terraform-fmt: ## Format Terraform files
	$(TERRAFORM) -chdir=iac fmt -recursive

validate: validate-compose validate-shell validate-python validate-json validate-yaml validate-notebook validate-format validate-terraform ## Run full project validation

validate-compose: ## Validate docker-compose configuration files
	$(COMPOSE_MAIN) config >/dev/null
	$(COMPOSE_CI) config >/dev/null

validate-shell: ## Validate shell script syntax
	find . -type f -name '*.sh' $(COMMON_EXCLUDES) -print0 | xargs -0 -n1 bash -n

validate-python: ## Validate Python syntax
	$(PYTHON) -m compileall $(PYTHON_SRC)

validate-json: ## Validate JSON files
	@find . -type f -name '*.json' \
		$(COMMON_EXCLUDES) \
		-print0 | xargs -0 -n1 $(PYTHON) -m json.tool >/dev/null
	@echo "JSON validation passed."

validate-yaml: ## Validate YAML files
	@find . -type f $(YAML_FILE_TYPES) \
		$(COMMON_EXCLUDES) \
		-print0 | xargs -0 -n1 $(PYTHON) -c "import sys,yaml; list(yaml.safe_load_all(open(sys.argv[1], encoding='utf-8')))"
	@echo "YAML validation passed."

validate-notebook: ## Validate notebook schema
	@$(PYTHON) -c "import nbformat; nbformat.read(open('notebooks/modern-data-stack.ipynb','r',encoding='utf-8'), as_version=4); print('Notebook schema validation passed.')"

validate-format: ## Check markdown/yaml/json/js/css/html formatting
	find . -type f $(TEXT_FILE_TYPES) \
		$(COMMON_EXCLUDES) \
		-print0 | xargs -0 $(PRETTIER) --check

validate-terraform: ## Validate Terraform formatting and configuration
	$(TERRAFORM) -chdir=iac fmt -check -recursive
	$(TERRAFORM) -chdir=iac init -backend=false -input=false >/dev/null
	$(TERRAFORM) -chdir=iac validate

terraform-init: ## Initialize Terraform providers/modules
	$(TERRAFORM) -chdir=iac init -backend=false -input=false

terraform-validate: ## Validate Terraform only
	$(TERRAFORM) -chdir=iac init -backend=false -input=false >/dev/null
	$(TERRAFORM) -chdir=iac validate

helm-lint: ## Lint in-repo Helm chart
	$(HELM) lint $(HELM_CHART)

helm-check-all: ## Lint chart and render qa/stg/prd templates
	$(MAKE) helm-lint
	$(MAKE) helm-template-qa >/dev/null
	$(MAKE) helm-template-stg >/dev/null
	$(MAKE) helm-template-prd >/dev/null
	@echo "Helm lint and template checks passed for qa/stg/prd."

helm-template: ## Render Helm chart for HELM_ENV (default qa)
	$(HELM) template $(HELM_RELEASE) $(HELM_CHART) \
		--namespace $(HELM_NAMESPACE) \
		-f $(HELM_CHART)/values.yaml \
		-f $(HELM_VALUES)

helm-template-qa: ## Render Helm chart for qa environment
	$(MAKE) helm-template HELM_ENV=qa

helm-template-stg: ## Render Helm chart for stg environment
	$(MAKE) helm-template HELM_ENV=stg

helm-template-prd: ## Render Helm chart for prd environment
	$(MAKE) helm-template HELM_ENV=prd

helm-deploy: ## Install/upgrade Helm release for HELM_ENV (default qa)
	$(HELM) upgrade --install $(HELM_RELEASE) $(HELM_CHART) \
		--namespace $(HELM_NAMESPACE) \
		--create-namespace \
		-f $(HELM_CHART)/values.yaml \
		-f $(HELM_VALUES) \
		--wait \
		--timeout 10m

helm-deploy-qa: ## Install/upgrade Helm release for qa environment
	$(MAKE) helm-deploy HELM_ENV=qa

helm-deploy-stg: ## Install/upgrade Helm release for stg environment
	$(MAKE) helm-deploy HELM_ENV=stg

helm-deploy-prd: ## Install/upgrade Helm release for prd environment
	$(MAKE) helm-deploy HELM_ENV=prd

helm-status: ## Show Helm release status for HELM_ENV (default qa)
	$(HELM) status $(HELM_RELEASE) -n $(HELM_NAMESPACE)

helm-history: ## Show Helm release history for HELM_ENV (default qa)
	$(HELM) history $(HELM_RELEASE) -n $(HELM_NAMESPACE)

helm-rollback: ## Roll back Helm release to HELM_REVISION for HELM_ENV
	$(HELM) rollback $(HELM_RELEASE) $(HELM_REVISION) -n $(HELM_NAMESPACE) --wait --timeout 10m

helm-rollback-qa: ## Roll back qa Helm release to HELM_REVISION
	$(MAKE) helm-rollback HELM_ENV=qa

helm-rollback-stg: ## Roll back stg Helm release to HELM_REVISION
	$(MAKE) helm-rollback HELM_ENV=stg

helm-rollback-prd: ## Roll back prd Helm release to HELM_REVISION
	$(MAKE) helm-rollback HELM_ENV=prd

helm-uninstall: ## Uninstall Helm release for HELM_ENV (default qa)
	$(HELM) uninstall $(HELM_RELEASE) -n $(HELM_NAMESPACE)

run-java-api-local: ## Run Java API from repo root using local profile
	mvn -f java-api/pom.xml spring-boot:run -Dspring-boot.run.profiles=local -DskipTests

run-java-api-compose: ## Run Java API from repo root using compose profile
	mvn -f java-api/pom.xml spring-boot:run -Dspring-boot.run.profiles=compose -DskipTests

run-java-api-local-safe: ## Stop process on 8081, then run Java API local profile
	@if lsof -ti tcp:8081 >/dev/null 2>&1; then \
		echo "Stopping process on port 8081..."; \
		kill $$(lsof -ti tcp:8081); \
		sleep 1; \
	fi
	mvn -f java-api/pom.xml spring-boot:run -Dspring-boot.run.profiles=local -DskipTests

build-java-api-container: ## Build Java API container image
	$(COMPOSE_MAIN) build workflow-api

run-java-api-container: ## Run Java API as Docker Compose service on port 8081
	@for pid in $$(lsof -ti tcp:8081 2>/dev/null); do \
		cmd=$$(ps -p $$pid -o comm= | tr -d ' '); \
		if [ "$$cmd" = "java" ]; then \
			echo "Stopping Java process on port 8081 (pid=$$pid)..."; \
			kill $$pid; \
			sleep 1; \
		fi; \
	done
	@PORT=""; \
	for p in $$(seq $(WORKFLOW_API_PORT_START) $(WORKFLOW_API_PORT_END)); do \
		if ! lsof -ti tcp:$$p >/dev/null 2>&1; then \
			PORT=$$p; \
			break; \
		fi; \
	done; \
	if [ -z "$$PORT" ]; then \
		echo "No free port found in range $(WORKFLOW_API_PORT_START)-$(WORKFLOW_API_PORT_END)."; \
		exit 1; \
	fi; \
	echo "Starting workflow-api on $$PORT."; \
	WORKFLOW_API_PORT=$$PORT $(COMPOSE_MAIN) up -d --force-recreate --no-deps workflow-api || exit $$?; \
	echo "workflow-api container is available at http://localhost:$$PORT"

stop-java-api-container: ## Stop Java API Docker Compose service
	$(COMPOSE_MAIN) stop workflow-api

logs-java-api-container: ## Tail Java API container logs
	$(COMPOSE_MAIN) logs --tail=200 -f workflow-api

run-wiki: ## Run local wiki server (override port: make run-wiki WIKI_PORT=3000)
	$(PYTHON) devtools/serve_wiki.py $(WIKI_PORT)

run-devtools: run-wiki ## Alias to run local devtools wiki server

run-web: ## Run local web + docs server (open /web/index.html; override port with WEB_PORT)
	@echo "Open http://localhost:$(WEB_PORT)/web/index.html"
	$(PYTHON) -m http.server $(WEB_PORT)

kind-up: ## Create local kind cluster for Kubernetes deployment
	$(KIND) create cluster --name $(KIND_CLUSTER) --config k8s/kind/cluster-config.yaml

kind-deploy: ## Deploy local stack into kind (build/load/apply/wait)
	./ops/deploy-kind.sh

kind-status: ## Show status of pods/services in local kind namespace
	$(KUBECTL) -n $(KIND_NAMESPACE) get pods,svc

kind-smoke: ## Run local smoke checks for kind deployment
	./ops/kind-smoke.sh

kind-down: ## Delete local kind cluster
	$(KIND) delete cluster --name $(KIND_CLUSTER)

hybrid-up: ## Start compose support services and deploy local kind stack
	$(COMPOSE_MAIN) up -d --no-deps $(HYBRID_SUPPORT_SERVICES)
	./ops/deploy-kind.sh

hybrid-status: ## Show compose support services and kind namespace status
	$(COMPOSE_MAIN) ps $(HYBRID_SUPPORT_SERVICES)
	$(KUBECTL) -n $(KIND_NAMESPACE) get pods,svc

hybrid-down: ## Stop hybrid compose support services and delete local kind cluster
	$(COMPOSE_MAIN) stop $(HYBRID_SUPPORT_SERVICES)
	$(COMPOSE_MAIN) rm -f $(HYBRID_SUPPORT_SERVICES)
	$(KIND) delete cluster --name $(KIND_CLUSTER)

run-kafka-producer: ## Run Kafka producer in compose stack
	@if $(SPARK_SERVICE_RUNNING); then \
		echo "Running producer in compose spark service..."; \
		$(COMPOSE_MAIN) exec -e KAFKA_TOPIC=events spark python3 /opt/kafka_jobs/producer.py; \
	else \
		echo "Compose spark service is not running. Using one-off spark container against host Kafka (hybrid mode)..."; \
		$(COMPOSE_MAIN) run --rm --no-deps \
			-e KAFKA_TOPIC=events \
			-e KAFKA_BROKER=host.docker.internal:9092 \
			spark python3 /opt/kafka_jobs/producer.py; \
	fi

run-streaming-job: ## Run Spark streaming job in compose stack
	@if $(SPARK_SERVICE_RUNNING); then \
		echo "Running streaming job in compose spark service..."; \
		MINIO_ENDPOINT=$$(if $(COMPOSE_MAIN) ps --services --filter status=running | grep -qx minio; then echo http://minio:9000; else echo http://host.docker.internal:9000; fi); \
		$(COMPOSE_MAIN) exec -T -e MINIO_ENDPOINT=$$MINIO_ENDPOINT spark $(SPARK_SUBMIT_BASE) --driver-memory 1g /opt/spark_jobs/spark_streaming_job.py; \
	else \
		echo "Compose spark service is not running. Using one-off spark container against host Kafka/MinIO (hybrid mode)..."; \
		$(COMPOSE_MAIN) run --rm --no-deps \
			-e KAFKA_BROKER=host.docker.internal:9092 \
			-e MINIO_ENDPOINT=http://host.docker.internal:9000 \
			-e POSTGRES_HOST=host.docker.internal \
			spark $(SPARK_SUBMIT_BASE) --driver-memory 1g /opt/spark_jobs/spark_streaming_job.py; \
	fi

run-batch-job: prepare-demo-data ## Run Spark batch job in compose stack
	@if $(SPARK_SERVICE_RUNNING); then \
		echo "Running batch job in compose spark service..."; \
		MINIO_ENDPOINT=$$(if $(COMPOSE_MAIN) ps --services --filter status=running | grep -qx minio; then echo http://minio:9000; else echo http://host.docker.internal:9000; fi); \
		$(COMPOSE_MAIN) exec -T -e MINIO_ENDPOINT=$$MINIO_ENDPOINT spark $(SPARK_SUBMIT_BASE) /opt/spark_jobs/spark_batch_job.py; \
	else \
		echo "Compose spark service is not running. Using one-off spark container against host MinIO (hybrid mode)..."; \
		$(COMPOSE_MAIN) run --rm --no-deps \
			-e MINIO_ENDPOINT=http://host.docker.internal:9000 \
			spark $(SPARK_SUBMIT_BASE) /opt/spark_jobs/spark_batch_job.py; \
	fi
	@echo "Batch job finished successfully. Output CSV: /tmp/transformed_orders.csv"

prepare-demo-data: ## Ensure MinIO buckets and sample orders CSV exist for Spark batch demo
	@if $(SPARK_SERVICE_RUNNING); then \
		echo "Seeding demo data using compose spark service..."; \
		MINIO_ENDPOINT=$$(if $(COMPOSE_MAIN) ps --services --filter status=running | grep -qx minio; then echo http://minio:9000; else echo http://host.docker.internal:9000; fi); \
		$(COMPOSE_MAIN) exec -T -e MINIO_ENDPOINT=$$MINIO_ENDPOINT spark python3 -c '$(SEED_DEMO_DATA_PY)'; \
	else \
		if $(KUBECTL) -n $(KIND_NAMESPACE) get deployment airflow-webserver >/dev/null 2>&1; then \
			echo "Compose spark service is not running. Seeding demo data via airflow pod in kind namespace..."; \
			AIRFLOW_POD=$$($(KUBECTL) -n $(KIND_NAMESPACE) get pod -l app=airflow-webserver -o jsonpath='{.items[0].metadata.name}'); \
			$(KUBECTL) -n $(KIND_NAMESPACE) exec $$AIRFLOW_POD -- env MINIO_ENDPOINT=http://minio:9000 python3 -c '$(SEED_DEMO_DATA_PY)'; \
		else \
			echo "Compose spark service is not running. Using one-off spark container against host MinIO (hybrid mode)..."; \
			$(COMPOSE_MAIN) run --rm --no-deps -e MINIO_ENDPOINT=http://host.docker.internal:9000 spark python3 -c '$(SEED_DEMO_DATA_PY)'; \
		fi; \
	fi

run-iceberg-demo: prepare-demo-data ## Run Spark batch job with Iceberg table write enabled
	@if $(SPARK_SERVICE_RUNNING); then \
		echo "Running Iceberg demo in compose spark service..."; \
		MINIO_ENDPOINT=$$(if $(COMPOSE_MAIN) ps --services --filter status=running | grep -qx minio; then echo http://minio:9000; else echo http://host.docker.internal:9000; fi); \
		$(COMPOSE_MAIN) exec -T \
			-e MINIO_ENDPOINT=$$MINIO_ENDPOINT \
			-e ENABLE_ICEBERG=true \
			-e ICEBERG_CATALOG=local \
			-e ICEBERG_NAMESPACE=analytics \
			-e ICEBERG_TABLE=orders \
			-e ICEBERG_WAREHOUSE=file:///tmp/iceberg_warehouse \
			spark $(SPARK_SUBMIT_BASE) /opt/spark_jobs/spark_batch_job.py; \
	else \
		echo "Compose spark service is not running. Using one-off spark container for Iceberg demo (hybrid mode)..."; \
		$(COMPOSE_MAIN) run --rm --no-deps \
			-e MINIO_ENDPOINT=http://host.docker.internal:9000 \
			-e ENABLE_ICEBERG=true \
			-e ICEBERG_CATALOG=local \
			-e ICEBERG_NAMESPACE=analytics \
			-e ICEBERG_TABLE=orders \
			-e ICEBERG_WAREHOUSE=file:///tmp/iceberg_warehouse \
			spark $(SPARK_SUBMIT_BASE) /opt/spark_jobs/spark_batch_job.py; \
	fi
	@echo "Iceberg demo finished successfully. Table: local.analytics.orders (warehouse=file:///tmp/iceberg_warehouse)"
