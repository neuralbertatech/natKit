from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from natvr.featurize import (
    build_feature_output_path,
    load_rows,
    rows_to_sample_stream,
    window_feature_vectors,
    write_feature_vectors,
)
from natvr.reconstruct_session import (
    DiscoveredRun,
    discover_runs,
    reconstruct_run,
    render_run_choice,
)
from natvr.calibration import build_calibration_output_path
from natvr.model import LdaModel
from natvr.model_bundle import (
    build_model_bundle,
    build_training_calibration_profile,
    write_model_bundle,
)
from natvr.replay_eval import evaluate_replay_session
from natvr.select_model import MODEL_FAMILIES, select_best_model, train_model_family

T = TypeVar("T")
ProgressCallback = Callable[[str], None]
StopRequestedCallback = Callable[[], bool]


class PipelineCancelledError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RunArtifacts:
    run: DiscoveredRun
    device_id: str
    parquet_path: Path
    marker_path: Path
    metadata_path: Path
    feature_path: Path
    sample_rate_hz: int


EMG_CHANNEL_FIELD_RE = re.compile(r"^channels\.(\d+)\.samples$")


def build_report_output_path(output_dir: Path) -> Path:
    return output_dir / "kafka-train-validate-report.json"


def report_progress(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def check_cancelled(should_stop: StopRequestedCallback | None) -> None:
    if should_stop is not None and should_stop():
        raise PipelineCancelledError("pipeline cancelled")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover Kafka-backed EMG recorded runs, reconstruct selected training "
            "and validation sets, train model artifacts, and evaluate them."
        )
    )
    parser.add_argument("--broker", default="127.0.0.1:29092")
    parser.add_argument("--output-dir", default="captures/model-selection")
    parser.add_argument("--group-id", default="natvr-emg-train-validate-kafka")
    parser.add_argument(
        "--family",
        action="append",
        choices=MODEL_FAMILIES,
        dest="families",
        help="Repeat to restrict model families. Defaults to lda, linear_svm, random_forest.",
    )
    parser.add_argument(
        "--train-run",
        action="append",
        dest="train_runs",
        help="Repeat run selectors as <session-id>:<run-index> for training.",
    )
    parser.add_argument(
        "--eval-run",
        action="append",
        dest="eval_runs",
        help="Repeat run selectors as <session-id>:<run-index> for validation.",
    )
    parser.add_argument("--idle-timeout-s", type=float, default=2.0)
    parser.add_argument("--no-direct-assign", action="store_true")
    parser.add_argument("--partition", type=int, default=0)
    parser.add_argument("--metadata-json")
    parser.add_argument("--allow-missing-session-end", action="store_true")
    parser.add_argument("--post-roll-us", type=int, default=1_000_000)
    parser.add_argument("--rest-gesture", default="rest")
    parser.add_argument("--active-gesture", default="fist")
    parser.add_argument("--window-ms", type=int, default=200)
    parser.add_argument("--hop-ms", type=int, default=50)
    parser.add_argument("--vote-windows", type=int, default=5)
    parser.add_argument("--confidence-threshold", type=float, default=0.6)
    parser.add_argument("--min-hold-windows", type=int, default=2)
    parser.add_argument("--emit-only-during-cue-hold", action="store_true")
    parser.add_argument(
        "--selected-field",
        action="append",
        dest="selected_fields",
        default=[],
        help=(
            "Repeat descriptor-backed EMG input fields to restrict training and "
            "evaluation, for example channels.0.samples."
        ),
    )
    return parser.parse_args(argv)


def parse_run_selector(raw: str) -> tuple[str, int]:
    session_id, separator, run_index_text = raw.partition(":")
    if not separator or not session_id.strip() or not run_index_text.strip():
        raise ValueError(
            f"invalid run selector {raw!r}; expected <session-id>:<run-index>"
        )
    try:
        run_index = int(run_index_text)
    except ValueError as exc:
        raise ValueError(
            f"invalid run selector {raw!r}; run-index must be an integer"
        ) from exc
    if run_index <= 0:
        raise ValueError(
            f"invalid run selector {raw!r}; run-index must be >= 1"
        )
    return session_id.strip(), run_index


