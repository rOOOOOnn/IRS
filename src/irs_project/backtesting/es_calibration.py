
"""ES-VaR calibration diagnostic with gap-aware block bootstrap."""

from __future__ import annotations

import numpy as np
import pandas as pd


def es_identification(loss, var, es, confidence):
    """Calculate the ES component of joint VaR-ES identification."""

    loss = np.asarray(loss, dtype=float)
    var = np.asarray(var, dtype=float)
    es = np.asarray(es, dtype=float)

    if not (len(loss) == len(var) == len(es)):
        raise ValueError("Input lengths do not match")

    if not 0 < confidence < 1:
        raise ValueError("Invalid confidence level")

    if (
        not np.isfinite(loss).all()
        or not np.isfinite(var).all()
        or not np.isfinite(es).all()
        or np.any(es < var)
    ):
        raise ValueError("Invalid Loss, VaR or ES")

    alpha = 1.0 - confidence

    residual = (
        np.maximum(loss - var, 0.0) / alpha
        - (es - var)
    )

    return residual


def contiguous_residual_segments(group, confidence):
    """Split the residual sequence at missing/invalid forecasts."""

    group = group.sort_values("Date").copy()

    group["Date"] = pd.to_datetime(group["Date"])
    group["Forecast_As_Of"] = pd.to_datetime(
        group["Forecast_As_Of"]
    )

    segments = []
    current = []
    previous_date = None

    for row in group.itertuples(index=False):

        if not bool(row.Valid):
            if current:
                segments.append(np.asarray(current))
                current = []

            previous_date = None
            continue

        adjacent = (
            previous_date is not None
            and row.Forecast_As_Of == previous_date
        )

        if current and not adjacent:
            segments.append(np.asarray(current))
            current = []

        residual = es_identification(
            [row.Loss],
            [row.VaR],
            [row.ES],
            confidence
        )[0]

        current.append(float(residual))
        previous_date = row.Date

    if current:
        segments.append(np.asarray(current))

    return segments


def _equal_tailed_p(draws, observed):
    """Invert the linearly interpolated pivotal interval for H0: E[Z] = 0.

    Count ties on both sides, and bound either tail below by 1/(B+1)
    to avoid an estimated zero probability with B Monte Carlo draws.
    """
    ordered = np.sort(draws)
    count = len(ordered)
    left = np.searchsorted(ordered, observed, side="left")
    right = np.searchsorted(ordered, observed, side="right")
    if left < right:
        lower_tail = (right - 1) / (count - 1)
        upper_tail = 1 - left / (count - 1)
    else:
        # Interpolate between distinct order statistics using the same grid as np.quantile.
        rank = np.interp(observed, ordered, np.linspace(0, 1, count))
        lower_tail, upper_tail = rank, 1 - rank
    return round(min(1.0, 2 * max(1 / (count + 1), min(lower_tail, upper_tail))), 15)


def bootstrap_es_ci(
    group,
    confidence,
    block_length=10,
    simulations=2000,
    seed=5003
):
    """Estimate a 95% CI for the mean ES calibration moment.

    The gap-aware circular block bootstrap is exploratory and unconditional.
    """

    if block_length < 1 or simulations < 100:
        raise ValueError("Invalid bootstrap parameters")

    segments = contiguous_residual_segments(
        group, confidence
    )

    values = (
        np.concatenate(segments)
        if segments else np.array([])
    )

    n = len(values)

    if n < 40:
        return {
            "ES_Moment_Mean": np.nan,
            "ES_Moment_CI_Lower": np.nan,
            "ES_Moment_CI_Upper": np.nan,
            "ES_Moment_Symmetric_CI_Lower": np.nan,
            "ES_Moment_Symmetric_CI_Upper": np.nan,
            "ES_Bootstrap_p": np.nan,
            "ES_Bootstrap_Symmetric_p": np.nan,
            "ES_Segment_Count": len(segments)
        }

    observed_mean = float(values.mean())

    # Center the residuals under H0: E[Z] = 0.
    centered_segments = [
        segment - observed_mean
        for segment in segments
    ]

    starts = [
        (j, k)
        for j, segment in enumerate(segments)
        for k in range(len(segment))
    ]

    rng = np.random.default_rng(seed)
    bootstrap_means = np.empty(simulations)

    for b in range(simulations):

        sampled_blocks = []
        sampled_length = 0

        while sampled_length < n:

            index = rng.integers(len(starts))
            j, k = starts[index]

            segment = centered_segments[j]

            length = min(
                block_length,
                len(segment),
                n - sampled_length
            )

            indices = (
                k + np.arange(length)
            ) % len(segment)

            block = segment[indices]

            sampled_blocks.append(block)
            sampled_length += length

        sample = np.concatenate(sampled_blocks)
        bootstrap_means[b] = sample.mean()

    # Symmetric 95% interval based on centered bootstrap.
    radius = float(
        np.quantile(
            np.abs(bootstrap_means), 0.95
        )
    )

    q025, q975 = np.quantile(bootstrap_means, [0.025, 0.975])
    symmetric_p = (
        1 + np.count_nonzero(np.abs(bootstrap_means) >= abs(observed_mean))
    ) / (simulations + 1)

    return {
        "ES_Moment_Mean": observed_mean,
        "ES_Moment_CI_Lower": float(observed_mean - q975),
        "ES_Moment_CI_Upper": float(observed_mean - q025),
        "ES_Moment_Symmetric_CI_Lower": observed_mean - radius,
        "ES_Moment_Symmetric_CI_Upper": observed_mean + radius,
        "ES_Bootstrap_p": _equal_tailed_p(bootstrap_means, observed_mean),
        "ES_Bootstrap_Symmetric_p": float(symmetric_p),
        "ES_Segment_Count": len(segments),
    }
