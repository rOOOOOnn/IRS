# Interpolation Comparison

The main comparison is cross-sectional Leave-One-Tenor-Out validation. For each date and held-out
tenor, the curve is rebuilt without that market instrument. The held-out OIS is then repriced from
the curve and its implied par rate is compared with the original Bloomberg quote in basis points.

Interior nodes form the primary interpolation comparison. The shortest and longest available nodes
are classified as endpoint extrapolation and reported separately. A monthly robustness experiment
also removes 3M+6M, 2Y+3Y, and 4Y+5Y pairs.

Training and Validation both select `monotone_convex_forward` by interior-node RMSE. The method also
wins every Training curve-regime subgroup, so a regime-dependent switching rule offers no supported
benefit. The global method avoids artificial IRS MTM changes caused by switching interpolation
algorithms through time.

Detailed results are generated under `outputs/curve_validation/`.
