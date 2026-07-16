from __future__ import annotations


def require_pyarrow():
    try:
        import pyarrow as pa  # type: ignore[import-not-found]
        import pyarrow.parquet as pq  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "pyarrow is required for Parquet recording and replay. Install natVR "
            "with `pip install -e .[dev]` or `pip install -e .` from natVR/."
        ) from exc
    return pa, pq


def require_sklearn():
    try:
        from sklearn.ensemble import RandomForestClassifier  # type: ignore[import-not-found]
        from sklearn.pipeline import make_pipeline  # type: ignore[import-not-found]
        from sklearn.preprocessing import StandardScaler  # type: ignore[import-not-found]
        from sklearn.svm import LinearSVC  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for model comparison. Install natVR with "
            "`pip install -e .[dev]` or `pip install -e .` from natVR/."
        ) from exc
    return RandomForestClassifier, make_pipeline, StandardScaler, LinearSVC
