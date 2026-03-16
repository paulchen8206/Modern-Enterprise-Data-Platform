"""Kafka-to-MongoDB streaming sink for raw sensor events."""

import os
from pymongo import MongoClient

from pipeline_patterns import RequiredFieldsValidator, StreamProcessor, with_default_timestamp

# ---------------------------
# CONFIGURATION
# ---------------------------
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor_readings")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DB = os.getenv("MONGODB_DB", "iot_data")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "sensor_readings")

# ---------------------------
# CONNECT TO MONGODB
# ---------------------------
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]

class MongoStreamingPipeline(StreamProcessor):
    """Template-based Kafka-to-MongoDB sink pipeline."""

    def transform(self, payload):
        return {
            "device_id": payload["device_id"],
            "reading_value": payload["reading_value"],
            "timestamp": with_default_timestamp(payload),
        }

    def persist(self, transformed, raw_payload):
        # Persist raw records first; enrichment can happen in downstream jobs.
        collection.insert_one(transformed)
        print(
            f"Stored in MongoDB: Device {transformed['device_id']} | Reading {transformed['reading_value']}"
        )


# ---------------------------
# MAIN EXECUTION
# ---------------------------
if __name__ == "__main__":
    pipeline = MongoStreamingPipeline(
        topic=KAFKA_TOPIC,
        broker=KAFKA_BROKER,
        validator=RequiredFieldsValidator(["device_id", "reading_value"]),
    )
    pipeline.run()
