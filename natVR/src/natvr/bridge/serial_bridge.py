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
from collections import deque
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time
from typing import Any, Callable


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


# A serial port value of this (case-insensitive) asks the bridge to auto-detect
# the device port at each (re)connect instead of using a fixed path.
AUTODETECT_PORT = "auto"

# USB VID:PID pairs common to ESP32 dev boards, used to prefer a real device port
# when auto-detecting. Espressif native USB-CDC, SiLabs CP210x, and WCH CH340.
_KNOWN_USB_VID_PIDS = frozenset(
    {
        (0x303A, None),  # Espressif (native USB-JTAG/serial, e.g. ESP32-C3/S3)
        (0x10C4, None),  # Silicon Labs CP210x
        (0x1A86, None),  # WCH CH340/CH341
    }
)


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
    # De-dupe by (device_id, seq_no) over this many recent seq_nos per device.
    # 0 disables. Covers the AUTO wireless<->serial handoff seam.
    dedupe_window: int = int(os.getenv("NATVR_SERIAL_DEDUPE_WINDOW", "4096"))
    # Rewrite device_ts_us from the host wall clock (for unsynced serial frames).
    stamp_host_time: bool = os.getenv("NATVR_SERIAL_STAMP_HOST_TIME", "0") == "1"


class _Stats:
    __slots__ = ("published", "skipped_nonjson", "skipped_invalid", "skipped_duplicate")

    def __init__(self) -> None:
        self.published = 0
        self.skipped_nonjson = 0
        self.skipped_invalid = 0
        self.skipped_duplicate = 0


class _FrameDeduper:
    """Drop already-seen ``(device_id, seq_no)`` frames within a sliding window.

    During an AUTO wireless<->serial handoff -- or when an operator forces SERIAL
    while MQTT is still flushing -- the same frame can momentarily arrive on both
    paths. This drops the second copy before it reaches MQTT/Kafka. The window is
    bounded per device so a long run doesn't grow without limit; the seq_no space
    is far larger than the window, so wrap-around is a non-issue here.
    """

    __slots__ = ("_window", "_recent")

    def __init__(self, window: int) -> None:
        self._window = max(1, window)
        # device_id -> (set of recent seq_nos, insertion-order queue for eviction)
        self._recent: dict[str, tuple[set[int], deque[int]]] = {}

    def is_duplicate(self, device_id: str, seq_no: int) -> bool:
        seen, order = self._recent.setdefault(device_id, (set(), deque()))
        if seq_no in seen:
            return True
        seen.add(seq_no)
        order.append(seq_no)
        if len(order) > self._window:
            seen.discard(order.popleft())
        return False


