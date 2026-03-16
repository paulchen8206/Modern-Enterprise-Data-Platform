"""Pattern smoke harness for pipeline refactors.

This script validates key design-pattern behavior with mocked adapters and
mocked third-party modules so no external services are required.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def install_fake_third_party_modules():
    class FakeKafkaConsumer:
        seeded_messages = []

        def __init__(self, *args, **kwargs):
            self._messages = list(FakeKafkaConsumer.seeded_messages)

        def __iter__(self):
            return iter(self._messages)

    class FakeKafkaProducer:
        def __init__(self, *args, **kwargs):
            self.sent = []
            self.flushed = False
            self.closed = False

        def send(self, topic, payload):
            self.sent.append((topic, payload))

        def flush(self):
            self.flushed = True

        def close(self):
            self.closed = True

    class FakeKafkaAdminClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_topics(self):
            return []

        def create_topics(self, topics):
            return topics

    class FakeNewTopic:
        def __init__(self, name, num_partitions, replication_factor):
            self.name = name
            self.num_partitions = num_partitions
            self.replication_factor = replication_factor

    class FakeKafkaError(Exception):
        pass

    kafka_module = types.ModuleType("kafka")
    setattr(kafka_module, "KafkaConsumer", FakeKafkaConsumer)
    setattr(kafka_module, "KafkaProducer", FakeKafkaProducer)
    setattr(kafka_module, "KafkaAdminClient", FakeKafkaAdminClient)

    kafka_admin_module = types.ModuleType("kafka.admin")
    setattr(kafka_admin_module, "NewTopic", FakeNewTopic)

    kafka_errors_module = types.ModuleType("kafka.errors")
    setattr(kafka_errors_module, "KafkaError", FakeKafkaError)

    requests_module = types.ModuleType("requests")
    setattr(requests_module, "ConnectionError", RuntimeError)
    setattr(requests_module, "RequestException", RuntimeError)
    setattr(requests_module, "get", lambda *args, **kwargs: FakeResponse(200))
    setattr(requests_module, "post", lambda *args, **kwargs: FakeResponse(201))

    pandas_module = types.ModuleType("pandas")
    setattr(
        pandas_module,
        "read_sql",
        lambda *args, **kwargs: types.SimpleNamespace(to_csv=lambda *a, **k: None),
    )

    sqlalchemy_module = types.ModuleType("sqlalchemy")
    setattr(sqlalchemy_module, "create_engine", lambda *args, **kwargs: object())

    psycopg2_module = types.ModuleType("psycopg2")

    sys.modules["kafka"] = kafka_module
    sys.modules["kafka.admin"] = kafka_admin_module
    sys.modules["kafka.errors"] = kafka_errors_module
    sys.modules["requests"] = requests_module
    sys.modules["pandas"] = pandas_module
    sys.modules["sqlalchemy"] = sqlalchemy_module
    sys.modules["psycopg2"] = psycopg2_module


class PatternSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_third_party_modules()
        cls.pipeline_patterns = load_module(
            "pipeline_patterns",
            "pipelines/storage/pipeline_patterns.py",
        )
        cls.kafka_producer_module = load_module(
            "kafka_producer_module",
            "pipelines/kafka/producer.py",
        )
        cls.atlas_module = load_module(
            "atlas_stub_module",
            "pipelines/governance/atlas_stub.py",
        )
        cls.monitoring_module = load_module(
            "monitoring_module",
            "pipelines/monitoring/monitoring.py",
        )
        cls.bi_module = load_module(
            "bi_dashboard_module",
            "pipelines/bi_dashboards/bi_dashboard.py",
        )

    def test_stream_processor_template_method(self):
        fake_consumer_cls = sys.modules["kafka"].KafkaConsumer
        fake_consumer_cls.seeded_messages = [
            types.SimpleNamespace(value={"device_id": 1, "reading_value": 12.5}),
            types.SimpleNamespace(value={"device_id": None, "reading_value": 4.0}),
            types.SimpleNamespace(value={"device_id": 2, "reading_value": 8.0}),
        ]

        processed = []

        class DemoProcessor(self.pipeline_patterns.StreamProcessor):
            def transform(self, payload):
                return {
                    "device_id": payload["device_id"],
                    "scaled": round(payload["reading_value"] * 10, 1),
                }

            def persist(self, transformed, raw_payload):
                processed.append((transformed, raw_payload))

        processor = DemoProcessor(
            topic="events",
            broker="kafka:9092",
            validator=self.pipeline_patterns.RequiredFieldsValidator(
                ["device_id", "reading_value"]
            ),
        )
        processor.run()

        self.assertEqual(len(processed), 2)
        self.assertEqual(processed[0][0]["scaled"], 125.0)
        self.assertEqual(processed[1][0]["device_id"], 2)

    def test_cached_feature_provider_adapter(self):
        class FakeRedisClient:
            def __init__(self):
                self.store = {}

            def get(self, key):
                return self.store.get(key)

            def setex(self, key, ttl_seconds, value):
                self.store[key] = value

        class FakeFeatureVector:
            def to_dict(self):
                return {
                    "device_features:avg_reading": [5.5],
                    "device_features:max_reading": [9.0],
                }

        class FakeFeatureStore:
            def get_online_features(self, features, entity_rows):
                return FakeFeatureVector()

        provider = self.pipeline_patterns.CachedFeastFeatureProvider(
            redis_client=FakeRedisClient(),
            feature_store=FakeFeatureStore(),
            ttl_seconds=60,
        )

        first = provider.get_features(1001)
        second = provider.get_features(1001)

        self.assertEqual(first["avg_reading"], 5.5)
        self.assertEqual(second["max_reading"], 9.0)

    def test_kafka_batch_producer_publish_batch(self):
        fake_generator = types.SimpleNamespace(next_event=lambda: {"x": 1})
        producer = self.kafka_producer_module.KafkaBatchProducer("events", fake_generator)

        local_fake_producer = sys.modules["kafka"].KafkaProducer()
        setattr(self.kafka_producer_module, "producer", local_fake_producer)
        producer.publish_batch([{"id": 1}, {"id": 2}])

        self.assertEqual(len(local_fake_producer.sent), 2)
        self.assertTrue(local_fake_producer.flushed)

    def test_lineage_registrar_facade(self):
        class FakeAtlasClient:
            def get(self, path):
                return FakeResponse(200, payload={"entities": [{"id": 1}]})

            def post(self, path, payload):
                return FakeResponse(201, payload={"ok": True})

        registrar = self.atlas_module.LineageRegistrar(FakeAtlasClient())
        self.assertTrue(registrar.dataset_exists("mysql.orders"))
        registrar.register_lineage("mysql.orders", "minio.raw-data.orders", {"job": "demo"})

    def test_monitoring_template_method(self):
        steps = []

        class DemoBootstrap(self.monitoring_module.MonitoringBootstrap):
            def start_prometheus(self):
                steps.append("prometheus")

            def start_grafana(self):
                steps.append("grafana")

            def wait_for_grafana(self):
                steps.append("wait")
                return True

            def configure_datasource(self):
                steps.append("datasource")

            def import_dashboards(self):
                steps.append("dashboards")

        DemoBootstrap().run()
        self.assertEqual(
            steps,
            ["prometheus", "grafana", "wait", "datasource", "dashboards"],
        )

    def test_bi_uploader_orchestrator(self):
        calls = []

        class FakeUploader:
            def __init__(self, label):
                self.label = label

            def name(self):
                return self.label

            def upload(self, csv_path):
                calls.append((self.label, csv_path))

        self.bi_module.run_uploads(
            [FakeUploader("A"), FakeUploader("B")],
            "bi_data/orders_transformed.csv",
        )

        self.assertEqual(
            calls,
            [
                ("A", "bi_data/orders_transformed.csv"),
                ("B", "bi_data/orders_transformed.csv"),
            ],
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PatternSmokeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