def parse_selected_channel_indexes(
    selected_fields: list[str] | tuple[str, ...] | None,
) -> list[int] | None:
    if not selected_fields:
        return None
    indexes: list[int] = []
    invalid_fields: list[str] = []
    for raw_field in selected_fields:
        field = str(raw_field).strip()
        if not field:
            continue
        match = EMG_CHANNEL_FIELD_RE.fullmatch(field)
        if match is None:
            invalid_fields.append(field)
            continue
        indexes.append(int(match.group(1)))
    if invalid_fields:
        raise ValueError(
            "unsupported selected fields for the current EMG pipeline: "
            + ", ".join(invalid_fields)
        )
    return sorted(set(indexes)) or None


def run_identity(run: DiscoveredRun) -> tuple[str, int]:
    return run.session_id, run.run_index


def find_run_by_selector(runs: list[DiscoveredRun], raw: str) -> DiscoveredRun:
    session_id, run_index = parse_run_selector(raw)
    for run in runs:
        if run.session_id == session_id and run.run_index == run_index:
            return run
    raise RuntimeError(f"run selector {raw!r} did not match a discovered recorded run")


def unique_runs(runs: list[DiscoveredRun]) -> list[DiscoveredRun]:
    seen: set[tuple[str, int]] = set()
    unique: list[DiscoveredRun] = []
    for run in runs:
        key = run_identity(run)
        if key in seen:
            continue
        seen.add(key)
        unique.append(run)
    return unique


def parse_index_selection(raw: str, *, max_index: int) -> list[int]:
    selected: list[int] = []
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    if not tokens:
        raise ValueError("at least one index is required")
    for token in tokens:
        if "-" in token:
            start_text, _, end_text = token.partition("-")
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"invalid descending range {token!r}")
            selected.extend(range(start, end + 1))
            continue
        selected.append(int(token))
    unique = sorted(set(selected))
    if any(index < 1 or index > max_index for index in unique):
        raise ValueError(f"indices must be between 1 and {max_index}")
    return unique


def prompt_multi_select(
    prompt: str,
    runs: list[DiscoveredRun],
    *,
    disallowed: set[tuple[str, int]] | None = None,
    allow_empty: bool = False,
) -> list[DiscoveredRun]:
    disallowed = disallowed or set()
    while True:
        raw = input(prompt).strip()
        if not raw and allow_empty:
            return []
        try:
            indexes = parse_index_selection(raw, max_index=len(runs))
        except ValueError as exc:
            print(str(exc))
            continue
        selected = [runs[index - 1] for index in indexes]
        overlapping = [run for run in selected if run_identity(run) in disallowed]
        if overlapping:
            print("selected runs overlap with a previously chosen set")
            continue
        return selected


def print_discovered_runs(runs: list[DiscoveredRun]) -> None:
    print("Available recorded runs:")
    for index, run in enumerate(runs, start=1):
        print(f"  {index}. {render_run_choice(run)}")


def resolve_train_eval_runs(
    args: argparse.Namespace,
    runs: list[DiscoveredRun],
) -> tuple[list[DiscoveredRun], list[DiscoveredRun]]:
    train_runs = unique_runs([find_run_by_selector(runs, raw) for raw in (args.train_runs or [])])
    eval_runs = unique_runs([find_run_by_selector(runs, raw) for raw in (args.eval_runs or [])])

    # The validation set is OPTIONAL. A model fits on the training runs alone;
    # the validation runs are only used to report held-out accuracy and to pick
    # between model families. So we require at least one training run but allow
    # zero validation runs (e.g. only one session was recorded). A validation
    # set can always be added later for a real accuracy estimate.
    if not train_runs and not sys.stdin.isatty():
        raise RuntimeError(
            "at least one training run (--train-run) is required when stdin is not a TTY"
        )

    if sys.stdin.isatty() and (not train_runs or not eval_runs):
        print_discovered_runs(runs)
        if not train_runs:
            train_runs = prompt_multi_select(
                "Select training runs [e.g. 1,3-5]: ",
                runs,
            )
        if not eval_runs:
            eval_runs = prompt_multi_select(
                "Select validation runs (optional — leave blank to skip) [e.g. 2,6]: ",
                runs,
                disallowed=set(map(run_identity, train_runs)),
                allow_empty=True,
            )

    if not train_runs:
        raise RuntimeError("at least one training run is required")
    if eval_runs:
        overlap = set(map(run_identity, train_runs)) & set(map(run_identity, eval_runs))
        if overlap:
            raise RuntimeError("training and validation runs must be disjoint")
    return train_runs, eval_runs


