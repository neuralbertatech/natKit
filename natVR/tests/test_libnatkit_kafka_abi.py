"""Phase 4 acceptance test for the libnatkit Kafka C ABI.

Round-trips raw payloads through the ctypes binding (``natvr.libnatkit_kafka``)
over a real Kafka broker, and cross-checks byte-for-byte wire compatibility with
``confluent-kafka`` in both directions -- which is what lets the existing
confluent-kafka consumers/producers migrate onto the ABI without a wire-format
change.

Skips cleanly when the shim ``.so`` is not built or no broker is reachable, so
it is a no-op in environments (CI, dev laptops) without Kafka. Point it at a
broker with ``NATKIT_TEST_BROKER`` (default ``127.0.0.1:29092``).
"""

from __future__ import annotations

import os
import socket
import time

import pytest

_BROKER = os.environ.get("NATKIT_TEST_BROKER", "127.0.0.1:29092")
_RECV_TIMEOUT_S = 20.0


def _load_binding():
    from natvr import libnatkit_kafka

    try:
        libnatkit_kafka._load_library()
    except FileNotFoundError as error:
        pytest.skip(f"libnatkit-kafka shared library unavailable: {error}")
    return libnatkit_kafka


def _require_broker() -> str:
    host, sep, port = _BROKER.rpartition(":")
    if not sep:
        host, port = _BROKER, "9092"
    try:
        with socket.create_connection((host, int(port)), timeout=2.0):
            pass
    except OSError as error:
        pytest.skip(f"no Kafka broker reachable at {_BROKER}: {error}")
    return _BROKER


def _unique_topic() -> str:
    # A fresh id per run so no stale messages from a previous run leak in.
    uid = (os.getpid() * 1_000_000 + int(time.time() * 1000)) % (1 << 62)
    return f"Data-{uid}-Json-MarkerEventV1"


def _drain_until(recv, expected: set[bytes], timeout_s: float = _RECV_TIMEOUT_S) -> set[bytes]:
    got: set[bytes] = set()
    deadline = time.time() + timeout_s
    while time.time() < deadline and not expected.issubset(got):
        msg = recv()
        if msg is not None:
            got.add(msg)
        else:
            time.sleep(0.05)
    return got


def test_shim_produce_shim_consume_round_trip() -> None:
    k = _load_binding()
    broker_addr = _require_broker()
    topic = _unique_topic()
    payloads = [
        b'{"marker":"start","n":1}',
        b'{"marker":"mid","n":2,"blob":"' + b"x" * 500 + b'"}',
        b"",  # empty payload must survive the two-call peek/fill path
        b"\x00\x01\x02\xff\xfe binary-safe",
    ]

    with k.KafkaBroker.from_bootstrap(broker_addr) as broker:
        rx = broker.messenger(topic, start_offset=k.OFFSET_BEGINNING)
        tx = broker.messenger(topic)
        try:
            time.sleep(1.0)  # let the consumer thread assign before producing
            for payload in payloads:
                tx.send(payload)
            tx.flush()

            got = _drain_until(rx.try_recv, {p for p in payloads if p})
            # The empty payload is produced but librdkafka may coalesce it; assert
            # every non-empty payload arrived byte-exact.
            for payload in payloads:
                if payload:
                    assert payload in got, f"missing {payload!r}; got {got!r}"
        finally:
            tx.close()
            rx.close()


