"""BI export and upload helpers.

This script exports transformed Postgres data to CSV and demonstrates upload
flows for Tableau, Looker, and Power BI APIs.
"""

import os
import pandas as pd
import psycopg2
from abc import ABC, abstractmethod
from sqlalchemy import create_engine
import requests
import json

# Database Configuration (PostgreSQL)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "processed_db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pass")

# Tableau API Configuration
TABLEAU_SERVER = os.getenv("TABLEAU_SERVER", "https://your-tableau-server.com")
TABLEAU_SITE_ID = os.getenv("TABLEAU_SITE_ID", "")
TABLEAU_USERNAME = os.getenv("TABLEAU_USERNAME", "admin")
TABLEAU_PASSWORD = os.getenv("TABLEAU_PASSWORD", "admin")
TABLEAU_PROJECT_ID = os.getenv("TABLEAU_PROJECT_ID", "project_uuid")

# Looker API Configuration
LOOKER_API_URL = os.getenv("LOOKER_API_URL", "https://your-looker-instance.com")
LOOKER_CLIENT_ID = os.getenv("LOOKER_CLIENT_ID", "your_client_id")
LOOKER_CLIENT_SECRET = os.getenv("LOOKER_CLIENT_SECRET", "your_client_secret")

# Power BI Configuration
POWER_BI_WORKSPACE_ID = os.getenv("POWER_BI_WORKSPACE_ID", "workspace_uuid")
POWER_BI_DATASET_ID = os.getenv("POWER_BI_DATASET_ID", "dataset_uuid")
POWER_BI_ACCESS_TOKEN = os.getenv("POWER_BI_ACCESS_TOKEN", "your_access_token")
CSV_EXPORT_PATH = "bi_data/orders_transformed.csv"


class BiUploader(ABC):
    """Strategy interface for uploading a prepared CSV to BI platforms."""

    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def upload(self, csv_path):
        pass


class TableauUploader(BiUploader):
    def name(self):
        return "Tableau"

    def upload(self, csv_path):
        auth_payload = {
            "credentials": {
                "name": TABLEAU_USERNAME,
                "password": TABLEAU_PASSWORD,
                "site": {"contentUrl": TABLEAU_SITE_ID},
            }
        }
        auth_response = requests.post(
            f"{TABLEAU_SERVER}/api/3.9/auth/signin", json=auth_payload
        )
        auth_response.raise_for_status()
        token = auth_response.json()["credentials"]["token"]

        with open(csv_path, "rb") as f:
            response = requests.post(
                f"{TABLEAU_SERVER}/api/3.9/sites/{TABLEAU_PROJECT_ID}/datasources",
                headers={"X-Tableau-Auth": token},
                files={"file": f},
            )
            response.raise_for_status()


class LookerUploader(BiUploader):
    def name(self):
        return "Looker"

    def upload(self, csv_path):
        auth_payload = {
            "client_id": LOOKER_CLIENT_ID,
            "client_secret": LOOKER_CLIENT_SECRET,
        }
        auth_response = requests.post(f"{LOOKER_API_URL}/login", data=auth_payload)
        auth_response.raise_for_status()
        token = auth_response.json()["access_token"]

        with open(csv_path, "rb") as f:
            response = requests.post(
                f"{LOOKER_API_URL}/upload-data",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": f},
            )
            response.raise_for_status()


class PowerBiUploader(BiUploader):
    def name(self):
        return "Power BI"

    def upload(self, csv_path):
        dataset_payload = {
            "name": "Orders Transformed",
            "tables": [
                {
                    "name": "orders",
                    "columns": [
                        {"name": "order_id", "dataType": "Int64"},
                        {"name": "customer_id", "dataType": "Int64"},
                        {"name": "amount", "dataType": "Double"},
                        {
                            "name": "processed_timestamp",
                            "dataType": "DateTime",
                        },
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {POWER_BI_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        dataset_response = requests.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{POWER_BI_WORKSPACE_ID}/datasets",
            headers=headers,
            json=dataset_payload,
        )
        dataset_response.raise_for_status()


def fetch_data():
    """
    Fetch transformed data from PostgreSQL and save as CSV for BI tools.
    """
    try:
        engine = create_engine(
            f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        # Keep extract query simple to produce a portable CSV baseline for BI tools.
        query = "SELECT * FROM orders_transformed;"
        df = pd.read_sql(query, con=engine)

        output_file = CSV_EXPORT_PATH
        df.to_csv(output_file, index=False)
        print(f"✅ Data exported for BI tools: {output_file}")

    except Exception as e:
        print(f"❌ Error fetching data from database: {e}")


def upload_to_tableau():
    """
    Upload dataset to Tableau using REST API.
    """
    try:
        TableauUploader().upload(CSV_EXPORT_PATH)
        print("✅ Data uploaded to Tableau successfully.")
    except Exception as e:
        print(f"❌ Error uploading data to Tableau: {e}")


def upload_to_looker():
    """
    Upload dataset to Looker via API.
    """
    try:
        LookerUploader().upload(CSV_EXPORT_PATH)
        print("✅ Data uploaded to Looker successfully.")
    except Exception as e:
        print(f"❌ Error uploading data to Looker: {e}")


def upload_to_power_bi():
    """
    Upload dataset to Power BI via API.
    """
    try:
        PowerBiUploader().upload(CSV_EXPORT_PATH)
        print("✅ Data uploaded to Power BI successfully.")
    except Exception as e:
        print(f"❌ Error uploading data to Power BI: {e}")


def run_uploads(uploaders, csv_path):
    """Template-style orchestration for a set of BI upload strategies."""
    for uploader in uploaders:
        try:
            uploader.upload(csv_path)
            print(f"✅ Data uploaded to {uploader.name()} successfully.")
        except Exception as exc:
            print(f"❌ Error uploading data to {uploader.name()}: {exc}")


if __name__ == "__main__":
    # Fetch data from PostgreSQL and export for BI tools
    fetch_data()

    # Upload to various BI tools
    run_uploads(
        [TableauUploader(), LookerUploader(), PowerBiUploader()],
        CSV_EXPORT_PATH,
    )
