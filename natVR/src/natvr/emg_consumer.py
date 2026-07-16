from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterator

from natvr.kafka_transport import open_stream_consumer
from natvr.models import (
    ExgPillEmgDataSchemaV1,
    MarkerEventV1,
    SessionMetadataRecord,
)
from natvr.topics import emg_raw, marker_stream, meta_session


@dataclass(frozen=True, slots=True)
class EmgFrameEnvelope:
    frame: ExgPillEmgDataSchemaV1
    topic: str
    partition: int | None = None
    offset: int | None = None
    broker_received_at_us: int | None = None
    sequence_gap: int = 0


@dataclass(frozen=True, slots=True)
class MarkerEventEnvelope:
    marker: MarkerEventV1
    topic: str
    partition: int | None = None
    offset: int | None = None
    broker_received_at_us: int | None = None


@dataclass(frozen=True, slots=True)
class SessionMetadataEnvelope:
    record: SessionMetadataRecord
    topic: str
    partition: int | None = None
    offset: int | None = None
    broker_received_at_us: int | None = None


StreamEnvelope = EmgFrameEnvelope | MarkerEventEnvelope | SessionMetadataEnvelope


class EmgGapTracker:
    def __init__(self) -> None:
        self._last_seq_by_device: dict[str, int] = {}

    def observe(self, frame: ExgPillEmgDataSchemaV1) -> int:
        last_seq = self._last_seq_by_device.get(frame.device_id)
        self._last_seq_by_device[frame.device_id] = frame.seq_no
        if last_seq is None:
            return 0
        if frame.seq_no <= last_seq:
            return 0
        return max(0, frame.seq_no - last_seq - 1)


def decode_emg_message(
    payload: bytes,
    *,
    topic: str,
    partition: int | None = None,
    offset: int | None = None,
    broker_received_at_us: int | None = None,
    gap_tracker: EmgGapTracker | None = None,
) -> EmgFrameEnvelope:
    frame = ExgPillEmgDataSchemaV1.from_json_bytes(payload)
    sequence_gap = gap_tracker.observe(frame) if gap_tracker else 0
    return EmgFrameEnvelope(
        frame=frame,
        topic=topic,
        partition=partition,
        offset=offset,
        broker_received_at_us=broker_received_at_us,
        sequence_gap=sequence_gap,
    )


def decode_marker_message(
    payload: bytes,
    *,
    topic: str,
    partition: int | None = None,
    offset: int | None = None,
    broker_received_at_us: int | None = None,
    gap_tracker: EmgGapTracker | None = None,
) -> MarkerEventEnvelope:
    marker = MarkerEventV1.from_json_bytes(payload)
    return MarkerEventEnvelope(
        marker=marker,
        topic=topic,
        partition=partition,
        offset=offset,
        broker_received_at_us=broker_received_at_us,
    )


def decode_session_metadata_message(
    payload: bytes,
    *,
    topic: str,
    partition: int | None = None,
    offset: int | None = None,
    broker_received_at_us: int | None = None,
    gap_tracker: EmgGapTracker | None = None,
) -> SessionMetadataEnvelope:
    del gap_tracker
    record = SessionMetadataRecord.from_meta_record_json_bytes(payload)
    return SessionMetadataEnvelope(
        record=record,
        topic=topic,
        partition=partition,
        offset=offset,
        broker_received_at_us=broker_received_at_us,
    )


class StreamKafkaConsumer:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        group_id: str,
        topics: list[str],
        decoders: dict[str, Callable[..., StreamEnvelope]],
        auto_offset_reset: str = "latest",
        direct_assign: bool = False,
        partition: int = 0,
    ) -> None:
        if not topics:
            raise ValueError("topics must not be empty")
        self._topics = list(dict.fromkeys(topics))
        if not decoders:
            raise ValueError("decoders must not be empty")
        missing_topics = [topic for topic in self._topics if topic not in decoders]
        if missing_topics:
            raise ValueError(
                f"missing decoders for topics: {', '.join(sorted(missing_topics))}"
            )
        self._direct_assign = direct_assign
        self._decoders = dict(decoders)
        self._gap_tracker = EmgGapTracker()
        # Kafka I/O goes through the shared libnatkit Kafka C ABI. kafka_error is
        # always None for the ABI (its messages never carry an error), so the
        # PARTITION_EOF branch in poll() is inert.
        self._consumer, self._kafka_error = open_stream_consumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            topics=self._topics,
            auto_offset_reset=auto_offset_reset,
            direct_assign=direct_assign,
            partition=partition,
        )

    @property
    def topics(self) -> tuple[str, ...]:
        return tuple(self._topics)

    def poll(self, timeout: float = 1.0) -> StreamEnvelope | None:
        message = self._consumer.poll(timeout)
        if message is None:
            return None
        if message.error():
            if message.error().code() == self._kafka_error._PARTITION_EOF:
                return None
            raise RuntimeError(f"kafka consume error: {message.error()}")
        received_at = datetime.now(tz=timezone.utc)
        decoder = self._decoders.get(message.topic())
        if decoder is None:
            raise RuntimeError(f"no decoder configured for topic {message.topic()!r}")
        return decoder(
            message.value(),
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            broker_received_at_us=int(received_at.timestamp() * 1_000_000),
            gap_tracker=self._gap_tracker,
        )

    def iter_messages(self, timeout: float = 1.0) -> Iterator[StreamEnvelope]:
        while True:
            message = self.poll(timeout=timeout)
            if message is not None:
                yield message

    def close(self) -> None:
        self._consumer.close()