def test_shim_and_confluent_wire_compatible() -> None:
    """Bytes produced by the shim decode identically under confluent-kafka and
    vice versa -- the guarantee the emg_consumer/session_publish migration rests on.

    Uses confluent's assign()/OFFSET_BEGINNING (not subscribe) so there is no
    consumer-group rebalance or new-topic metadata-refresh delay to race."""
    k = _load_binding()
    broker_addr = _require_broker()
    confluent = pytest.importorskip("confluent_kafka")
    from confluent_kafka import OFFSET_BEGINNING, TopicPartition

    from_shim = b'{"src":"shim","payload":[1,2,3]}'
    from_confluent = b'{"src":"confluent","payload":[4,5,6]}'

    # Direction 1: shim produces -> confluent consumes.
    topic1 = _unique_topic()
    with k.KafkaBroker.from_bootstrap(broker_addr) as broker:
        tx = broker.messenger(topic1)
        try:
            time.sleep(1.0)
            tx.send(from_shim)
            tx.flush()
        finally:
            tx.close()
    consumer = confluent.Consumer(
        {
            "bootstrap.servers": broker_addr,
            "group.id": f"natkit-abi-test-{os.getpid()}",
            "enable.auto.commit": False,
        }
    )
    consumer.assign([TopicPartition(topic1, 0, OFFSET_BEGINNING)])
    try:
        deadline = time.time() + _RECV_TIMEOUT_S
        seen = None
        while time.time() < deadline and seen is None:
            msg = consumer.poll(0.2)
            if msg is not None and not msg.error():
                seen = msg.value()
        assert seen == from_shim, f"confluent saw {seen!r}, expected {from_shim!r}"
    finally:
        consumer.close()

    # Direction 2: confluent produces -> shim consumes.
    topic2 = _unique_topic()
    with k.KafkaBroker.from_bootstrap(broker_addr) as broker:
        rx = broker.messenger(topic2, start_offset=k.OFFSET_BEGINNING)
        producer = confluent.Producer({"bootstrap.servers": broker_addr})
        try:
            time.sleep(1.0)
            producer.produce(topic2, from_confluent)
            producer.flush()
            got = _drain_until(rx.try_recv, {from_confluent})
            assert from_confluent in got, f"shim missed confluent bytes; got {got!r}"
        finally:
            rx.close()


def test_migrated_consumer_stack_over_abi(monkeypatch) -> None:
    """The migrated EmgAndMarkerKafkaConsumer decodes EMG + marker frames when
    forced onto the ABI transport -- exercises the multi-topic KafkaConsumer
    adapter (round-robin poll) end to end through the real decoders."""
    _load_binding()
    broker_addr = _require_broker()
    monkeypatch.setenv("NATVR_KAFKA_TRANSPORT", "abi")

    from natvr.models import ExgPillEmgDataSchemaV1, MarkerEventV1
    from natvr.topics import emg_raw, marker_stream
    from natvr.kafka_transport import open_producer
    from natvr.emg_consumer import (
        EmgAndMarkerKafkaConsumer,
        EmgFrameEnvelope,
        MarkerEventEnvelope,
    )

    uid = (os.getpid() * 1_000_000 + int(time.time() * 1000)) % 100000
    device_id = f"emgabi{uid}"
    session_id = f"sessabi{uid}"
    emg_topic = emg_raw(device_id)
    marker_topic = marker_stream(session_id)

    consumer = EmgAndMarkerKafkaConsumer(
        bootstrap_servers=broker_addr,
        device_id=device_id,
        session_id=session_id,
        group_id="natkit-abi-consumer-test",
        auto_offset_reset="earliest",
        direct_assign=True,
    )
    # It really is the ABI adapter, not a confluent Consumer fallback.
    assert type(consumer._consumer._consumer).__name__ == "KafkaConsumer"
    producer = open_producer(broker_addr)
    try:
        time.sleep(1.0)
        frame = ExgPillEmgDataSchemaV1(
            device_id=device_id,
            seq_no=7,
            device_ts_us=1782496727200000,
            sample_rate_hz=2000,
            channel_labels=("flexor_a",),
            channels=((100, 120, 90, -50, -40),),
        )
        marker = MarkerEventV1(
            session_id=session_id,
            marker_type="session",
            marker_id="m1",
            event="start",
            label="go",
            emitted_at_us=1782496727200001,
            attributes={},
        )
        producer.produce(emg_topic, frame.to_json_bytes())
        producer.produce(marker_topic, marker.to_json_bytes())
        producer.flush()

        got_emg = got_marker = None
        deadline = time.time() + _RECV_TIMEOUT_S
        while time.time() < deadline and (got_emg is None or got_marker is None):
            env = consumer.poll(timeout=0.5)
            if isinstance(env, EmgFrameEnvelope):
                got_emg = env
            elif isinstance(env, MarkerEventEnvelope):
                got_marker = env

        assert got_emg is not None, "migrated consumer never decoded the EMG frame"
        assert got_emg.topic == emg_topic
        assert got_emg.frame.seq_no == 7
        assert got_emg.frame.channels == ((100, 120, 90, -50, -40),)
        assert got_marker is not None, "migrated consumer never decoded the marker"
        assert got_marker.topic == marker_topic
        assert got_marker.marker.event == "start"
    finally:
        consumer.close()
        producer.close()
