"""Prometheus/Grafana local bootstrap helper.

Starts both services and configures Grafana datasource/dashboard resources.
"""

import os
import json
import subprocess
import time
import logging
import requests
from abc import ABC, abstractmethod

# Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Prometheus & Grafana Configurations
PROMETHEUS_CONFIG_PATH = os.getenv(
    "PROMETHEUS_CONFIG_PATH", "/etc/prometheus/prometheus.yml"
)
PROMETHEUS_PORT = os.getenv("PROMETHEUS_PORT", "9090")
GRAFANA_PORT = os.getenv("GRAFANA_PORT", "3000")
GRAFANA_API_URL = f"http://localhost:{GRAFANA_PORT}/api"
GRAFANA_ADMIN_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
GRAFANA_ADMIN_PASS = os.getenv("GRAFANA_ADMIN_PASS", "admin")
DASHBOARDS_PATH = os.getenv("DASHBOARDS_PATH", "./grafana_dashboards")


class GrafanaApiClient:
    """Adapter around Grafana REST calls used by monitoring bootstrap."""

    def __init__(self, api_url, username, password):
        self.api_url = api_url
        self.auth = (username, password)

    def is_healthy(self):
        response = requests.get(f"{self.api_url}/health")
        return response.status_code == 200

    def create_datasource(self, payload):
        return requests.post(
            f"{self.api_url}/datasources",
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
        )

    def import_dashboard(self, payload):
        return requests.post(
            f"{self.api_url}/dashboards/db",
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
        )


grafana_client = GrafanaApiClient(
    GRAFANA_API_URL,
    GRAFANA_ADMIN_USER,
    GRAFANA_ADMIN_PASS,
)


class MonitoringBootstrap(ABC):
    """Template Method for monitoring startup and Grafana provisioning."""

    def run(self):
        self.start_prometheus()
        self.start_grafana()
        if self.wait_for_grafana():
            self.configure_datasource()
            self.import_dashboards()
        logging.info("Monitoring setup complete.")

    @abstractmethod
    def start_prometheus(self):
        pass

    @abstractmethod
    def start_grafana(self):
        pass

    @abstractmethod
    def wait_for_grafana(self):
        pass

    @abstractmethod
    def configure_datasource(self):
        pass

    @abstractmethod
    def import_dashboards(self):
        pass


class LocalMonitoringBootstrap(MonitoringBootstrap):
    """Concrete monitoring bootstrap flow for local binaries and local dashboards."""

    def start_prometheus(self):
        start_prometheus()

    def start_grafana(self):
        start_grafana()

    def wait_for_grafana(self):
        return wait_for_grafana()

    def configure_datasource(self):
        create_grafana_datasource()

    def import_dashboards(self):
        import_grafana_dashboards()


def start_prometheus():
    """
    Starts Prometheus as a subprocess and ensures configuration exists.
    """
    if not os.path.exists(PROMETHEUS_CONFIG_PATH):
        logging.error(f"Prometheus config file not found: {PROMETHEUS_CONFIG_PATH}")
        return

    logging.info("Starting Prometheus...")
    try:
        subprocess.Popen(["prometheus", "--config.file", PROMETHEUS_CONFIG_PATH])
        logging.info(f"Prometheus started on port {PROMETHEUS_PORT}")
    except Exception as e:
        logging.error(f"Failed to start Prometheus: {e}")


def start_grafana():
    """
    Starts Grafana as a subprocess.
    """
    logging.info("Starting Grafana...")
    try:
        subprocess.Popen(["grafana-server"])
        logging.info(f"Grafana started on port {GRAFANA_PORT}")
    except Exception as e:
        logging.error(f"Failed to start Grafana: {e}")


def wait_for_grafana():
    """
    Waits until Grafana API is responsive before proceeding.
    """
    logging.info("Waiting for Grafana to be ready...")
    # Poll health endpoint to avoid race conditions during first-time startup.
    for _ in range(30):  # Wait for up to 30 seconds
        try:
            if grafana_client.is_healthy():
                logging.info("Grafana is ready.")
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    logging.error("Grafana did not start in time.")
    return False


def create_grafana_datasource():
    """
    Creates a Prometheus data source in Grafana via the API.
    """
    logging.info("Creating Grafana Prometheus datasource...")

    datasource_payload = {
        "name": "Prometheus",
        "type": "prometheus",
        "url": f"http://localhost:{PROMETHEUS_PORT}",
        "access": "proxy",
        "basicAuth": False,
    }

    response = grafana_client.create_datasource(datasource_payload)

    if response.status_code in [200, 201]:
        logging.info("Grafana Prometheus datasource created successfully.")
    else:
        logging.error(f"Failed to create Grafana datasource: {response.text}")


def import_grafana_dashboards():
    """
    Imports predefined Grafana dashboards from JSON files.
    """
    if not os.path.exists(DASHBOARDS_PATH):
        logging.warning(f"Dashboard directory not found: {DASHBOARDS_PATH}")
        return

    # Import every JSON dashboard in the configured directory.
    for dashboard_file in os.listdir(DASHBOARDS_PATH):
        if dashboard_file.endswith(".json"):
            dashboard_path = os.path.join(DASHBOARDS_PATH, dashboard_file)
            with open(dashboard_path, "r") as f:
                dashboard_data = json.load(f)
                dashboard_payload = {"dashboard": dashboard_data, "overwrite": True}

                response = grafana_client.import_dashboard(dashboard_payload)

                if response.status_code in [200, 201]:
                    logging.info(f"Imported Grafana dashboard: {dashboard_file}")
                else:
                    logging.error(f"Failed to import {dashboard_file}: {response.text}")


def main():
    """
    Main function to start Prometheus, Grafana, and configure monitoring.
    """
    bootstrap = LocalMonitoringBootstrap()
    bootstrap.run()


if __name__ == "__main__":
    main()
