"""Shared five-feature calculation for recorded and live vibration windows."""
import numpy as np
import pandas as pd
from scipy.fft import rfft, rfftfreq
from scipy.stats import kurtosis

FEATURE_NAMES = ["rms", "kurtosis", "crest_factor", "std", "peak_frequency_hz"]


def compute_window_features(w, fs_actual):
    w = np.asarray(w, dtype=float)
    if w.ndim != 1 or len(w) < 2 or not np.isfinite(w).all():
        raise ValueError("A window must contain at least two finite magnitude samples.")
    if not np.isfinite(fs_actual) or fs_actual <= 0:
        raise ValueError("Sample rate must be positive and finite.")
    rms = np.sqrt(np.mean(w ** 2))
    std = np.std(w)
    constant = std < 1e-12
    kurt = 0.0 if constant else float(kurtosis(w))
    crest = np.max(np.abs(w)) / (rms + 1e-9)
    spectrum = np.abs(rfft(w - np.mean(w)))
    freqs = rfftfreq(len(w), d=1 / fs_actual)
    peak = 0.0 if constant else float(freqs[np.argmax(spectrum)])
    features = np.array([rms, kurt, crest, std, peak], dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Feature calculation produced a non-finite value.")
    return features.tolist()


def extract_features(path, window_seconds=5.0, min_samples=40):
    if not np.isfinite(window_seconds) or window_seconds <= 0 or min_samples < 2:
        raise ValueError("Use a positive window duration and at least two samples.")
    df = pd.read_csv(path)
    required = {"timestamp", "ax", "ay", "az"}
    if not required.issubset(df.columns):
        raise ValueError("CSV must contain timestamp, ax, ay and az.")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        raise ValueError("CSV contains a missing or invalid timestamp.")
    axes = df[["ax", "ay", "az"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(axes.to_numpy()).all():
        raise ValueError("CSV contains a missing or non-finite acceleration value.")
    if df["timestamp"].duplicated().any():
        raise ValueError("CSV contains duplicate timestamps; review the recording first.")
    mag = pd.Series(np.sqrt((axes ** 2).sum(axis=1)).to_numpy(), index=df["timestamp"])
    feats = []
    for _, window in mag.sort_index().resample(pd.Timedelta(seconds=window_seconds)):
        if len(window) >= min_samples:
            feats.append(compute_window_features(window.to_numpy(), len(window) / window_seconds))
    if not feats:
        raise ValueError("No window has enough samples; provide a longer recording.")
    return np.asarray(feats)
