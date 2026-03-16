import json
import time
import random
import uuid
import logging
from abc import ABC, abstractmethod
from kafka import KafkaProducer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import KafkaError
import os

# Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Kafka Configuration (Can be overridden using environment variables)
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "sensor_readings")
MESSAGE_FREQUENCY = float(
    os.getenv("MESSAGE_FREQUENCY", 1)
)  # Delay between messages (seconds)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 10))  # Number of messages per batch
ACKS_MODE = os.getenv("ACKS_MODE", "all")  # Kafka acknowledgments ("all", "1", or "0")

# Create producer once at module load to avoid reconnect overhead in the loop.
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    acks=ACKS_MODE,
)


def create_kafka_topic(topic_name):
    """
    Creates a Kafka topic if it does not exist.
    """
    try:
        # Topic bootstrap is idempotent: create if missing, otherwise continue.
        admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
        existing_topics = admin_client.list_topics()

        if topic_name not in existing_topics:
            topic = NewTopic(name=topic_name, num_partitions=3, replication_factor=1)
            admin_client.create_topics([topic])
            logging.info(f"Kafka topic '{topic_name}' created successfully.")
        else:
            logging.info(f"Kafka topic '{topic_name}' already exists.")
    except KafkaError as e:
        logging.error(f"Failed to create Kafka topic '{topic_name}': {e}")


def generate_event():
    """
    Generates a single random sensor event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "device_id": random.randint(1000, 9999),
        "reading_value": round(random.uniform(20.0, 80.0), 2),
    }


class EventGenerator(ABC):
    """Strategy interface for producing event payloads."""

    @abstractmethod
    def next_event(self):
        """Return the next event payload."""


class RandomSensorEventGenerator(EventGenerator):
    """Default event generation strategy for synthetic sensor traffic."""

    def next_event(self):
        return generate_event()


class KafkaBatchProducer:
    """Template Method for batched Kafka event publishing."""

    def __init__(self, topic, event_generator):
        self.topic = topic
        self.event_generator = event_generator

    def run(self):
        logging.info(f"Starting Kafka Producer. Sending messages to topic: {self.topic}")
        create_kafka_topic(self.topic)

        batch = []
        message_count = 0

        try:
            while True:
                event = self.event_generator.next_event()
                batch.append(event)

                # Send records in groups to reduce request overhead and improve throughput.
                if len(batch) >= BATCH_SIZE:
                    self.publish_batch(batch)
                    message_count += len(batch)
                    batch.clear()

                logging.debug(f"Generated event: {event}")
                time.sleep(MESSAGE_FREQUENCY)

        except KeyboardInterrupt:
            logging.warning("Kafka Producer stopped manually.")
        except KafkaError as e:
            logging.error(f"Kafka producer error: {e}")
        finally:
            logging.info(
                f"Kafka Producer shutting down. Total messages sent: {message_count}"
            )
            producer.close()

    def publish_batch(self, batch):
        for msg in batch:
            producer.send(self.topic, msg)
        producer.flush()
        logging.info(
            f"Sent batch of {len(batch)} messages to Kafka topic: {self.topic}"
        )


if __name__ == "__main__":
    kafka_batch_producer = KafkaBatchProducer(
        topic=KAFKA_TOPIC,
        event_generator=RandomSensorEventGenerator(),
    )
    kafka_batch_producer.run()