def featurize_reconstruction(
    parquet_path: Path,
    *,
    marker_path: Path,
    selected_channel_indexes: list[int] | tuple[int, ...] | None,
    window_ms: int,
    hop_ms: int,
) -> tuple[Path, int]:
    rows = load_rows(parquet_path, marker_path=marker_path)
    stream, sample_rate_hz = rows_to_sample_stream(
        rows,
        selected_channel_indexes=selected_channel_indexes,
    )
    session_id = parquet_path.stem.split("__", 1)[0]
    vectors = window_feature_vectors(
        stream,
        sample_rate_hz=sample_rate_hz,
        session_id=session_id,
        window_ms=window_ms,
        hop_ms=hop_ms,
    )
    feature_path = build_feature_output_path(parquet_path)
    write_feature_vectors(feature_path, vectors)
    return feature_path, sample_rate_hz


def reconstruct_and_featurize_runs(
    args: argparse.Namespace,
    runs: list[DiscoveredRun],
    *,
    runs_per_session: dict[str, int],
    selected_channel_indexes: list[int] | tuple[int, ...] | None = None,
    progress: ProgressCallback | None = None,
    should_stop: StopRequestedCallback | None = None,
    phase_label: str = "run",
) -> list[RunArtifacts]:
    artifacts: list[RunArtifacts] = []
    for index, run in enumerate(runs, start=1):
        check_cancelled(should_stop)
        report_progress(
            progress,
            (
                f"Reconstructing {phase_label} {index}/{len(runs)}: "
                f"{run.session_id} run {run.run_index}"
            ),
        )
        child_args = argparse.Namespace(**vars(args))
        child_args.session_id = run.session_id
        child_args.device_id = None
        child_args.input_topic = None
        child_args.marker_topic = None
        child_args.meta_topic = None
        reconstructed = reconstruct_run(
            child_args,
            run,
            session_run_count=runs_per_session.get(run.session_id, 1),
        )
        check_cancelled(should_stop)
        feature_path, sample_rate_hz = featurize_reconstruction(
            reconstructed.output_path,
            marker_path=reconstructed.marker_path,
            selected_channel_indexes=selected_channel_indexes,
            window_ms=args.window_ms,
            hop_ms=args.hop_ms,
        )
        check_cancelled(should_stop)
        report_progress(
            progress,
            (
                f"Featurized {phase_label} {index}/{len(runs)}: "
                f"{run.session_id} run {run.run_index}"
            ),
        )
        artifacts.append(
            RunArtifacts(
                run=run,
                device_id=reconstructed.device_id,
                parquet_path=reconstructed.output_path,
                marker_path=reconstructed.marker_path,
                metadata_path=reconstructed.metadata_path,
                feature_path=feature_path,
                sample_rate_hz=sample_rate_hz,
            )
        )
    return artifacts


