"""Feature store streaming stub.

Consumes Kafka sensor events and maintains lightweight online aggregates in Feast.
"""

import os
import feast
import pandas as pd
from abc import ABC, abstractmethod
from feast import FeatureStore, Entity, FeatureView, Field
from feast.types import Float32, Int64
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, avg, max
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType
from kafka import KafkaConsumer
import json

# Feast Configuration
FEAST_REPO_PATH = os.getenv("FEAST_REPO_PATH", "./feature_repo")
store = FeatureStore(repo_path=FEAST_REPO_PATH)

# Kafka Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor_readings")

# Spark session is kept for parity with broader pipeline tooling in this project.
spark = SparkSession.builder.appName("StreamingFeatureProcessing").getOrCreate()

# Define Schema for incoming JSON sensor readings
schema = StructType(
    [
        StructField("event_id", StringType(), True),
        StructField("timestamp", LongType(), True),
        StructField("device_id", Int64(), True),
        StructField("reading_value", Float32(), True),
    ]
)

# Define Feast Entity
device_entity = Entity(
    name="device_id", value_type=Int64, description="Unique identifier for IoT devices"
)

# Define Feast Feature View for storing real-time features
device_feature_view = FeatureView(
    name="device_features",
    entities=["device_id"],
    schema=[
        Field(name="avg_reading", dtype=Float32),
        Field(name="max_reading", dtype=Float32),
        Field(name="timestamp", dtype=Int64),
    ],
    online=True,  # Enable real-time serving
)


class RollingFeatureStrategy(ABC):
    """Strategy interface for computing rolling aggregate features."""

    @abstractmethod
    def next_average(self, existing_avg, reading_value):
        pass

    @abstractmethod
    def next_max(self, existing_max, reading_value):
        pass


class MeanMaxRollingStrategy(RollingFeatureStrategy):
    """Default strategy for online average/max updates."""

    def next_average(self, existing_avg, reading_value):
        safe_avg = existing_avg if existing_avg is not None else 0
        return (safe_avg + reading_value) / 2

    def next_max(self, existing_max, reading_value):
        safe_max = existing_max if existing_max is not None else 0
        return max(safe_max, reading_value)


rolling_feature_strategy = MeanMaxRollingStrategy()


def consume_stream_and_store_features():
    """
    Consumes real-time Kafka messages, extracts features, and stores in Feast Feature Store.
    """
    # Connect to Kafka
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    print(f"✅ Listening for sensor data on Kafka topic: {KAFKA_TOPIC}")

    for message in consumer:
        data = message.value
        device_id = data.get("device_id")
        reading_value = data.get("reading_value")

        if device_id is None or reading_value is None:
            continue  # Skip malformed data

        # Read current online features so we can maintain rolling aggregates.
        existing_features = store.get_online_features(
            features=["device_features:avg_reading", "device_features:max_reading"],
            entity_rows=[{"device_id": device_id}],
        ).to_dict()

        # Compute new aggregate features via strategy to keep logic swappable.
        avg_reading = rolling_feature_strategy.next_average(
            existing_features["device_features:avg_reading"][0], reading_value
        )
        max_reading = rolling_feature_strategy.next_max(
            existing_features["device_features:max_reading"][0], reading_value
        )

        # Prepare DataFrame for Feast ingestion
        feature_data = pd.DataFrame(
            [
                {
                    "device_id": device_id,
                    "avg_reading": avg_reading,
                    "max_reading": max_reading,
                    "timestamp": int(datetime.utcnow().timestamp()),
                }
            ]
        )

        # Store in Feast
        store.apply([device_entity, device_feature_view])
        store.ingest("device_features", feature_data)

        print(
            f"✅ Stored features for device {device_id}: {feature_data.to_dict(orient='records')}"
        )


def get_features(device_ids):
    """
    Fetch stored features for given device_ids from the Feast Feature Store.
    """
    feature_refs = [
        "device_features:avg_reading",
        "device_features:max_reading",
        "device_features:timestamp",
    ]

    # Batch fetch keeps API calls compact when querying multiple entities.
    feature_vector = store.get_online_features(
        features=feature_refs,
        entity_rows=[{"device_id": device_id} for device_id in device_ids],
    ).to_dict()

    return feature_vector


if __name__ == "__main__":
    # Start consuming and storing real-time features
    consume_stream_and_store_features()
