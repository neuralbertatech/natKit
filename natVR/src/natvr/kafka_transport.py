"""Kafka transport for natVR's producers/consumers.

All Kafka I/O for the migrated entry points (session_publish / replay /
emg_consumer / reconstruct_session) routes through the shared libnatkit Kafka C
ABI (``natvr.libnatkit_kafka``, backed by the single C++ transport). This is the
sole transport since the Phase 4 migration was validated end to end -- the
previous confluent-kafka fallback has been removed. A missing
``liblibnatkit-kafka.so`` (``LIBNATKIT_KAFKA_PATH`` or the build tree) raises at
construction rather than silently degrading.

Note: ``classifier.py`` and ``bridge/hand_state_bridge.py`` are the deferred
Phase 5 hand-state pipeline and still use confluent-kafka directly; they are not
routed through here, which is why natVR still depends on confluent-kafka.
"""

from __future__ import annotations

from natvr.libnatkit_kafka import (
    KafkaBroker,
    KafkaConsumer,
    KafkaProducer,
    OFFSET_BEGINNING,
    OFFSET_END,
)


def open_producer(bootstrap_servers: str) -> KafkaProducer:
    """A producer with a ``produce(topic, bytes)`` / ``flush()`` API."""
    return KafkaProducer(bootstrap_servers)


def open_stream_consumer(
    *,
    bootstrap_servers: str,
    group_id: str,
    topics: list[str],
    auto_offset_reset: str,
    direct_assign: bool,
    partition: int,
) -> tuple[KafkaConsumer, None]:
    """Open a consumer whose ``poll(timeout)`` yields Message-shaped objects
    (``value``/``topic``/``partition``/``offset``/``error``).

    Returns ``(consumer, None)`` -- the second element was the confluent
    ``KafkaError`` type used for a PARTITION_EOF check; the ABI transport has no
    such sentinel (its messages never carry an error), so it is always ``None``.
    ``group_id`` / ``direct_assign`` / ``partition`` are accepted for call-site
    compatibility but have no effect: the ABI has no consumer groups or committed
    offsets, so each consumer simply reads from ``start_offset``
    (earliest -> BEGINNING, latest -> END).
    """
    del group_id, direct_assign, partition
    start_offset = OFFSET_BEGINNING if auto_offset_reset == "earliest" else OFFSET_END
    return KafkaConsumer(bootstrap_servers, list(topics), start_offset), None


def list_broker_topics(*, bootstrap_servers: str) -> list[str]:
    """Sorted list of topic strings on the broker."""
    with KafkaBroker.from_bootstrap(bootstrap_servers) as broker:
        return sorted(broker.list_topics())
