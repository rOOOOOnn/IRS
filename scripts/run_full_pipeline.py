"""Compatibility entry point for the curve and pricing pipeline."""

if __package__:
    from .run_curve_pricing_pipeline import main
else:
    from run_curve_pricing_pipeline import main

if __name__ == "__main__":
    main()
