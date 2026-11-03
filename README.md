# RMSC5003 Interest Rate Swaps Project

This repository contains market data and reference materials for our RMSC5003 group project on SOFR interest rate swaps (IRS). Analysis code, results, and presentation materials will be added as the project develops.

## Repository Structure

```text
IRS/
├── data/
│   ├── raw_exports/       # Original grid-based Excel exports
│   └── market_series/     # Named SOFR and USD SOFR market series
├── references/            # Reading materials and market documentation
└── README.md
```

## Data

- `data/raw_exports/` contains the original `grid_*.xlsx` files.
- `data/market_series/` contains the named SOFR index, rate, and tenor files.
- Data files are included in the repository so that every group member can access the same inputs.

## References

The `references/` directory contains background reading on SOFR interest rate swaps, OTC clearing, and margin methodology from industry sources.

## Getting Started

Clone the repository:

```bash
git clone https://github.com/rOOOOOnn/IRS.git
cd IRS
```

Create a separate branch before making substantial changes:

```bash
git switch -c your-name/short-description
```

Commit your work, push the branch, and open a pull request on GitHub for review.

## Collaboration

The repository is public, so anyone with the link can view and download it. Group members need collaborator access from the repository owner before they can push changes directly.

