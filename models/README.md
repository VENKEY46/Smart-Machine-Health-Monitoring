# Model files

The two files directly in this folder are preserved upstream model artifacts.
The setup instructions do not load them.

Run `python -m backend.train_model` from the repository root to create your own
model, score range and version report in `models/generated/`. The bridge and
validation command use that generated model. Keep training and inference in the
same Python environment. Load only model files whose source you trust.

The index maps the training decision-score range to 0–100. It is not a
probability of failure, remaining life, or an engineering safety rating.
