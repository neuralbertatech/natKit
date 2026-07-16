from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

from natvr.calibration import CalibrationProfile, normalize_feature_vector
from natvr.emg_consumer import (
    EmgAndMarkerKafkaConsumer,
    EmgFrameEnvelope,
    EmgKafkaConsumer,
    MarkerEventEnvelope,
)
from natvr.features import WindowedFeatureVector, extract_hudgins_features
from natvr.dsp import preprocess_channel
from natvr.kafka_transport import open_producer
from natvr.marker_context import MarkerContextTracker
from natvr.model import vector_to_flat_features
from natvr.models import DeviceStatusV1, HandStateV1, MarkerEventV1
from natvr.predictor import PredictiveModel, load_prediction_model
from natvr.topics import device_status, emg_raw, hand_state, marker_stream


DEFAULT_CURLS = {
    "rest": (0.0, 0.0, 0.0, 0.0, 0.0),
    "fist": (1.0, 1.0, 1.0, 1.0, 1.0),
    "open": (0.0, 0.0, 0.0, 0.0, 0.0),
    "pinch": (0.7, 0.15, 1.0, 1.0, 1.0),
    "point": (0.7, 0.0, 1.0, 1.0, 1.0),
    "thumbs_up": (0.0, 1.0, 1.0, 1.0, 1.0),
}


def load_calibration_profile(path: Path) -> CalibrationProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CalibrationProfile(
        session_id=payload.get("session_id"),
        rest_mean_rms=tuple(float(v) for v in payload["rest_mean_rms"]),
        active_mean_rms=tuple(float(v) for v in payload["active_mean_rms"]),
        scale_rms=tuple(float(v) for v in payload["scale_rms"]),
    )


class SampleWindowBuffer:
    def __init__(self, *, sample_rate_hz: int, window_ms: int = 200, hop_ms: int = 50) -> None:
        self.sample_rate_hz = sample_rate_hz
        self.window_samples = max(1, int(round(sample_rate_hz * window_ms / 1000.0)))
        self.hop_samples = max(1, int(round(sample_rate_hz * hop_ms / 1000.0)))
        self.samples: deque[tuple[int, tuple[int, ...]]] = deque()

    def add_frame(self, frame_device_ts_us: int, channels: tuple[tuple[int, ...], ...]) -> None:
        if not channels:
            return
        sample_count = len(channels[0])
        channel_count = len(channels)
        for sample_idx in range(sample_count):
            ts_us = frame_device_ts_us + int(sample_idx * 1_000_000 / self.sample_rate_hz)
            self.samples.append(
                (
                    ts_us,
                    tuple(channels[channel_idx][sample_idx] for channel_idx in range(channel_count)),
                )
            )

    def pop_next_window(self) -> tuple[int, int, list[tuple[int, ...]]] | None:
        if len(self.samples) < self.window_samples:
            return None
        window = list(self.samples)[: self.window_samples]
        start_ts = window[0][0]
        end_ts = window[-1][0]
        values = [value for _, value in window]
        for _ in range(min(self.hop_samples, len(self.samples))):
            self.samples.popleft()
        return start_ts, end_ts, values

    def add_envelope(self, envelope: EmgFrameEnvelope) -> None:
        self.add_frame(envelope.frame.device_ts_us, envelope.frame.channels)


@dataclass(slots=True)
class GestureStabilizer:
    vote_windows: int = 5
    confidence_threshold: float = 0.6
    min_hold_windows: int = 2
    history: deque[str] = field(init=False)
    current_label: str | None = field(init=False, default=None)
    hold_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.history = deque(maxlen=self.vote_windows)

    def update(self, label: str, confidence: float) -> tuple[str | None, float]:
        if confidence < self.confidence_threshold:
            return self.current_label, confidence
        self.history.append(label)
        if len(self.history) < self.vote_windows:
            return self.current_label, confidence
        voted, count = Counter(self.history).most_common(1)[0]
        voted_conf = count / len(self.history)
        if voted != self.current_label:
            self.hold_count += 1
            if self.hold_count >= self.min_hold_windows:
                self.current_label = voted
                self.hold_count = 0
        else:
            self.hold_count = 0
        return self.current_label or voted, voted_conf


