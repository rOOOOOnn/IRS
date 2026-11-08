"""Supported QuantLib interpolation frameworks."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import QuantLib as ql


class InterpolationMethod(StrEnum):
    LINEAR_ZERO = "linear_zero"
    LOG_LINEAR_DISCOUNT = "log_linear_discount"
    NATURAL_CUBIC_ZERO = "natural_cubic_zero"
    MONOTONE_CONVEX_FORWARD = "monotone_convex_forward"


def build_piecewise_curve(
    method: str | InterpolationMethod,
    reference_date: ql.Date,
    helpers: list[ql.RateHelper],
    day_counter: ql.DayCounter,
) -> Any:
    selected = InterpolationMethod(method)
    if selected == InterpolationMethod.MONOTONE_CONVEX_FORWARD:
        bootstrap = ql.IterativeBootstrap(
            accuracy=1.0e-12,
            maxAttempts=5,
            maxFactor=3.0,
            minFactor=3.0,
            maxEvaluations=500,
        )
        interpolator = ql.ConvexMonotone(0.3, 0.7, False)
        return ql.PiecewiseConvexMonotoneForward(
            reference_date,
            helpers,
            day_counter,
            bootstrap,
            interpolator,
        )
    constructors = {
        InterpolationMethod.LINEAR_ZERO: ql.PiecewiseLinearZero,
        InterpolationMethod.LOG_LINEAR_DISCOUNT: ql.PiecewiseLogLinearDiscount,
        InterpolationMethod.NATURAL_CUBIC_ZERO: ql.PiecewiseNaturalCubicZero,
    }
    return constructors[selected](reference_date, helpers, day_counter)
