"""Common loss statistics and zero-rate shock generators. No pricing logic lives here."""

from __future__ import annotations

import numpy as np

MODELS = ("HS", "EWMA", "PCA_MC")
OUTPUT_COLUMNS = [
    "Date",
    "Model",
    "Confidence_Level",
    "Forecast_Horizon",
    "VaR",
    "ES",
    "Forecast_As_Of",
]


def empirical_var_es(losses, alpha):
    x = np.sort(np.asarray(losses, dtype=float))
    if x.ndim != 1 or not x.size or not np.isfinite(x).all() or not 0 < alpha < 1:
        raise ValueError("Invalid finite loss sample or confidence level")
    n = len(x)
    var = float(x[int(np.ceil(alpha * n)) - 1])
    left = np.arange(n)
    weights = np.maximum(0.0, left + 1 - np.maximum(left, alpha * n))
    es = float(x @ weights / ((1 - alpha) * n))
    # Interface requires positive loss magnitudes; do not change the underlying loss sample.
    return max(0.0, var), max(0.0, es)


def generate_shocks(model, changes, config, rng):
    x = np.asarray(changes, dtype=float)
    if x.ndim != 2 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("Invalid rolling window")
    if model == "HS":
        return x.copy(), {"Scenario_Count": len(x)}
    if model == "EWMA":
        decay = config["ewma_decay"]
        covariance = np.outer(x[0], x[0])
        for dx in x[1:]:
            covariance = decay * covariance + (1 - decay) * np.outer(dx, dx)
    elif model == "PCA_MC":
        covariance = np.cov(x, rowvar=False)
    else:
        raise ValueError(f"Unknown model: {model}")
    values, vectors = np.linalg.eigh((covariance + covariance.T) / 2)
    scale = max(float(np.max(np.abs(values))), np.finfo(float).tiny)
    if values.min() < -1e-10 * scale:
        raise ValueError("Covariance is not positive semidefinite")
    order = np.argsort(values)[::-1]
    values, vectors = np.maximum(values[order], 0), vectors[:, order]
    k = config["pca_factors"] if model == "PCA_MC" else x.shape[1]
    explained = float(values[:k].sum() / values.sum()) if values.sum() else 1.0
    draws = rng.standard_normal((config["simulations"], k))
    shocks = (draws * np.sqrt(values[:k])) @ vectors[:, :k].T
    return shocks, {"Scenario_Count": len(shocks), "Explained_Variance": explained}