class _HostTimeStamper:
    """Rewrite ``device_ts_us`` from the host wall clock for unsynced frames.

    A serial-only device with no NTP stamps frames from its local monotonic clock,
    which has no wall-clock reference. With ``--stamp-host-time`` the bridge
    overwrites ``device_ts_us`` with the host clock at receipt, kept monotonically
    non-decreasing per device so downstream windowing/reconstruction stays ordered.
    This *rewrites* the frame -- it is no longer byte-identical to the firmware
    output -- so it is opt-in only.
    """

    __slots__ = ("_now_us", "_last")

    def __init__(self, now_us: Callable[[], int] | None = None) -> None:
        self._now_us = now_us or (lambda: int(time.time() * 1_000_000))
        self._last: dict[str, int] = {}

    def stamp(self, device_id: str, obj: dict[str, Any]) -> None:
        candidate = self._now_us()
        last = self._last.get(device_id)
        if last is not None and candidate <= last:
            candidate = last + 1
        self._last[device_id] = candidate
        obj["device_ts_us"] = candidate


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
    line: str,
    required: tuple[str, ...],
    stats: _Stats,
    *,
    deduper: _FrameDeduper | None = None,
    stamper: _HostTimeStamper | None = None,
) -> tuple[str, bytes] | None:
    """Parse one console line -> (mqtt_topic, payload_bytes) to publish, or None.

    By default the published payload is the original line bytes (verbatim), so the
    frame the bridge sees is byte-for-byte what the firmware serialized. When a
    ``deduper`` is supplied, an EMG frame whose ``(device_id, seq_no)`` was seen
    recently is dropped (the switchover-overlap safety net). When a ``stamper`` is
    supplied, ``device_ts_us`` is rewritten from the host clock and the frame is
    re-serialized (no longer byte-identical -- opt-in via --stamp-host-time).
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
        device_id = obj["device_id"]
        seq_no = obj.get("seq_no")
        if deduper is not None and isinstance(seq_no, int) and deduper.is_duplicate(
            device_id, seq_no
        ):
            stats.skipped_duplicate += 1
            LOG.debug("dropping duplicate frame %s/%s", device_id, seq_no)
            return None
        topic = EMG_TOPIC_TEMPLATE.format(device_id=device_id)
        if stamper is not None:
            stamper.stamp(device_id, obj)
            return topic, json.dumps(obj, separators=(",", ":")).encode("utf-8")
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


def _pick_autodetect_port(ports: list[Any]) -> str | None:
    """Choose the most likely device port from a list of pyserial ListPortInfo.

    Prefers a port whose USB VID matches a known ESP32 dev-board bridge; otherwise
    falls back to the first ``ttyACM*``/``ttyUSB*`` (Linux) or ``cu.*`` (macOS)
    device. Returns None if nothing plausible is present.
    """
    candidates = list(ports)
    for info in candidates:
        vid = getattr(info, "vid", None)
        if vid is not None and (vid, None) in _KNOWN_USB_VID_PIDS:
            return info.device
    for info in candidates:
        device = getattr(info, "device", "") or ""
        name = device.rsplit("/", 1)[-1]
        if name.startswith(("ttyACM", "ttyUSB", "cu.")):
            return device
    return None


def _resolve_serial_port(config: SerialBridgeConfig, serial_module: Any) -> str | None:
    """Return the serial port to open, auto-detecting when configured to.

    A fixed ``serial_port`` is returned as-is. The ``AUTODETECT_PORT`` sentinel
    scans the currently-attached ports so a bumped/replugged cable can land on a
    different device path without restarting the bridge.
    """
    if config.serial_port.lower() != AUTODETECT_PORT:
        return config.serial_port
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError:  # pragma: no cover - pyserial always ships list_ports
        return None
    port = _pick_autodetect_port(list(list_ports.comports()))
    if port is not None:
        LOG.info("auto-detected serial port %s", port)
    return port


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
    deduper = _FrameDeduper(config.dedupe_window) if config.dedupe_window > 0 else None
    stamper = _HostTimeStamper() if config.stamp_host_time else None
    if stamper is not None:
        LOG.info("stamping device_ts_us from host wall clock (frames re-serialized)")

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
                port_path = _resolve_serial_port(config, serial)
                if port_path is None:
                    LOG.warning(
                        "no serial device found (port=%s); retrying in %.1fs",
                        config.serial_port,
                        config.reconnect_delay_s,
                    )
                    stop_event.wait(config.reconnect_delay_s)
                    continue
                with serial.Serial(port_path, config.serial_baud, timeout=1.0) as port:
                    LOG.info(
                        "reading EMG frames from %s @ %d baud",
                        port_path,
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
                                routed = _route_line(
                                    line,
                                    required,
                                    stats,
                                    deduper=deduper,
                                    stamper=stamper,
                                )
                                if routed is not None:
                                    topic, payload = routed
                                    client.publish(topic, payload, qos=0)
                                    stats.published += 1

                        now = time.monotonic()
                        if now - last_stats >= config.stats_interval_s:
                            LOG.info(
                                "published=%d skipped_nonjson=%d skipped_invalid=%d "
                                "skipped_duplicate=%d",
                                stats.published,
                                stats.skipped_nonjson,
                                stats.skipped_invalid,
                                stats.skipped_duplicate,
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
            "serial bridge stopped: published=%d skipped_nonjson=%d "
            "skipped_invalid=%d skipped_duplicate=%d",
            stats.published,
            stats.skipped_nonjson,
            stats.skipped_invalid,
            stats.skipped_duplicate,
        )


def _parse_args(argv: list[str] | None = None) -> SerialBridgeConfig:
    defaults = SerialBridgeConfig()
    parser = argparse.ArgumentParser(
        prog="natvr-serial-bridge",
        description="Republish ESP32 serial-mode EMG frames onto the standard MQTT topics.",
    )
    parser.add_argument(
        "--serial-port",
        default=defaults.serial_port,
        help=f"serial device path, or '{AUTODETECT_PORT}' to scan for it",
    )
    parser.add_argument("--serial-baud", type=int, default=defaults.serial_baud)
    parser.add_argument("--mqtt-host", default=defaults.mqtt_host)
    parser.add_argument("--mqtt-port", type=int, default=defaults.mqtt_port)
    parser.add_argument("--mqtt-keepalive", type=int, default=defaults.mqtt_keepalive)
    parser.add_argument("--mqtt-client-id", default=defaults.mqtt_client_id)
    parser.add_argument(
        "--dedupe-window",
        type=int,
        default=defaults.dedupe_window,
        help="per-device (device_id, seq_no) de-dupe window; 0 disables",
    )
    parser.add_argument(
        "--stamp-host-time",
        action="store_true",
        default=defaults.stamp_host_time,
        help="rewrite device_ts_us from the host clock for unsynced serial frames "
        "(re-serializes the frame; use for serial-only devices without NTP)",
    )
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
        dedupe_window=args.dedupe_window,
        stamp_host_time=args.stamp_host_time,
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