@dataclass(frozen=True, slots=True)
class WindowInferenceResult:
    start_ts_us: int
    end_ts_us: int
    predicted_gesture: str
    prediction_confidence: float
    stable_gesture: str | None
    stable_confidence: float
    compute_ms: float
    emitted_state: HandStateV1 | None
    active_marker_context: dict[str, object]


@dataclass(slots=True)
class ClassifierMetricsAccumulator:
    windows_processed: int = 0
    states_emitted: int = 0
    compute_ms_total: float = 0.0
    max_compute_ms: float = 0.0
    end_to_end_ms_total: float = 0.0
    last_compute_ms: float = 0.0
    last_end_to_end_ms: float = 0.0
    last_gesture_id: str | None = None
    last_status_emitted_monotonic: float = field(default_factory=time.monotonic)

    def observe(self, result: WindowInferenceResult) -> None:
        self.windows_processed += 1
        self.compute_ms_total += result.compute_ms
        self.last_compute_ms = result.compute_ms
        self.max_compute_ms = max(self.max_compute_ms, result.compute_ms)
        if result.emitted_state is None:
            return
        self.states_emitted += 1
        self.last_gesture_id = result.emitted_state.gesture_id
        end_to_end_ms = max(
            0.0,
            (result.emitted_state.emitted_at_us - result.end_ts_us) / 1000.0,
        )
        self.last_end_to_end_ms = end_to_end_ms
        self.end_to_end_ms_total += end_to_end_ms

    def should_emit(self, interval_s: float) -> bool:
        if interval_s <= 0:
            return False
        return (time.monotonic() - self.last_status_emitted_monotonic) >= interval_s

    def mark_status_emitted(self) -> None:
        self.last_status_emitted_monotonic = time.monotonic()

    def build_status(
        self,
        *,
        session_id: str,
        device_id: str,
        sample_rate_hz: int,
    ) -> DeviceStatusV1:
        mean_compute_ms = (
            self.compute_ms_total / self.windows_processed if self.windows_processed else 0.0
        )
        mean_end_to_end_ms = (
            self.end_to_end_ms_total / self.states_emitted if self.states_emitted else 0.0
        )
        return DeviceStatusV1(
            device_id=device_id,
            session_id=session_id,
            sample_rate_hz=sample_rate_hz,
            windows_processed=self.windows_processed,
            states_emitted=self.states_emitted,
            mean_compute_ms=mean_compute_ms,
            max_compute_ms=self.max_compute_ms,
            mean_end_to_end_ms=mean_end_to_end_ms,
            last_compute_ms=self.last_compute_ms,
            last_end_to_end_ms=self.last_end_to_end_ms,
            last_gesture_id=self.last_gesture_id,
            emitted_at_us=int(datetime.now(tz=timezone.utc).timestamp() * 1_000_000),
        )


def build_window_vector(
    values: list[tuple[int, ...]],
    *,
    sample_rate_hz: int,
    start_ts_us: int,
    end_ts_us: int,
) -> WindowedFeatureVector:
    channel_count = len(values[0])
    channel_features = []
    for channel_idx in range(channel_count):
        raw_channel = [float(sample[channel_idx]) for sample in values]
        processed = preprocess_channel(
            raw_channel,
            sample_rate_hz=sample_rate_hz,
            highpass_hz=20.0,
            rectify_signal=False,
            envelope_window_samples=None,
        )
        channel_features.append(extract_hudgins_features(processed))
    return WindowedFeatureVector(
        session_id=None,
        gesture=None,
        phase=None,
        start_ts_us=start_ts_us,
        end_ts_us=end_ts_us,
        channel_features=tuple(channel_features),
    )


def hand_state_to_dict(state: HandStateV1) -> dict[str, Any]:
    return state.to_dict()


def hand_state_from_prediction(
    *,
    session_id: str,
    device_id: str,
    gesture: str,
    confidence: float,
    start_ts_us: int,
    end_ts_us: int,
) -> HandStateV1:
    return HandStateV1(
        session_id=session_id,
        gesture_id=gesture,
        confidence=confidence,
        curls=DEFAULT_CURLS.get(gesture, DEFAULT_CURLS["rest"]),
        source_window_start_us=start_ts_us,
        source_window_end_us=end_ts_us,
        emitted_at_us=int(datetime.now(tz=timezone.utc).timestamp() * 1_000_000),
        source_device_id=device_id,
    )


