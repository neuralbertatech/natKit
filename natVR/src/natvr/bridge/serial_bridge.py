"""Serial backup ingest shim: USB serial -> MQTT.

When an ESP32 EMG node cannot reach natKit over WiFi it can be built in serial
transport mode (``idf.py -DNATVR_TRANSPORT_SERIAL=1 build``), which writes the
*same* newline-delimited ``exg.pill.emg.data.v1`` JSON frames to the USB serial
console instead of publishing them over MQTT.

This shim runs on the host the device is plugged into. It reads those lines and
republishes each frame **verbatim** onto the standard MQTT topic
(``natKit/sending/emg/raw/emg.raw.<device_id>``). Because the KafkaMosquittoBridge
routes MQTT -> Kafka on the JSON payload's ``schema_version`` (not the topic
string) and we forward the original bytes untouched, the resulting Kafka stream
is byte-identical to the WiFi transport -- the bridge, stream discovery, and the
whole downstream pipeline see no difference.

Non-JSON lines (firmware log/banner output) are skipped, so the shim is robust to
interleaved diagnostics on the console.

Run with::

    natvr-serial-bridge --serial-port /dev/ttyACM0 --mqtt-host <broker>

Requires the ``serial`` extra (``pip install 'natvr[serial]'``): pyserial for the
USB read and paho-mqtt for the publish.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time
from typing import Any


LOG = logging.getLogger(__name__)

EMG_SCHEMA_VERSION = "exg.pill.emg.data.v1"
STATUS_SCHEMA_VERSION = "device.firmware.status.v1"

# Identical to the firmware's own topic construction (configure_topics() in
# natVR/firmware/main/main.cpp) so the serial path is indistinguishable from WiFi.
EMG_TOPIC_TEMPLATE = "natKit/sending/emg/raw/emg.raw.{device_id}"
STATUS_TOPIC_TEMPLATE = "natKit/sending/emg/status/device.status.{status_device_id}"

# Required keys for a v1 EMG frame. Loaded from the schema file when available so
# this tracks the contract; the literal is the fallback if the schema is absent.
_EMG_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "schemas" / "exg-pill-emg-data-v1.schema.json"
)
_EMG_REQUIRED_FALLBACK = (
    "schema_version",
    "device_id",
    "seq_no",
    "device_ts_us",
    "n_channels",
    "samples_per_channel",
    "sample_rate_hz",
    "channel_labels",
    "payload",
)


def _load_emg_required() -> tuple[str, ...]:
    try:
        with _EMG_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
        required = schema.get("required")
        if isinstance(required, list) and all(isinstance(k, str) for k in required):
            return tuple(required)
    except (OSError, ValueError):
        pass
    return _EMG_REQUIRED_FALLBACK


@dataclass(frozen=True, slots=True)
class SerialBridgeConfig:
    serial_port: str = os.getenv("NATVR_SERIAL_PORT", "/dev/ttyACM0")
    serial_baud: int = int(os.getenv("NATVR_SERIAL_BAUD", "115200"))
    mqtt_host: str = os.getenv("NATVR_MQTT_HOST", "127.0.0.1")
    mqtt_port: int = int(os.getenv("NATVR_MQTT_PORT", "1883"))
    mqtt_keepalive: int = int(os.getenv("NATVR_MQTT_KEEPALIVE", "30"))
    mqtt_client_id: str = os.getenv("NATVR_MQTT_CLIENT_ID", "natvr-serial-bridge")
    reconnect_delay_s: float = float(os.getenv("NATVR_SERIAL_RECONNECT_S", "2.0"))
    stats_interval_s: float = float(os.getenv("NATVR_SERIAL_STATS_S", "10.0"))


class _Stats:
    __slots__ = ("published", "skipped_nonjson", "skipped_invalid")

    def __init__(self) -> None:
        self.published = 0
        self.skipped_nonjson = 0
        self.skipped_invalid = 0


def _validate_emg_frame(obj: dict[str, Any], required: tuple[str, ...]) -> str | None:
    """Return None if the object is a well-formed EMG frame, else a reason string.

    A lightweight structural check (no jsonschema dependency): it guards against
    truncated/corrupt serial lines that happen to parse as JSON, and confirms the
    channel/sample geometry is self-consistent before we forward the frame.
    """
    for key in required:
        if key not in obj:
            return f"missing key {key!r}"
    if obj.get("schema_version") != EMG_SCHEMA_VERSION:
        return f"unexpected schema_version {obj.get('schema_version')!r}"
    payload = obj["payload"]
    n_channels = obj["n_channels"]
    samples_per_channel = obj["samples_per_channel"]
    if not isinstance(payload, list) or len(payload) != n_channels:
        return "payload channel count != n_channels"
    for channel in payload:
        if not isinstance(channel, list) or len(channel) != samples_per_channel:
            return "payload sample count != samples_per_channel"
    return None


def _route_line(
    line: str, required: tuple[str, ...], stats: _Stats
) -> tuple[str, bytes] | None:
    """Parse one console line -> (mqtt_topic, payload_bytes) to publish, or None.

    The published payload is the original line bytes (verbatim), so the frame the
    bridge sees is byte-for-byte what the firmware serialized.
    """
    try:
        obj = json.loads(line)
    except ValueError:
        stats.skipped_nonjson += 1
        LOG.debug("skipping non-JSON line: %s", line[:120])
        return None
    if not isinstance(obj, dict):
        stats.skipped_nonjson += 1
        return None

    schema_version = obj.get("schema_version")
    if schema_version == EMG_SCHEMA_VERSION:
        reason = _validate_emg_frame(obj, required)
        if reason is not None:
            stats.skipped_invalid += 1
            LOG.warning("dropping invalid EMG frame: %s", reason)
            return None
        topic = EMG_TOPIC_TEMPLATE.format(device_id=obj["device_id"])
        return topic, line.encode("utf-8")
    if schema_version == STATUS_SCHEMA_VERSION:
        status_device_id = obj.get("status_device_id") or obj.get("device_id")
        if not status_device_id:
            stats.skipped_invalid += 1
            return None
        topic = STATUS_TOPIC_TEMPLATE.format(status_device_id=status_device_id)
        return topic, line.encode("utf-8")

    stats.skipped_nonjson += 1
    LOG.debug("skipping line with unknown schema_version %r", schema_version)
    return None


def _import_dependencies():  # pragma: no cover - thin dependency shim
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "natvr-serial-bridge needs pyserial. Install the serial extra:\n"
            "    pip install 'natvr[serial]'   (or: pip install pyserial paho-mqtt)"
        ) from exc
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "natvr-serial-bridge needs paho-mqtt. Install the serial extra:\n"
            "    pip install 'natvr[serial]'   (or: pip install pyserial paho-mqtt)"
        ) from exc
    return serial, mqtt


def run_bridge(config: SerialBridgeConfig, stop_event: threading.Event) -> None:
    serial, mqtt = _import_dependencies()
    required = _load_emg_required()
    stats = _Stats()

    client = mqtt.Client(client_id=config.mqtt_client_id, clean_session=True)
    client.connect_async(config.mqtt_host, config.mqtt_port, config.mqtt_keepalive)
    # loop_start handles connect + automatic reconnect on a background thread.
    client.loop_start()
    LOG.info(
        "publishing to MQTT %s:%d as %s",
        config.mqtt_host,
        config.mqtt_port,
        config.mqtt_client_id,
    )

    last_stats = time.monotonic()
    try:
        while not stop_event.is_set():
            try:
                with serial.Serial(
                    config.serial_port, config.serial_baud, timeout=1.0
                ) as port:
                    LOG.info(
                        "reading EMG frames from %s @ %d baud",
                        config.serial_port,
                        config.serial_baud,
                    )
                    while not stop_event.is_set():
                        raw = port.readline()
                        if not raw:
                            # readline timeout; fall through to stats/heartbeat.
                            pass
                        else:
                            line = raw.decode("utf-8", errors="replace").strip()
                            if line:
                                routed = _route_line(line, required, stats)
                                if routed is not None:
                                    topic, payload = routed
                                    client.publish(topic, payload, qos=0)
                                    stats.published += 1

                        now = time.monotonic()
                        if now - last_stats >= config.stats_interval_s:
                            LOG.info(
                                "published=%d skipped_nonjson=%d skipped_invalid=%d",
                                stats.published,
                                stats.skipped_nonjson,
                                stats.skipped_invalid,
                            )
                            last_stats = now
            except serial.SerialException as exc:
                LOG.warning(
                    "serial port %s unavailable (%s); retrying in %.1fs",
                    config.serial_port,
                    exc,
                    config.reconnect_delay_s,
                )
                stop_event.wait(config.reconnect_delay_s)
    finally:
        client.loop_stop()
        client.disconnect()
        LOG.info(
            "serial bridge stopped: published=%d skipped_nonjson=%d skipped_invalid=%d",
            stats.published,
            stats.skipped_nonjson,
            stats.skipped_invalid,
        )


def _parse_args(argv: list[str] | None = None) -> SerialBridgeConfig:
    defaults = SerialBridgeConfig()
    parser = argparse.ArgumentParser(
        prog="natvr-serial-bridge",
        description="Republish ESP32 serial-mode EMG frames onto the standard MQTT topics.",
    )
    parser.add_argument("--serial-port", default=defaults.serial_port)
    parser.add_argument("--serial-baud", type=int, default=defaults.serial_baud)
    parser.add_argument("--mqtt-host", default=defaults.mqtt_host)
    parser.add_argument("--mqtt-port", type=int, default=defaults.mqtt_port)
    parser.add_argument("--mqtt-keepalive", type=int, default=defaults.mqtt_keepalive)
    parser.add_argument("--mqtt-client-id", default=defaults.mqtt_client_id)
    args = parser.parse_args(argv)
    return SerialBridgeConfig(
        serial_port=args.serial_port,
        serial_baud=args.serial_baud,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_keepalive=args.mqtt_keepalive,
        mqtt_client_id=args.mqtt_client_id,
        reconnect_delay_s=defaults.reconnect_delay_s,
        stats_interval_s=defaults.stats_interval_s,
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("NATVR_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = _parse_args()
    stop_event = threading.Event()

    def _handle_signal(*_args: object) -> None:
        LOG.info("shutdown requested")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    run_bridge(config, stop_event)


if __name__ == "__main__":
    main()
