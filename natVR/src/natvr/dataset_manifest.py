from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from typing import Any

from natvr.featurize import infer_session_id


@dataclass(frozen=True, slots=True)
class DatasetSource:
    path: str
    kind: str
    session_id: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "kind": self.kind,
            "session_id": self.session_id,
            "sha256": self.sha256,
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_source(path: Path) -> str:
    if path.name.endswith(".features.jsonl"):
        return "feature_windows"
    if path.suffix == ".parquet":
        return "raw_capture"
    return "artifact"


def normalize_sources(paths: list[Path]) -> list[DatasetSource]:
    normalized = []
    for path in paths:
        normalized.append(
            DatasetSource(
                path=str(path),
                kind=classify_source(path),
                session_id=infer_session_id(path),
                sha256=file_sha256(path),
            )
        )
    return normalized


def build_session_splits(
    session_ids: list[str],
    *,
    seed: int = 7,
    train_fraction: float = 0.7,
    val_fraction: float = 0.15,
) -> dict[str, list[str]]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between 0 and 1")
    if not 0.0 <= val_fraction < 1.0:
        raise ValueError("val_fraction must be between 0 and 1")
    if train_fraction + val_fraction >= 1.0:
        raise ValueError("train_fraction + val_fraction must be < 1")

    ordered = sorted(set(session_ids))
    if not ordered:
        return {"train": [], "val": [], "test": []}

    rng = random.Random(seed)
    rng.shuffle(ordered)

    if len(ordered) == 1:
        return {"train": ordered, "val": [], "test": []}
    if len(ordered) == 2:
        return {"train": [ordered[0]], "val": [], "test": [ordered[1]]}

    n_sessions = len(ordered)
    train_count = max(1, int(round(n_sessions * train_fraction)))
    val_count = max(1, int(round(n_sessions * val_fraction)))
    if train_count + val_count >= n_sessions:
        val_count = 1
        train_count = max(1, n_sessions - 2)
    test_count = n_sessions - train_count - val_count
    if test_count <= 0:
        test_count = 1
        if train_count > val_count:
            train_count -= 1
        else:
            val_count -= 1

    train_ids = sorted(ordered[:train_count])
    val_ids = sorted(ordered[train_count : train_count + val_count])
    test_ids = sorted(ordered[train_count + val_count :])
    return {"train": train_ids, "val": val_ids, "test": test_ids}


def build_dataset_manifest(
    paths: list[Path],
    *,
    dataset_name: str | None = None,
    seed: int = 7,
    train_fraction: float = 0.7,
    val_fraction: float = 0.15,
) -> dict[str, Any]:
    sources = normalize_sources(paths)
    session_ids = sorted({source.session_id for source in sources})
    splits = build_session_splits(
        session_ids,
        seed=seed,
        train_fraction=train_fraction,
        val_fraction=val_fraction,
    )
    sources_by_session = {
        session_id: [source.to_dict() for source in sources if source.session_id == session_id]
        for session_id in session_ids
    }
    return {
        "schema_version": "dataset.manifest.v1",
        "dataset_name": dataset_name or paths[0].parent.name,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "seed": seed,
        "splits": splits,
        "session_ids": session_ids,
        "sources": [source.to_dict() for source in sources],
        "sources_by_session": sources_by_session,
    }


def build_manifest_output_path(first_path: Path) -> Path:
    return first_path.parent / "dataset-manifest.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a deterministic dataset manifest with session-level train/val/test splits."
    )
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--dataset-name")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    paths = [Path(path) for path in args.paths]
    manifest = build_dataset_manifest(
        paths,
        dataset_name=args.dataset_name,
        seed=args.seed,
        train_fraction=args.train_fraction,
        val_fraction=args.val_fraction,
    )
    output_path = (
        Path(args.output) if args.output else build_manifest_output_path(paths[0])
    )
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote dataset manifest to {output_path}")
