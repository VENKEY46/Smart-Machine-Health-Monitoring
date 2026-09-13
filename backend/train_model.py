"""Train locally from the team baseline; no downloaded model is loaded."""
import argparse
import json
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from backend.settings import MODEL_DIR, ROOT
from feature_extraction import FEATURE_NAMES, extract_features


def train(baseline, model_dir):
    X = extract_features(baseline)
    if len(X) < 2:
        raise ValueError("At least two baseline windows are needed for training.")
    model = IsolationForest(n_estimators=200, contamination=0.03, random_state=42)
    model.fit(X)
    scores = model.decision_function(X)
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / "isolation_forest_model.pkl")
    np.save(model_dir / "score_range.npy", [scores.min(), scores.max()])
    report = {"baseline_file": Path(baseline).name, "baseline_windows": len(X),
              "features": FEATURE_NAMES, "window_seconds": 5, "min_samples": 40,
              "baseline_score_min": float(scores.min()), "baseline_score_max": float(scores.max()),
              "baseline_flagged_fraction": float((model.predict(X) == -1).mean()),
              "random_state": 42, "contamination": 0.03,
              "versions": {p: version(p) for p in ["numpy", "pandas", "scipy", "scikit-learn", "joblib"]}}
    (model_dir / "training_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "baseline_normal.csv")
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args()
    print(json.dumps(train(args.baseline, args.model_dir), indent=2))


if __name__ == "__main__":
    main()
