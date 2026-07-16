"""ctypes binding for the libnatkit Kafka C ABI (liblibnatkit-kafka.so).

This is the Phase 4 companion to :mod:`natvr.libnatkit_core`. Where
``libnatkit_core`` binds the lean, Kafka-free ``liblibnatkit-core.so``, this
module binds the separate ``liblibnatkit-kafka.so`` that wraps the
librdkafka-backed C++ transport (``nat::kafka::BrokerManager`` /
``nat::core::TopicMessenger``) behind the ``nat_kafka_v1_*`` opaque-handle ABI
declared in ``libnatkit/libnatkit/include/libnatkit-kafka-abi.h``.

It is deliberately independent of ``libnatkit_core``'s discovery: the two shared
libraries live in different build trees and are located via different env vars
(``LIBNATKIT_KAFKA_PATH`` vs ``LIBNATKIT_CORE_PATH``), mirroring the
``libnatkit_stitch`` precedent.

The Pythonic surface is two context-managed handles:

    with KafkaBroker.from_bootstrap("127.0.0.1:29092") as broker:
        with broker.messenger("Data-123-Json-MarkerEventV1") as tx:
            tx.send(payload_bytes)
            tx.flush()
        with broker.messenger(topic, start_offset=OFFSET_BEGINNING) as rx:
            while True:
                msg = rx.try_recv()
                if msg is not None:
                    handle(msg)
"""

from __future__ import annotations

import ctypes
from ctypes.util import find_library
import os
import time
from pathlib import Path

# Status codes from libnatkit-core-abi.h (shared registry).
NAT_OK = 0
NAT_ERR_NULL_ARGUMENT = 1
NAT_ERR_INVALID_ARGUMENT = 2
NAT_ERR_BUFFER_TOO_SMALL = 3
NAT_ERR_DECODE_FAILED = 4
NAT_ERR_ENCODE_FAILED = 5
NAT_ERR_ALLOCATION_FAILED = 6
NAT_ERR_INTERNAL = 7

_STATUS_NAMES = {
    NAT_OK: "NAT_OK",
    NAT_ERR_NULL_ARGUMENT: "NAT_ERR_NULL_ARGUMENT",
    NAT_ERR_INVALID_ARGUMENT: "NAT_ERR_INVALID_ARGUMENT",
    NAT_ERR_BUFFER_TOO_SMALL: "NAT_ERR_BUFFER_TOO_SMALL",
    NAT_ERR_DECODE_FAILED: "NAT_ERR_DECODE_FAILED",
    NAT_ERR_ENCODE_FAILED: "NAT_ERR_ENCODE_FAILED",
    NAT_ERR_ALLOCATION_FAILED: "NAT_ERR_ALLOCATION_FAILED",
    NAT_ERR_INTERNAL: "NAT_ERR_INTERNAL",
}

# Start-offset sentinels (mirror NAT_KAFKA_OFFSET_* in libnatkit-kafka-abi.h).
OFFSET_BEGINNING = -2
OFFSET_END = -1


class LibnatkitKafkaError(RuntimeError):
    """A nat_kafka_v1_* function returned a nonzero status code."""

    def __init__(self, func: str, status: int) -> None:
        name = _STATUS_NAMES.get(status, f"status {status}")
        super().__init__(f"{func} failed: {name}")
        self.status = status


def _check(func: str, status: int) -> None:
    if status != NAT_OK:
        raise LibnatkitKafkaError(func, status)


_UNSET = object()
_LIB_HANDLE: ctypes.CDLL | object = _UNSET


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _candidate_library_paths() -> list[str]:
    names = (
        "liblibnatkit-kafka.so",
        "libnatkit-kafka.so",
        "liblibnatkit-kafka.dylib",
        "libnatkit-kafka.dylib",
        "liblibnatkit-kafka.dll",
        "libnatkit-kafka.dll",
    )
    candidates: list[str] = []

    env_path = os.environ.get("LIBNATKIT_KAFKA_PATH")
    if env_path:
        candidates.append(env_path)

    # The kafka shim is built inside the full libnatkit tree, not lib/libnatkit-core.
    build_root = _repo_root() / "libnatkit" / "build" / "libnatkit" / "core" / "kafka" / "src"
    for name in names:
        candidates.extend(
            [
                str(build_root / name),
                str(build_root / "Debug" / name),
                str(build_root / "Release" / name),
                str(build_root / "RelWithDebInfo" / name),
            ]
        )

    system_name = find_library("natkit-kafka")
    if system_name:
        candidates.append(system_name)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def find_libnatkit_kafka() -> str | None:
    for candidate in _candidate_library_paths():
        if Path(candidate).exists() or os.path.sep not in candidate:
            return candidate
    return None