class EmgKafkaConsumer:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        device_id: str,
        group_id: str,
        topic: str | None = None,
        auto_offset_reset: str = "latest",
        direct_assign: bool = False,
        partition: int = 0,
    ) -> None:
        self._topic = topic or emg_raw(device_id)
        self._consumer = StreamKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            topics=[self._topic],
            decoders={self._topic: decode_emg_message},
            auto_offset_reset=auto_offset_reset,
            direct_assign=direct_assign,
            partition=partition,
        )

    @property
    def topic(self) -> str:
        return self._topic

    def poll(self, timeout: float = 1.0) -> EmgFrameEnvelope | None:
        envelope = self._consumer.poll(timeout=timeout)
        if envelope is None:
            return None
        assert isinstance(envelope, EmgFrameEnvelope)
        return envelope

    def iter_frames(self, timeout: float = 1.0) -> Iterator[EmgFrameEnvelope]:
        while True:
            envelope = self.poll(timeout=timeout)
            if envelope is not None:
                yield envelope

    def close(self) -> None:
        self._consumer.close()


class EmgAndMarkerKafkaConsumer:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        device_id: str,
        session_id: str,
        group_id: str,
        emg_topic: str | None = None,
        marker_topic: str | None = None,
        auto_offset_reset: str = "latest",
        direct_assign: bool = False,
        partition: int = 0,
    ) -> None:
        self._emg_topic = emg_topic or emg_raw(device_id)
        self._marker_topic = marker_topic or marker_stream(session_id)
        if self._emg_topic == self._marker_topic:
            raise ValueError("emg_topic and marker_topic must be different topics")
        self._consumer = StreamKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            topics=[self._emg_topic, self._marker_topic],
            decoders={
                self._emg_topic: decode_emg_message,
                self._marker_topic: decode_marker_message,
            },
            auto_offset_reset=auto_offset_reset,
            direct_assign=direct_assign,
            partition=partition,
        )

    @property
    def emg_topic(self) -> str:
        return self._emg_topic

    @property
    def marker_topic(self) -> str:
        return self._marker_topic

    @property
    def topics(self) -> tuple[str, str]:
        return (self._emg_topic, self._marker_topic)

    def poll(self, timeout: float = 1.0) -> StreamEnvelope | None:
        return self._consumer.poll(timeout=timeout)

    def iter_messages(self, timeout: float = 1.0) -> Iterator[StreamEnvelope]:
        return self._consumer.iter_messages(timeout=timeout)

    def close(self) -> None:
        self._consumer.close()


class SessionMetadataKafkaConsumer:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        session_id: str,
        group_id: str,
        topic: str | None = None,
        auto_offset_reset: str = "latest",
        direct_assign: bool = False,
        partition: int = 0,
    ) -> None:
        self._topic = topic or meta_session(session_id)
        self._consumer = StreamKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            topics=[self._topic],
            decoders={self._topic: decode_session_metadata_message},
            auto_offset_reset=auto_offset_reset,
            direct_assign=direct_assign,
            partition=partition,
        )

    @property
    def topic(self) -> str:
        return self._topic

    def poll(self, timeout: float = 1.0) -> SessionMetadataEnvelope | None:
        envelope = self._consumer.poll(timeout=timeout)
        if envelope is None:
            return None
        assert isinstance(envelope, SessionMetadataEnvelope)
        return envelope

    def close(self) -> None:
        self._consumer.close()
