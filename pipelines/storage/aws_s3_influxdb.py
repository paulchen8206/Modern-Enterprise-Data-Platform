"""Streaming-to-time-series plus batch-archive storage stub.

Consumes Kafka events into InfluxDB and periodically exports recent data to S3.
"""

import os
import boto3
import pandas as pd
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from pyspark.sql import SparkSession

from pipeline_patterns import RequiredFieldsValidator, StreamProcessor, with_default_timestamp

# ---------------------------
# CONFIGURATION
# ---------------------------
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor_readings")

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "my-iot-data")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY", "your-access-key")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", "your-secret-key")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "my-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "iot_data")

# ---------------------------
# AWS S3 CLIENT
# ---------------------------
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION,
)

# ---------------------------
# INFLUXDB CLIENT
# ---------------------------
influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = influx_client.write_api(write_options=WritePrecision.NS)

# ---------------------------
# SPARK SESSION
# ---------------------------
spark = SparkSession.builder.appName("AWS_S3_InfluxDB_Pipeline").getOrCreate()


class InfluxStreamingPipeline(StreamProcessor):
    """Template-based Kafka-to-InfluxDB stream sink."""

    def transform(self, payload):
        return {
            "device_id": payload["device_id"],
            "reading_value": payload["reading_value"],
            "timestamp": with_default_timestamp(payload),
        }

    def persist(self, transformed, raw_payload):
        # Store each reading as a tagged point for fast time-series queries.
        point = (
            Point("sensor_readings")
            .tag("device_id", str(transformed["device_id"]))
            .field("reading_value", transformed["reading_value"])
            .time(transformed["timestamp"], WritePrecision.S)
        )
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        print(
            f"Stored in InfluxDB: Device {transformed['device_id']} | Reading {transformed['reading_value']}"
        )


def consume_kafka_to_influx():
    """Consumes real-time sensor data from Kafka and stores it in InfluxDB."""
    pipeline = InfluxStreamingPipeline(
        topic=KAFKA_TOPIC,
        broker=KAFKA_BROKER,
        validator=RequiredFieldsValidator(["device_id", "reading_value"]),
    )
    pipeline.run()


# ---------------------------
# FUNCTION: EXTRACT DATA FROM INFLUXDB & UPLOAD TO S3
# ---------------------------
def extract_from_influx_and_upload_s3():
    """
    Extracts batch data from InfluxDB, converts it to CSV, and uploads to AWS S3.
    """
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "sensor_readings")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """

    query_api = influx_client.query_api()
    tables = query_api.query(query, org=INFLUXDB_ORG)

    # Flatten Flux query output into a tabular file for downstream analytics.
    # Convert query results to DataFrame
    data = []
    for table in tables:
        for record in table.records:
            data.append(record.values)

    df = pd.DataFrame(data)

    if df.empty:
        print("❌ No data available for extraction.")
        return

    # Save to CSV
    csv_filename = f"iot_data_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(csv_filename, index=False)
    print(f"✅ Extracted data from InfluxDB and saved as {csv_filename}")

    # Upload to AWS S3
    s3_client.upload_file(csv_filename, AWS_S3_BUCKET, f"iot_data/{csv_filename}")
    print(f"✅ Uploaded {csv_filename} to S3 bucket {AWS_S3_BUCKET}")


# ---------------------------
# MAIN EXECUTION
# ---------------------------
if __name__ == "__main__":
    # Step 1️⃣: Consume Kafka sensor data & store in InfluxDB
    consume_kafka_to_influx()

    # Step 2️⃣: Extract batch data from InfluxDB and upload to S3
    extract_from_influx_and_upload_s3()