def _load_library() -> ctypes.CDLL:
    global _LIB_HANDLE
    if _LIB_HANDLE is not _UNSET:
        return _LIB_HANDLE  # type: ignore[return-value]
    path = find_libnatkit_kafka()
    if path is None:
        raise FileNotFoundError(
            "liblibnatkit-kafka shared library not found. Set LIBNATKIT_KAFKA_PATH "
            "or build the kafka ABI target: "
            "cmake -S libnatkit -B libnatkit/build && "
            "cmake --build libnatkit/build --target libnatkit-kafka"
        )
    handle = ctypes.CDLL(str(path))

    handle.nat_kafka_v1_broker_create.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    handle.nat_kafka_v1_broker_create.restype = ctypes.c_int

    handle.nat_kafka_v1_broker_destroy.argtypes = [ctypes.c_void_p]
    handle.nat_kafka_v1_broker_destroy.restype = None

    handle.nat_kafka_v1_broker_list_topics.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    handle.nat_kafka_v1_broker_list_topics.restype = ctypes.c_int

    handle.nat_kafka_v1_messenger_create.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int64,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    handle.nat_kafka_v1_messenger_create.restype = ctypes.c_int

    handle.nat_kafka_v1_messenger_destroy.argtypes = [ctypes.c_void_p]
    handle.nat_kafka_v1_messenger_destroy.restype = None

    handle.nat_kafka_v1_messenger_send.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    handle.nat_kafka_v1_messenger_send.restype = ctypes.c_int

    handle.nat_kafka_v1_messenger_flush.argtypes = [ctypes.c_void_p]
    handle.nat_kafka_v1_messenger_flush.restype = ctypes.c_int

    handle.nat_kafka_v1_messenger_try_recv.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_int),
    ]
    handle.nat_kafka_v1_messenger_try_recv.restype = ctypes.c_int

    _LIB_HANDLE = handle
    return handle


def split_bootstrap(bootstrap: str) -> tuple[str, str]:
    """Split a "host:port" bootstrap string into (host, port).

    The C ABI takes host and port separately (matching createBrokerManager). A
    bootstrap without a port defaults to Kafka's 9092.
    """
    if ":" in bootstrap:
        host, _, port = bootstrap.rpartition(":")
        return host, port
    return bootstrap, "9092"


class KafkaMessenger:
    """A per-topic send+receive channel backed by a C++ TopicMessenger.

    Not safe to use from multiple threads concurrently on the same instance --
    give each thread its own messenger, exactly as with a confluent-kafka
    Consumer.
    """

    def __init__(self, lib: ctypes.CDLL, handle: ctypes.c_void_p) -> None:
        self._lib = lib
        self._handle: ctypes.c_void_p | None = handle

    def send(self, payload: bytes) -> None:
        if self._handle is None:
            raise ValueError("messenger is closed")
        _check(
            "nat_kafka_v1_messenger_send",
            self._lib.nat_kafka_v1_messenger_send(
                self._handle, payload, len(payload)
            ),
        )

    def flush(self) -> None:
        """Block until queued sends have been delivered to the broker."""
        if self._handle is None:
            raise ValueError("messenger is closed")
        _check(
            "nat_kafka_v1_messenger_flush",
            self._lib.nat_kafka_v1_messenger_flush(self._handle),
        )

    def try_recv(self) -> bytes | None:
        """Return the next raw message, or None if none is currently available."""
        if self._handle is None:
            raise ValueError("messenger is closed")
        size = ctypes.c_size_t(0)
        has_message = ctypes.c_int(0)
        # Sizing call (NULL buffer): peeks the next message without consuming it.
        _check(
            "nat_kafka_v1_messenger_try_recv",
            self._lib.nat_kafka_v1_messenger_try_recv(
                self._handle, None, ctypes.byref(size), ctypes.byref(has_message)
            ),
        )
        if has_message.value == 0:
            return None
        buffer = ctypes.create_string_buffer(size.value) if size.value else ctypes.create_string_buffer(1)
        # Fill call: copies and consumes the peeked message.
        _check(
            "nat_kafka_v1_messenger_try_recv",
            self._lib.nat_kafka_v1_messenger_try_recv(
                self._handle, buffer, ctypes.byref(size), ctypes.byref(has_message)
            ),
        )
        return buffer.raw[: size.value]

    def close(self) -> None:
        if self._handle is not None:
            self._lib.nat_kafka_v1_messenger_destroy(self._handle)
            self._handle = None

    def __enter__(self) -> "KafkaMessenger":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()


