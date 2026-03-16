"""Redis feature cache and processed-queue integration for streaming events."""

import os
import json
import redis
from kafka import KafkaProducer
from feast import FeatureStore

from pipeline_patterns import (
    CachedFeastFeatureProvider,
    RequiredFieldsValidator,
    StreamProcessor,
)

# ---------------------------
# CONFIGURATION
# ---------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC", "sensor_readings")
KAFKA_OUTPUT_TOPIC = os.getenv("KAFKA_OUTPUT_TOPIC", "processed_readings")

FEAST_REPO_PATH = os.getenv("FEAST_REPO_PATH", "./feature_repo")

# ---------------------------
# CONNECT TO REDIS
# ---------------------------
redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
)

# ---------------------------
# CONNECT TO FEATURE STORE (FEAST)
# ---------------------------
store = FeatureStore(repo_path=FEAST_REPO_PATH)

# ---------------------------
# KAFKA PRODUCER FOR PROCESSED MESSAGES
# ---------------------------
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)


feature_provider = CachedFeastFeatureProvider(redis_client=redis_client, feature_store=store)


class RedisFeaturePipeline(StreamProcessor):
    """Template-based streaming enrichment with Redis queue + Kafka output sinks."""

    def transform(self, payload):
        device_id = payload["device_id"]
        reading_value = payload["reading_value"]
        features = feature_provider.get_features(device_id)

        max_reading = features.get("max_reading") or 0
        normalized_reading = 0.0 if max_reading == 0 else reading_value / max_reading

        return {
            "device_id": device_id,
            "original_reading": reading_value,
            "normalized_reading": round(normalized_reading, 4),
            "avg_reading": features.get("avg_reading"),
        }

    def persist(self, transformed, raw_payload):
        # Push to queue for decoupled consumers (dashboards, alerts, batch drains).
        redis_client.lpush("processed_queue", json.dumps(transformed))
        print(f"Stored in Redis Queue: {transformed}")

        producer.send(KAFKA_OUTPUT_TOPIC, transformed)
        print(f"Sent to Kafka topic {KAFKA_OUTPUT_TOPIC}: {transformed}")


# ---------------------------
# FUNCTION: FETCH PROCESSED DATA FROM REDIS QUEUE
# ---------------------------
def fetch_processed_data():
    """
    Retrieves processed data from Redis queue.
    """
    queue_length = redis_client.llen("processed_queue")

    if queue_length == 0:
        print("❌ No processed data available in Redis queue.")
        return None

    processed_data = redis_client.rpop("processed_queue")
    return json.loads(processed_data) if processed_data else None


# ---------------------------
# MAIN EXECUTION
# ---------------------------
if __name__ == "__main__":
    pipeline = RedisFeaturePipeline(
        topic=KAFKA_INPUT_TOPIC,
        broker=KAFKA_BROKER,
        validator=RequiredFieldsValidator(["device_id", "reading_value"]),
    )
    pipeline.run()
