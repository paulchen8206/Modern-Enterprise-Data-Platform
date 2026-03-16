"""Apache Atlas lineage registration stub.

Provides simple existence checks and lineage registration calls for local demos.
"""

import json
import logging
import os
import requests

# Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Apache Atlas / OpenMetadata Configuration
ATLAS_API_URL = os.getenv("ATLAS_API_URL", "http://atlas:21000/api/atlas/v2/lineage")
ATLAS_USERNAME = os.getenv("ATLAS_USERNAME", "admin")
ATLAS_PASSWORD = os.getenv("ATLAS_PASSWORD", "admin")

# Headers for API requests
HEADERS = {"Content-Type": "application/json"}


class AtlasApiClient:
    """Adapter that encapsulates Atlas HTTP/auth concerns."""

    def __init__(self, api_url, username, password, headers):
        self.api_url = api_url
        self.auth = (username, password)
        self.headers = headers

    def get(self, path):
        return requests.get(
            f"{self.api_url}{path}", auth=self.auth, headers=self.headers
        )

    def post(self, path, payload):
        return requests.post(
            f"{self.api_url}{path}",
            auth=self.auth,
            headers=self.headers,
            data=json.dumps(payload),
        )


class LineageRegistrar:
    """Facade for lineage-related existence checks and registration."""

    def __init__(self, atlas_client):
        self.atlas_client = atlas_client

    def dataset_exists(self, dataset_name):
        try:
            response = self.atlas_client.get(
                f"/entities?type=Dataset&name={dataset_name}"
            )
            if response.status_code != 200:
                logging.error(
                    f"Failed to check dataset existence: {response.status_code} - {response.text}"
                )
                return False
            data = response.json()
            exists = "entities" in data and len(data["entities"]) > 0
            if exists:
                logging.info(f"Dataset '{dataset_name}' exists in Apache Atlas.")
            else:
                logging.warning(
                    f"Dataset '{dataset_name}' does not exist in Apache Atlas."
                )
            return exists
        except requests.RequestException as e:
            logging.error(f"Error while checking dataset existence: {str(e)}")
            return False

    def register_lineage(self, source_name, target_name, extra_info=None):
        if not self.dataset_exists(source_name) or not self.dataset_exists(target_name):
            logging.error("Cannot register lineage: One or both datasets do not exist.")
            return

        lineage_payload = {
            "guidEntityMap": {},
            "relations": [
                {
                    "typeName": "Process",
                    "fromEntityId": source_name,
                    "toEntityId": target_name,
                    "relationshipAttributes": extra_info or {},
                }
            ],
        }

        try:
            response = self.atlas_client.post("/entities", lineage_payload)
            if response.status_code in [200, 201]:
                logging.info(
                    f"Successfully registered lineage from '{source_name}' to '{target_name}'"
                )
            else:
                logging.error(
                    f"Failed to register lineage: {response.status_code} - {response.text}"
                )
        except requests.RequestException as e:
            logging.error(f"Error while registering dataset lineage: {str(e)}")


atlas_client = AtlasApiClient(ATLAS_API_URL, ATLAS_USERNAME, ATLAS_PASSWORD, HEADERS)
lineage_registrar = LineageRegistrar(atlas_client)


def check_dataset_exists(dataset_name):
    """
    Checks if a dataset exists in Apache Atlas or OpenMetadata before registering lineage.

    :param dataset_name: str, dataset qualified name (e.g., "mysql.orders")
    :return: bool, True if dataset exists, False otherwise
    """
    return lineage_registrar.dataset_exists(dataset_name)


def register_dataset_lineage(source_name, target_name, extra_info=None):
    """
    Registers dataset lineage in Apache Atlas / OpenMetadata via REST API.

    :param source_name: str, qualified name of the source dataset (e.g., "mysql.orders")
    :param target_name: str, qualified name of the target dataset (e.g., "minio.raw-data.orders")
    :param extra_info: dict, additional metadata such as transformations, job details, timestamps
    """
    lineage_registrar.register_lineage(source_name, target_name, extra_info)


if __name__ == "__main__":
    # Example lineage edge used during local smoke runs.
    register_dataset_lineage(
        "mysql.orders",
        "minio.raw-data.orders",
        {"job": "batch_ingestion_dag", "transformation": "cleaning, enrichment"},
    )
