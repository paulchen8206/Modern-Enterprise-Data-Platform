"""Reusable design-pattern helpers for storage streaming pipelines.

Patterns used:
- Template Method: `StreamProcessor.run()` defines the consume/validate/transform/persist flow.
- Strategy: validators are pluggable callables.
- Adapter: `CachedFeastFeatureProvider` adapts Feast + Redis cache into a simple feature API.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable

from kafka import KafkaConsumer


class RequiredFieldsValidator:
    """Validation strategy that enforces required payload keys."""

    def __init__(self, required_fields: list[str]):
        self.required_fields = required_fields

    def __call__(self, payload: dict[str, Any]) -> bool:
        return all(payload.get(field) is not None for field in self.required_fields)


class CachedFeastFeatureProvider:
    """Adapter that exposes Feast online features with Redis cache-aside semantics."""

    def __init__(self, redis_client: Any, feature_store: Any, ttl_seconds: int = 3600):
        self.redis_client = redis_client
        self.feature_store = feature_store
        self.ttl_seconds = ttl_seconds

    def get_features(self, device_id: int) -> dict[str, Any]:
        cache_key = f"features:{device_id}"
        cached_features = self.redis_client.get(cache_key)
        if cached_features:
            return json.loads(cached_features)

        feature_vector = self.feature_store.get_online_features(
            features=["device_features:avg_reading", "device_features:max_reading"],
            entity_rows=[{"device_id": device_id}],
        ).to_dict()

        features = {
            "avg_reading": feature_vector["device_features:avg_reading"][0],
            "max_reading": feature_vector["device_features:max_reading"][0],
        }

        self.redis_client.setex(cache_key, self.ttl_seconds, json.dumps(features))
        return features


class StreamProcessor(ABC):
    """Template Method base class for Kafka streaming processors."""

    def __init__(
        self,
        *,
        topic: str,
        broker: str,
        validator: Callable[[dict[str, Any]], bool] | None = None,
        value_deserializer: Callable[[bytes], Any] | None = None,
    ):
        self.topic = topic
        self.broker = broker
        self.validator = validator
        self.value_deserializer = value_deserializer or (
            lambda value: json.loads(value.decode("utf-8"))
        )

    def run(self) -> None:
        logging.info("Starting stream processor for topic: %s", self.topic)
        consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=[self.broker],
            value_deserializer=self.value_deserializer,
        )

        for message in consumer:
            try:
                payload = message.value
                if not isinstance(payload, dict):
                    logging.debug("Skipping non-dict message payload")
                    continue

                if self.validator and not self.validator(payload):
                    logging.debug("Skipping invalid payload: %s", payload)
                    continue

                transformed = self.transform(payload)
                if transformed is None:
                    continue

                self.persist(transformed, payload)
                self.on_success(transformed)
            except Exception as exc:
                self.on_error(exc)

    @abstractmethod
    def transform(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Transform raw payload into the persisted message shape."""

    @abstractmethod
    def persist(self, transformed: dict[str, Any], raw_payload: dict[str, Any]) -> None:
        """Persist transformed message using target sink(s)."""

    def on_success(self, transformed: dict[str, Any]) -> None:
        logging.info("Processed payload for device_id=%s", transformed.get("device_id"))

    def on_error(self, exc: Exception) -> None:
        logging.error("Stream processing error: %s", exc)


def with_default_timestamp(payload: dict[str, Any], key: str = "timestamp") -> int:
    """Return payload timestamp or current epoch seconds."""
    return int(payload.get(key, int(datetime.utcnow().timestamp())))
