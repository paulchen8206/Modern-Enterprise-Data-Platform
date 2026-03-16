"""ML training and tracking stub.

Consumes feature updates, trains a simple regression model, and logs artifacts
to MLflow for experiment tracking.
"""

import mlflow
import mlflow.sklearn
import feast
import pandas as pd
import numpy as np
import os
from abc import ABC, abstractmethod
from kafka import KafkaConsumer
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, avg, max
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

# ---------------------------
# CONFIGURATION
# ---------------------------
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor_readings")
FEAST_REPO_PATH = os.getenv("FEAST_REPO_PATH", "./feature_repo")

# Initialize MLflow & Feast
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment("device_readings_experiment")
store = feast.FeatureStore(repo_path=FEAST_REPO_PATH)

# ---------------------------
# SPARK STREAMING SETUP
# ---------------------------
spark = SparkSession.builder.appName("MLTrainingPipeline").getOrCreate()

schema = StructType(
    [
        StructField("event_id", StringType(), True),
        StructField("timestamp", LongType(), True),
        StructField("device_id", LongType(), True),
        StructField("reading_value", DoubleType(), True),
    ]
)


class RollingFeatureStrategy(ABC):
    """Strategy interface for computing rolling feature values."""

    @abstractmethod
    def next_average(self, existing_avg, reading_value):
        pass

    @abstractmethod
    def next_max(self, existing_max, reading_value):
        pass


class MeanMaxRollingStrategy(RollingFeatureStrategy):
    """Default averaging and max strategy for online feature updates."""

    def next_average(self, existing_avg, reading_value):
        safe_avg = existing_avg if existing_avg is not None else 0
        return (safe_avg + reading_value) / 2

    def next_max(self, existing_max, reading_value):
        safe_max = existing_max if existing_max is not None else 0
        return max(safe_max, reading_value)


rolling_feature_strategy = MeanMaxRollingStrategy()


# ---------------------------
# FUNCTION: STREAM DATA & STORE FEATURES
# ---------------------------
def consume_kafka_and_store_features():
    """
    Listens to Kafka, extracts features, and stores in Feast.
    """
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    print(f"✅ Listening for streaming data on Kafka topic: {KAFKA_TOPIC}")

    for message in consumer:
        data = message.value
        device_id = data.get("device_id")
        reading_value = data.get("reading_value")

        if device_id is None or reading_value is None:
            continue  # Ignore malformed messages

        # Pull current online features to update rolling statistics incrementally.
        existing_features = store.get_online_features(
            features=["device_features:avg_reading", "device_features:max_reading"],
            entity_rows=[{"device_id": device_id}],
        ).to_dict()

        # Compute updated features via pluggable rolling strategy.
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
                    "timestamp": int(data.get("timestamp", 0)),
                }
            ]
        )

        # Store in Feast
        store.ingest("device_features", feature_data)

        print(
            f"✅ Stored features for device {device_id}: {feature_data.to_dict(orient='records')}"
        )


# ---------------------------
# FUNCTION: TRAIN MODEL WITH REAL FEATURES
# ---------------------------
def fetch_features_from_feast():
    """
    Retrieve real-time feature data for all available device IDs from Feast.
    """
    device_ids = list(range(1000, 1100))  # Assuming we have 100 devices streaming data

    feature_refs = [
        "device_features:avg_reading",
        "device_features:max_reading",
        "device_features:timestamp",
    ]

    feature_vector = store.get_online_features(
        features=feature_refs,
        entity_rows=[{"device_id": device_id} for device_id in device_ids],
    ).to_dict()

    df = pd.DataFrame(feature_vector)
    df = df.drop(columns=["device_features:timestamp"])  # Drop timestamp if unnecessary
    df.rename(columns=lambda x: x.replace("device_features:", ""), inplace=True)

    return df


def train_and_log_model():
    """
    Train a Linear Regression model using real streaming data and log it to MLflow.
    """
    # Fetch real features from Feast
    features_df = fetch_features_from_feast()

    if features_df.empty:
        print(
            "❌ No features found in Feast. Ensure Kafka is streaming and Feast is populated."
        )
        return

    # Synthetic target keeps this demo self-contained without labeled ground truth.
    y = (
        2.5 * features_df["avg_reading"]
        + 1.8 * features_df["max_reading"]
        + np.random.randn(len(features_df)) * 10
    )

    # Split Data
    X_train, X_test, y_train, y_test = train_test_split(
        features_df, y, test_size=0.2, random_state=42
    )

    with mlflow.start_run():
        model = LinearRegression()
        model.fit(X_train, y_train)

        # Predictions
        y_pred = model.predict(X_test)

        # Compute Metrics
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        # Log Parameters & Metrics
        mlflow.log_param("model_type", "LinearRegression")
        mlflow.log_metric("mse", mse)
        mlflow.log_metric("r2_score", r2)

        # Log Model
        mlflow.sklearn.log_model(model, "linear_regression_model")

        print(f"✅ Model trained & logged to MLflow | MSE: {mse:.4f} | R²: {r2:.4f}")


# ---------------------------
# MAIN EXECUTION
# ---------------------------
if __name__ == "__main__":
    # 1️⃣ Start consuming real Kafka streaming data & store features
    consume_kafka_and_store_features()

    # 2️⃣ Train ML model with real Feast features
    train_and_log_model()