class KafkaBroker:
    """A connection to a Kafka broker, wrapping nat::kafka::BrokerManager."""

    def __init__(self, host: str, port: str | int) -> None:
        self._lib = _load_library()
        handle = ctypes.c_void_p()
        _check(
            "nat_kafka_v1_broker_create",
            self._lib.nat_kafka_v1_broker_create(
                str(host).encode("utf-8"),
                str(port).encode("utf-8"),
                ctypes.byref(handle),
            ),
        )
        self._handle: ctypes.c_void_p | None = handle

    @classmethod
    def from_bootstrap(cls, bootstrap: str) -> "KafkaBroker":
        host, port = split_bootstrap(bootstrap)
        return cls(host, port)

    def list_topics(self, include_hidden: bool = False) -> list[str]:
        if self._handle is None:
            raise ValueError("broker is closed")
        size = ctypes.c_size_t(0)
        flag = 1 if include_hidden else 0
        _check(
            "nat_kafka_v1_broker_list_topics",
            self._lib.nat_kafka_v1_broker_list_topics(
                self._handle, flag, None, ctypes.byref(size)
            ),
        )
        buffer = ctypes.create_string_buffer(size.value)
        _check(
            "nat_kafka_v1_broker_list_topics",
            self._lib.nat_kafka_v1_broker_list_topics(
                self._handle, flag, buffer, ctypes.byref(size)
            ),
        )
        text = buffer.value.decode("utf-8")
        return [line for line in text.split("\n") if line]

    def messenger(self, topic: str, start_offset: int = OFFSET_END) -> KafkaMessenger:
        if self._handle is None:
            raise ValueError("broker is closed")
        handle = ctypes.c_void_p()
        _check(
            "nat_kafka_v1_messenger_create",
            self._lib.nat_kafka_v1_messenger_create(
                self._handle,
                topic.encode("utf-8"),
                ctypes.c_int64(start_offset),
                ctypes.byref(handle),
            ),
        )
        return KafkaMessenger(self._lib, handle)

    def close(self) -> None:
        if self._handle is not None:
            self._lib.nat_kafka_v1_broker_destroy(self._handle)
            self._handle = None

    def __enter__(self) -> "KafkaBroker":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()


class KafkaProducer:
    """A confluent-kafka-``Producer``-shaped adapter over the ABI.

    Exposes ``produce(topic, payload)`` and ``flush()`` so code written against
    ``confluent_kafka.Producer`` (e.g. session_publish, replay) can swap to the
    shared C++ transport with a one-line change. Lazily opens one messenger per
    topic and caches it.
    """

    def __init__(self, bootstrap: str) -> None:
        self._broker = KafkaBroker.from_bootstrap(bootstrap)
        self._messengers: dict[str, KafkaMessenger] = {}

    def produce(self, topic: str, payload: bytes) -> None:
        messenger = self._messengers.get(topic)
        if messenger is None:
            messenger = self._broker.messenger(topic)
            self._messengers[topic] = messenger
        messenger.send(payload)

    def poll(self, timeout: float = 0) -> int:
        """No-op for API compatibility with confluent_kafka.Producer.poll().

        Delivery is serviced on the C++ background thread, so there is nothing to
        pump here. Returns 0 (messages served) to match the confluent signature.
        """
        del timeout
        return 0

    def flush(self) -> None:
        for messenger in self._messengers.values():
            messenger.flush()

    def close(self) -> None:
        for messenger in self._messengers.values():
            messenger.close()
        self._messengers.clear()
        self._broker.close()

    def __enter__(self) -> "KafkaProducer":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()


class _ConsumerMessage:
    """confluent-kafka-``Message``-shaped view of one received payload.

    Exposes the accessors ``StreamKafkaConsumer`` uses (``value``/``topic``/
    ``partition``/``offset``/``error``). ``offset()`` is a synthetic per-topic
    counter, not the real Kafka offset -- the raw transport ABI does not surface
    broker offsets; consumers rely on in-payload ordering (EMG ``seq_no``, marker
    ``emitted_at_us``), not this value. ``error()`` is always None.
    """

    __slots__ = ("_value", "_topic", "_offset")

    def __init__(self, value: bytes, topic: str, offset: int) -> None:
        self._value = value
        self._topic = topic
        self._offset = offset

    def value(self) -> bytes:
        return self._value

    def topic(self) -> str:
        return self._topic

    def partition(self) -> int:
        return 0

    def offset(self) -> int:
        return self._offset

    def error(self) -> None:
        return None


class KafkaConsumer:
    """A confluent-kafka-``Consumer``-shaped adapter over per-topic messengers.

    Opens one messenger per topic (all at the same ``start_offset``) and
    round-robins a blocking ``poll(timeout)`` across them, so code written
    against ``confluent_kafka.Consumer.poll`` can swap to the shared C++
    transport. Note the ABI has no consumer groups or committed offsets: every
    consumer reads independently from ``start_offset`` (``group_id`` is ignored),
    which suits natVR's one-consumer-per-stream live/historical reads.
    """

    def __init__(
        self, bootstrap: str, topics: list[str], start_offset: int = OFFSET_END
    ) -> None:
        self._broker = KafkaBroker.from_bootstrap(bootstrap)
        self._order = list(dict.fromkeys(topics))
        self._messengers = {
            topic: self._broker.messenger(topic, start_offset)
            for topic in self._order
        }
        self._offsets = {topic: -1 for topic in self._order}
        self._next = 0

    def poll(self, timeout: float = 1.0) -> _ConsumerMessage | None:
        deadline = time.monotonic() + max(0.0, timeout)
        count = len(self._order)
        while True:
            for i in range(count):
                topic = self._order[(self._next + i) % count]
                payload = self._messengers[topic].try_recv()
                if payload is not None:
                    self._next = (self._next + i + 1) % count
                    self._offsets[topic] += 1
                    return _ConsumerMessage(payload, topic, self._offsets[topic])
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.005)

    def close(self) -> None:
        for messenger in self._messengers.values():
            messenger.close()
        self._messengers.clear()
        self._broker.close()

    def __enter__(self) -> "KafkaConsumer":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
