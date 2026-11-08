# Final Curve Method Recommendation

- Training RMSE winner: `monotone_convex_forward`.
- Validation RMSE winner: `monotone_convex_forward`.
- Validation supports the Training winner: `True`.
- Selected global method: `monotone_convex_forward`.
- Test results were not used for selection.
- The main comparison uses interior LOTO nodes; endpoints are reported separately.
- Regime-dependent switching is not adopted as the primary method because method switches can create artificial MTM changes; the mapping below remains diagnostic.

## Frozen Training Regime Thresholds

- Flat absolute slope threshold: 0.00117080.
- Absolute curvature threshold: 0.00236940.

## Training Diagnostic Best Method by Regime

- FLAT: `monotone_convex_forward`
- HUMPED: `monotone_convex_forward`
- INVERTED: `monotone_convex_forward`
- TROUGH: `monotone_convex_forward`
- UPWARD: `monotone_convex_forward`

## Limitations

Contract and OIS cash-flow conventions not present in the disclosure remain explicit research assumptions. LOTO measures cross-sectional interpolation performance and does not prove that one method is universally superior.
