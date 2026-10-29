import json

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

from marketpulse.config import BROKERS, CURATED, DLQ, RAW, SYMBOLS
from marketpulse.db import connection, query


def topics() -> None:
    admin = KafkaAdminClient(bootstrap_servers=BROKERS, client_id="marketpulse-admin")
    try:
        for name in [RAW, CURATED, DLQ]:
            try:
                admin.create_topics(
                    [NewTopic(name, 3, 1, topic_configs={"retention.ms": "604800000"})]
                )
            except TopicAlreadyExistsError:
                pass
    finally:
        admin.close()


def producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=BROKERS,
        acks="all",
        retries=5,
        max_in_flight_requests_per_connection=1,
        key_serializer=lambda key: key.encode(),
        value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode(),
    )


def flush_outbox(run_id: str) -> None:
    client = producer()
    try:
        for row in query(
            "SELECT * FROM ops.outbox WHERE run_id=%s AND sent_at IS NULL ORDER BY payload->'event'->>'event_time_utc',event_id",
            (run_id,),
        ):
            payload = row["payload"]
            symbol = payload.get("event", {}).get("symbol", SYMBOLS[0])
            client.send(
                row["topic"], key=symbol, partition=SYMBOLS.index(symbol), value=payload
            ).get(timeout=30)
            with connection() as conn:
                conn.execute(
                    "UPDATE ops.outbox SET sent_at=now() WHERE run_id=%s AND event_id=%s AND topic=%s",
                    (run_id, row["event_id"], row["topic"]),
                )
    finally:
        client.flush(timeout=30)
        client.close()
