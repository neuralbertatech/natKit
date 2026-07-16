from __future__ import annotations

from dataclasses import dataclass
import math


def _normalize_biquad(
    b0: float,
    b1: float,
    b2: float,
    a0: float,
    a1: float,
    a2: float,
) -> tuple[float, float, float, float, float]:
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


@dataclass(frozen=True, slots=True)
class BiquadCoefficients:
    b0: float
    b1: float
    b2: float
    a1: float
    a2: float


class BiquadFilter:
    def __init__(self, coefficients: BiquadCoefficients) -> None:
        self.coefficients = coefficients
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    def process(self, samples: list[float] | tuple[float, ...]) -> list[float]:
        output: list[float] = []
        c = self.coefficients
        for x0 in samples:
            y0 = (
                c.b0 * x0
                + c.b1 * self.x1
                + c.b2 * self.x2
                - c.a1 * self.y1
                - c.a2 * self.y2
            )
            output.append(y0)
            self.x2 = self.x1
            self.x1 = x0
            self.y2 = self.y1
            self.y1 = y0
        return output


def design_notch(sample_rate_hz: int, frequency_hz: float, q: float = 30.0) -> BiquadCoefficients:
    w0 = 2.0 * math.pi * frequency_hz / sample_rate_hz
    alpha = math.sin(w0) / (2.0 * q)
    b0, b1, b2 = 1.0, -2.0 * math.cos(w0), 1.0
    a0, a1, a2 = 1.0 + alpha, -2.0 * math.cos(w0), 1.0 - alpha
    nb0, nb1, nb2, na1, na2 = _normalize_biquad(b0, b1, b2, a0, a1, a2)
    return BiquadCoefficients(nb0, nb1, nb2, na1, na2)


def design_highpass(
    sample_rate_hz: int,
    cutoff_hz: float,
    q: float = 1.0 / math.sqrt(2.0),
) -> BiquadCoefficients:
    w0 = 2.0 * math.pi * cutoff_hz / sample_rate_hz
    alpha = math.sin(w0) / (2.0 * q)
    cos_w0 = math.cos(w0)
    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0, a1, a2 = 1.0 + alpha, -2.0 * cos_w0, 1.0 - alpha
    nb0, nb1, nb2, na1, na2 = _normalize_biquad(b0, b1, b2, a0, a1, a2)
    return BiquadCoefficients(nb0, nb1, nb2, na1, na2)


def apply_notch_chain(
    samples: list[float] | tuple[float, ...],
    *,
    sample_rate_hz: int,
    base_frequency_hz: float = 60.0,
    harmonics: int = 3,
    q: float = 30.0,
) -> list[float]:
    output = [float(sample) for sample in samples]
    for harmonic in range(1, harmonics + 1):
        frequency = base_frequency_hz * harmonic
        if frequency >= sample_rate_hz / 2.0:
            break
        filt = BiquadFilter(design_notch(sample_rate_hz, frequency, q=q))
        output = filt.process(output)
    return output


def apply_highpass(
    samples: list[float] | tuple[float, ...],
    *,
    sample_rate_hz: int,
    cutoff_hz: float = 20.0,
) -> list[float]:
    filt = BiquadFilter(design_highpass(sample_rate_hz, cutoff_hz))
    return filt.process([float(sample) for sample in samples])


def rectify(samples: list[float] | tuple[float, ...]) -> list[float]:
    return [abs(sample) for sample in samples]


def moving_rms(samples: list[float] | tuple[float, ...], window_size: int) -> list[float]:
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if not samples:
        return []
    output: list[float] = []
    acc = 0.0
    squares = [float(sample) * float(sample) for sample in samples]
    for idx, square in enumerate(squares):
        acc += square
        if idx >= window_size:
            acc -= squares[idx - window_size]
        denom = min(idx + 1, window_size)
        output.append(math.sqrt(acc / denom))
    return output


def preprocess_channel(
    samples: list[int] | tuple[int, ...],
    *,
    sample_rate_hz: int,
    notch_base_hz: float = 60.0,
    notch_harmonics: int = 3,
    highpass_hz: float | None = 20.0,
    rectify_signal: bool = True,
    envelope_window_samples: int | None = None,
) -> list[float]:
    processed = apply_notch_chain(
        [float(sample) for sample in samples],
        sample_rate_hz=sample_rate_hz,
        base_frequency_hz=notch_base_hz,
        harmonics=notch_harmonics,
    )
    if highpass_hz is not None:
        processed = apply_highpass(
            processed,
            sample_rate_hz=sample_rate_hz,
            cutoff_hz=highpass_hz,
        )
    if rectify_signal:
        processed = rectify(processed)
    if envelope_window_samples:
        processed = moving_rms(processed, envelope_window_samples)
    return processed
