# Curve Validation Design

## Time Split and Cross-Sectional Holdout

The chronological Training, Validation, Transition, and Test periods remain those in
`config/project.yaml`. LOTO is an additional within-date cross-sectional experiment and does not
replace the time split.

Curve-shape thresholds use only Training data:

- slope = 5Y par rate - 1Y par rate;
- curvature = 2 × 3Y par rate - 1Y par rate - 5Y par rate;
- flat threshold = Training 20th percentile of absolute slope;
- curvature threshold = Training 80th percentile of absolute curvature.

The frozen thresholds classify Validation and Test dates as upward, flat, inverted, humped, or
trough-shaped. Small subgroups are marked as insufficient when below the configured sample minimum.

## Quality Controls

- 87,252 of 87,252 single-tenor holdout combinations succeeded.
- 2,472 of 2,472 multi-tenor robustness observations succeeded.
- All selected daily curves calibrated successfully.
- Daily market-instrument calibration errors are recorded rather than silently discarded.
- Monthly forward-rate samples are checked against broad configured diagnostic bounds.
- Test results are reported only after the Validation-based method choice is frozen.