def evaluate_family(
    args: argparse.Namespace,
    *,
    family: str,
    train_artifacts: list[RunArtifacts],
    eval_artifacts: list[RunArtifacts],
    selected_channel_indexes: list[int] | tuple[int, ...] | None = None,
    progress: ProgressCallback | None = None,
    should_stop: StopRequestedCallback | None = None,
) -> dict[str, object]:
    check_cancelled(should_stop)
    report_progress(progress, f"Training {family} model")
    feature_paths = [artifact.feature_path for artifact in train_artifacts]
    model_path = train_model_family(
        feature_paths,
        family=family,
        rest_gesture=args.rest_gesture,
        active_gesture=args.active_gesture,
    )
    check_cancelled(should_stop)
    # Evaluate against the TRAINING calibration profile — the same one the LDA was
    # fit with and that the live bundle bakes in (build_training_calibration_profile).
    # A per-eval-session calibration (the old ensure_calibration_path(eval_parquet))
    # normalizes with a *different* scale_rms than the model was trained on: on a
    # channel where fist barely exceeds rest that scale collapses toward zero, the
    # normalized features land far off the model's training distribution, and
    # accuracy drops to ~chance while live serving (which uses the baked training
    # profile) does not. Reusing the training profile keeps train/eval/serve aligned.
    train_calibration_profile = build_training_calibration_profile(
        feature_paths,
        rest_gesture=args.rest_gesture,
        active_gesture=args.active_gesture,
    )
    train_calibration_path = build_calibration_output_path(feature_paths[0])
    train_calibration_path.write_text(
        json.dumps(train_calibration_profile.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    replay_reports = []
    accuracies: list[float] = []
    coverages: list[float] = []
    for index, artifact in enumerate(eval_artifacts, start=1):
        check_cancelled(should_stop)
        report_progress(
            progress,
            (
                f"Evaluating {family} on validation run {index}/{len(eval_artifacts)}: "
                f"{artifact.run.session_id} run {artifact.run.run_index}"
            ),
        )
        calibration_path = train_calibration_path
        check_cancelled(should_stop)
        report = evaluate_replay_session(
            artifact.parquet_path,
            session_id=f"{family}-{artifact.run.session_id}-run-{artifact.run.run_index}",
            model_path=model_path,
            calibration_path=calibration_path,
            marker_path=artifact.marker_path,
            device_id=artifact.device_id,
            selected_channel_indexes=selected_channel_indexes,
            window_ms=args.window_ms,
            hop_ms=args.hop_ms,
            vote_windows=args.vote_windows,
            confidence_threshold=args.confidence_threshold,
            min_hold_windows=args.min_hold_windows,
            emit_only_during_cue_hold=args.emit_only_during_cue_hold,
        )
        replay_reports.append(report)
        accuracies.append(float(report["accuracy"]))
        coverages.append(float(report["coverage"]))
    check_cancelled(should_stop)
    return {
        "family": family,
        "model_path": str(model_path),
        "train_feature_paths": [str(path) for path in feature_paths],
        "replay_reports": replay_reports,
        "mean_accuracy": (sum(accuracies) / len(accuracies)) if accuracies else 0.0,
        "min_accuracy": min(accuracies) if accuracies else 0.0,
        "mean_coverage": (sum(coverages) / len(coverages)) if coverages else 0.0,
    }


def run_pipeline(
    args: argparse.Namespace,
    progress: ProgressCallback | None = None,
    should_stop: StopRequestedCallback | None = None,
) -> dict[str, object]:
    args.direct_assign = not args.no_direct_assign
    selected_channel_indexes = parse_selected_channel_indexes(
        getattr(args, "selected_fields", None)
    )
    check_cancelled(should_stop)
    report_progress(progress, "Discovering recorded runs from Kafka")
    runs = discover_runs(args)
    if not runs:
        raise RuntimeError("no Kafka recorded runs were discovered")
    check_cancelled(should_stop)
    train_runs, eval_runs = resolve_train_eval_runs(args, runs)
    report_progress(
        progress,
        (
            f"Selected {len(train_runs)} training runs and "
            f"{len(eval_runs)} validation runs"
        ),
    )
    check_cancelled(should_stop)
    runs_per_session: dict[str, int] = {}
    for run in runs:
        runs_per_session[run.session_id] = max(
            runs_per_session.get(run.session_id, 0),
            run.run_index,
        )
    report_progress(progress, "Preparing training run reconstructions")
    train_artifacts = reconstruct_and_featurize_runs(
        args,
        train_runs,
        runs_per_session=runs_per_session,
        selected_channel_indexes=selected_channel_indexes,
        progress=progress,
        should_stop=should_stop,
        phase_label="training run",
    )
    check_cancelled(should_stop)
    report_progress(progress, "Preparing validation run reconstructions")
    eval_artifacts = reconstruct_and_featurize_runs(
        args,
        eval_runs,
        runs_per_session=runs_per_session,
        selected_channel_indexes=selected_channel_indexes,
        progress=progress,
        should_stop=should_stop,
        phase_label="validation run",
    )
    check_cancelled(should_stop)
    families = args.families or list(MODEL_FAMILIES)
    report_progress(progress, f"Evaluating {len(families)} model families")
    results = [
        evaluate_family(
            args,
            family=family,
            train_artifacts=train_artifacts,
            eval_artifacts=eval_artifacts,
            selected_channel_indexes=selected_channel_indexes,
            progress=progress,
            should_stop=should_stop,
        )
        for family in families
    ]
    check_cancelled(should_stop)
    report_progress(progress, "Selecting best model")
    selected = select_best_model(results)
    report_progress(progress, f"Selected {selected['family']} as the best model")

    # Emit the self-describing live-inference bundle for the LDA model (the only
    # family that deploys live). It captures windowing, DSP, feature order, the
    # per-session rest-calibration profile, and the LDA params so the C++
    # emg_gesture_classify transform reproduces training by construction. Built
    # from the LDA result regardless of which family "won" the accuracy
    # comparison, since only LDA is live-deployable in v1.
    train_feature_paths = [artifact.feature_path for artifact in train_artifacts]
    sample_rate_hz = train_artifacts[0].sample_rate_hz if train_artifacts else 0
    lda_result = next((result for result in results if result["family"] == "lda"), None)
    bundle_path: str | None = None
    if lda_result is not None and sample_rate_hz > 0:
        try:
            profile = build_training_calibration_profile(
                train_feature_paths,
                rest_gesture=args.rest_gesture,
                active_gesture=args.active_gesture,
            )
            lda_model = LdaModel.load_json(Path(str(lda_result["model_path"])))
            bundle = build_model_bundle(
                lda_model=lda_model,
                calibration=profile,
                sample_rate_hz=sample_rate_hz,
                window_ms=args.window_ms,
                hop_ms=args.hop_ms,
                selected_channel_indexes=selected_channel_indexes,
                zc_threshold=0.0,
                ssc_threshold=0.0,
            )
            written = write_model_bundle(Path(str(lda_result["model_path"])), bundle)
            bundle_path = str(written)
            report_progress(progress, f"Wrote live-inference bundle to {written}")
        except (ValueError, OSError, KeyError) as exc:
            report_progress(progress, f"Skipped live-inference bundle: {exc}")

    return {
        "broker": args.broker,
        "output_dir": str(Path(args.output_dir)),
        "selected_fields": list(getattr(args, "selected_fields", []) or []),
        "selected_channel_indexes": selected_channel_indexes,
        "train_runs": [
            {
                "session_id": artifact.run.session_id,
                "run_index": artifact.run.run_index,
                "device_id": artifact.device_id,
                "parquet_path": str(artifact.parquet_path),
                "marker_path": str(artifact.marker_path),
                "feature_path": str(artifact.feature_path),
            }
            for artifact in train_artifacts
        ],
        "eval_runs": [
            {
                "session_id": artifact.run.session_id,
                "run_index": artifact.run.run_index,
                "device_id": artifact.device_id,
                "parquet_path": str(artifact.parquet_path),
                "marker_path": str(artifact.marker_path),
                "feature_path": str(artifact.feature_path),
            }
            for artifact in eval_artifacts
        ],
        "results": results,
        "selected_family": selected["family"],
        "selected_model_path": selected["model_path"],
        # Accuracy/coverage are only meaningful with a held-out validation set.
        # With none, the model still trains — report null rather than a
        # misleading 0% (the family is chosen by preference, not accuracy).
        "selected_mean_accuracy": selected["mean_accuracy"] if eval_runs else None,
        "selected_min_accuracy": selected["min_accuracy"] if eval_runs else None,
        "selected_mean_coverage": selected["mean_coverage"] if eval_runs else None,
        # Self-describing live-inference bundle for emg_gesture_classify (LDA-only).
        "bundle_path": bundle_path,
        "bundle_family": "lda" if bundle_path else None,
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    report = run_pipeline(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_report_output_path(output_dir)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote Kafka train/validate report to {output_path} "
        f"(selected_family={report['selected_family']})"
    )