@dataclass(slots=True)
class ClassifierEngine:
    device_id: str
    session_id: str
    sample_rate_hz: int
    model: PredictiveModel
    calibration: CalibrationProfile
    window_ms: int = 200
    hop_ms: int = 50
    vote_windows: int = 5
    confidence_threshold: float = 0.6
    min_hold_windows: int = 2
    emit_only_during_cue_hold: bool = False
    buffer: SampleWindowBuffer = field(init=False)
    stabilizer: GestureStabilizer = field(init=False)
    marker_context: MarkerContextTracker = field(init=False)

    def __post_init__(self) -> None:
        self.buffer = SampleWindowBuffer(
            sample_rate_hz=self.sample_rate_hz,
            window_ms=self.window_ms,
            hop_ms=self.hop_ms,
        )
        self.stabilizer = GestureStabilizer(
            vote_windows=self.vote_windows,
            confidence_threshold=self.confidence_threshold,
            min_hold_windows=self.min_hold_windows,
        )
        self.marker_context = MarkerContextTracker()

    def observe_marker_event(self, marker: MarkerEventV1) -> None:
        self.marker_context.observe(marker)

    def current_marker_context(self) -> dict[str, object]:
        return self.marker_context.to_output_context()

    def process_frame_detailed(
        self,
        *,
        device_ts_us: int,
        channels: tuple[tuple[int, ...], ...],
    ) -> list[WindowInferenceResult]:
        self.buffer.add_frame(device_ts_us, channels)
        outputs: list[WindowInferenceResult] = []
        while True:
            window = self.buffer.pop_next_window()
            if window is None:
                break
            start_ts_us, end_ts_us, values = window
            started = time.perf_counter()
            vector = build_window_vector(
                values,
                sample_rate_hz=self.sample_rate_hz,
                start_ts_us=start_ts_us,
                end_ts_us=end_ts_us,
            )
            normalized = normalize_feature_vector(vector, self.calibration)
            flat = vector_to_flat_features(normalized)
            predicted, confidence = self.model.predict_confidence(flat)
            gesture, stable_conf = self.stabilizer.update(predicted, confidence)
            active_marker_context = self.current_marker_context()
            emitted_state = None
            cue_phase = active_marker_context.get("cue_phase")
            allow_emit = not self.emit_only_during_cue_hold or cue_phase in {
                "hold",
                "gesture_hold",
            }
            if gesture and allow_emit:
                emitted_state = hand_state_from_prediction(
                    session_id=self.session_id,
                    device_id=self.device_id,
                    gesture=gesture,
                    confidence=stable_conf,
                    start_ts_us=start_ts_us,
                    end_ts_us=end_ts_us,
                )
            compute_ms = (time.perf_counter() - started) * 1000.0
            outputs.append(
                WindowInferenceResult(
                    start_ts_us=start_ts_us,
                    end_ts_us=end_ts_us,
                    predicted_gesture=predicted,
                    prediction_confidence=confidence,
                    stable_gesture=gesture,
                    stable_confidence=stable_conf,
                    compute_ms=compute_ms,
                    emitted_state=emitted_state,
                    active_marker_context=active_marker_context,
                )
            )
        return outputs

    def process_frame(
        self,
        *,
        device_ts_us: int,
        channels: tuple[tuple[int, ...], ...],
    ) -> list[HandStateV1]:
        return [
            result.emitted_state
            for result in self.process_frame_detailed(
                device_ts_us=device_ts_us,
                channels=channels,
            )
            if result.emitted_state is not None
        ]


def build_model_output_path(first_path: Path) -> Path:
    return first_path.parent / "lda-model.json"


