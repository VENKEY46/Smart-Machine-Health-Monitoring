"""Evaluate the included fault recording with a locally trained model."""
import argparse
import json
from pathlib import Path

import joblib

from backend.settings import MODEL_PATH, ROOT
from feature_extraction import extract_features


def evaluate(recording, model_path):
    if not Path(model_path).exists():
        raise FileNotFoundError("Run python -m backend.train_model first.")
    model = joblib.load(model_path)  # Load only the model you trained locally.
    X = extract_features(recording)
    scores = model.decision_function(X)
    return {"recording": Path(recording).name, "windows": len(X),
            "flagged_windows": int((model.predict(X) == -1).sum()),
            "flagged_fraction": float((model.predict(X) == -1).mean()),
            "score_min": float(scores.min()), "score_mean": float(scores.mean()),
            "score_max": float(scores.max()),
            "scope": "One included fault recording; not a general accuracy estimate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", type=Path, default=ROOT / "fault_imbalance.csv")
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.recording, args.model), indent=2))


if __name__ == "__main__":
    main()
