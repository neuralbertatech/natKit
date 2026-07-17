# ML Workspace

Dataset and model workflow for EMG + IMU gesture classification.

## Scope
- Data capture and labeling tools.
- Feature extraction pipeline.
- Baseline model training and evaluation.
- Export runtime-friendly model artifacts.

## Baseline Plan
- Window: `200 ms` with overlap.
- Features: `MAV`, `RMS`, `WL`, `ZC`, `SSC` + IMU orientation features.
- Compare: `LDA`, `SVM`, `RandomForest`.

## Initial Deliverables
- Reproducible training script.
- Confusion matrix + cross-session validation output.
- Serialized model metadata (`model_version`, class map, feature config).