def resolve_classifier_input_topics(
    *,
    device_id: str,
    session_id: str,
    input_topic: str | None = None,
    marker_topic: str | None = None,
    disable_marker_stream: bool = False,
) -> tuple[str, str | None]:
    emg_topic = input_topic or emg_raw(device_id)
    resolved_marker_topic = None
    if not disable_marker_stream:
        resolved_marker_topic = marker_topic or marker_stream(session_id)
    return emg_topic, resolved_marker_topic


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a live EMG classifier service from Kafka raw frames to hand.state."
    )
    parser.add_argument("--broker", default="127.0.0.1:29092")
    parser.add_argument("--device-id", required=True)
    parser.add_argument(
        "--input-topic",
        help="Optional Kafka topic override for EMG input; defaults to the canonical emg_raw(device_id) topic.",
    )
    parser.add_argument(
        "--marker-topic",
        help="Optional Kafka topic override for marker input; defaults to the canonical marker_stream(session_id) topic.",
    )
    parser.add_argument(
        "--disable-marker-stream",
        action="store_true",
        help="Consume only raw EMG frames and ignore the session marker stream.",
    )
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--group-id", default="natvr-emg-classifier")
    parser.add_argument("--direct-assign", action="store_true")
    parser.add_argument("--partition", type=int, default=0)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--calibration-path", required=True)
    parser.add_argument("--window-ms", type=int, default=200)
    parser.add_argument("--hop-ms", type=int, default=50)
    parser.add_argument("--vote-windows", type=int, default=5)
    parser.add_argument("--confidence-threshold", type=float, default=0.6)
    parser.add_argument("--min-hold-windows", type=int, default=2)
    parser.add_argument("--emit-only-during-cue-hold", action="store_true")
    parser.add_argument("--status-interval-s", type=float, default=2.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    model = load_prediction_model(Path(args.model_path))
    calibration = load_calibration_profile(Path(args.calibration_path))
    emg_topic, resolved_marker_topic = resolve_classifier_input_topics(
        device_id=args.device_id,
        session_id=args.session_id,
        input_topic=args.input_topic,
        marker_topic=args.marker_topic,
        disable_marker_stream=args.disable_marker_stream,
    )
    consumer = (
        EmgAndMarkerKafkaConsumer(
            bootstrap_servers=args.broker,
            device_id=args.device_id,
            session_id=args.session_id,
            group_id=args.group_id,
            emg_topic=emg_topic,
            marker_topic=resolved_marker_topic,
            direct_assign=args.direct_assign,
            partition=args.partition,
        )
        if resolved_marker_topic is not None
        else None
    )
    emg_only_consumer: EmgKafkaConsumer | None = None
    if consumer is None:
        emg_only_consumer = EmgKafkaConsumer(
            bootstrap_servers=args.broker,
            device_id=args.device_id,
            group_id=args.group_id,
            topic=emg_topic,
            direct_assign=args.direct_assign,
            partition=args.partition,
        )
    producer = open_producer(args.broker)
    engine: ClassifierEngine | None = None
    metrics = ClassifierMetricsAccumulator()
    pending_markers: list[MarkerEventV1] = []
    topic = hand_state(args.session_id)
    status_topic = device_status(args.device_id)
    try:
        while True:
            stream_event = (
                consumer.poll(timeout=1.0)
                if consumer is not None
                else emg_only_consumer.poll(timeout=1.0)
            )
            if stream_event is None:
                continue
            if isinstance(stream_event, MarkerEventEnvelope):
                if engine is not None:
                    engine.observe_marker_event(stream_event.marker)
                else:
                    pending_markers.append(stream_event.marker)
                continue
            envelope = stream_event
            if engine is None:
                engine = ClassifierEngine(
                    device_id=args.device_id,
                    session_id=args.session_id,
                    sample_rate_hz=envelope.frame.sample_rate_hz,
                    window_ms=args.window_ms,
                    hop_ms=args.hop_ms,
                    vote_windows=args.vote_windows,
                    confidence_threshold=args.confidence_threshold,
                    min_hold_windows=args.min_hold_windows,
                    emit_only_during_cue_hold=args.emit_only_during_cue_hold,
                    model=model,
                    calibration=calibration,
                )
                for marker in pending_markers:
                    engine.observe_marker_event(marker)
                pending_markers.clear()
            for result in engine.process_frame_detailed(
                device_ts_us=envelope.frame.device_ts_us,
                channels=envelope.frame.channels,
            ):
                metrics.observe(result)
                if result.emitted_state is not None:
                    producer.produce(topic, result.emitted_state.to_json_bytes())
                    producer.poll(0)
            if engine is not None and metrics.should_emit(args.status_interval_s):
                status = metrics.build_status(
                    session_id=args.session_id,
                    device_id=args.device_id,
                    sample_rate_hz=engine.sample_rate_hz,
                )
                producer.produce(status_topic, status.to_json_bytes())
                producer.poll(0)
                metrics.mark_status_emitted()
    finally:
        if consumer is not None:
            consumer.close()
        elif emg_only_consumer is not None:
            emg_only_consumer.close()
        producer.flush()
        producer.close()
