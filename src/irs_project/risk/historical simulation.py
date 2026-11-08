#!/usr/bin/env python
# coding: utf-8

# In[43]:


# ============================================================
# 1. Parameters
# ============================================================

import numpy as np
import pandas as pd

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "rOOOOOnn/IRS/main/data/processed/"
)


NOTIONAL = 10_000_000       # Notional: USD 10 million
FIXED_RATE = 0.03356        # Fixed rate: 3.356%
SIDE = "payer"             # payer: pay fixed, receive floating
                           # receiver: receive fixed, pay floating

WINDOW = 500               # Number of historical changes
CONFIDENCE_LEVELS = [0.95, 0.99]

# None: use the latest available date
# Alternatively, specify a date, e.g. "2023-05-31"
AS_OF_DATE = None

RATE_COLUMNS = [
    "OIS_1Y", "OIS_2Y", "OIS_3Y", "OIS_4Y", "OIS_5Y"
]

# ============================================================
# 2. Load and validate data
# ============================================================

# Load the 1Y–5Y par swap rates
# Pandas will raise an error if a required column is missing
annual_quotes = pd.read_csv(
    BASE_URL + "ois_curve_inputs_5y.csv",
    parse_dates=["Date"],
    index_col="Date"
).sort_index()[RATE_COLUMNS]


# Keep observations up to the specified valuation date
if AS_OF_DATE is not None:
    annual_quotes = annual_quotes.loc[:AS_OF_DATE]


# Ensure all quotes are numeric
annual_quotes = annual_quotes.apply(
    pd.to_numeric, errors="raise"
)


# Load the full set of quote dates to identify skipped observations
wide_dates = pd.read_csv(
    BASE_URL + "ois_par_rates_wide.csv",
    usecols=["Date"],
    parse_dates=["Date"]
)["Date"]


# Basic data validation
if annual_quotes.index.has_duplicates or wide_dates.duplicated().any():
    raise ValueError("Duplicate dates detected.")

if len(annual_quotes) < 2:
    raise ValueError("Insufficient curve observations.")

if not np.isfinite(annual_quotes.to_numpy()).all():
    raise ValueError("Quotes contain missing or non-finite values.")

# Rates in the processed files are already expressed as decimals
# Do not divide them by 100 again


print(
    f"Loaded {len(annual_quotes):,} curves: "
    f"{annual_quotes.index.min().date()} "
    f"to {annual_quotes.index.max().date()}"
)

display(annual_quotes.tail())


# In[44]:


# ============================================================
# 3. Extract historical one-observation-day rate changes
# ============================================================

# Locate complete-curve dates within the full set of quote dates
all_dates = pd.DatetimeIndex(wide_dates).sort_values()
positions = all_dates.get_indexer(annual_quotes.index)

if (positions < 0).any():
    raise ValueError("Dates are inconsistent between the two datasets.")

# Keep changes only between consecutive observed quote dates
valid = np.insert(np.diff(positions) == 1, 0, False)

# Use absolute rate changes rather than percentage returns
historical_changes = annual_quotes.diff().loc[valid].dropna()

# Select the most recent WINDOW valid changes
if len(historical_changes) < WINDOW:
    raise ValueError(
        f"Fewer than {WINDOW} valid historical changes are available."
    )

historical_changes = historical_changes.tail(WINDOW)

# Current valuation date and par swap curve
current_date = annual_quotes.index[-1]
current_quotes = annual_quotes.iloc[-1].to_numpy(dtype=float)


# In[45]:


# ============================================================
# 4. Bootstrap discount factors from annual par swap rates
# ============================================================

def bootstrap_discount_factors(par_rates):
    # Convert inputs to a two-dimensional floating-point array
    # Each row represents a scenario; each column represents a tenor
    rates = np.atleast_2d(
        np.asarray(par_rates, dtype=float)
    )

    # Validate inputs
    if rates.shape[1] != 5:
        raise ValueError("Five annual quotes from 1Y to 5Y are required.")

    if not np.isfinite(rates).all() or (rates <= -1).any():
        raise ValueError("Quotes are invalid or incompatible with the formula.")

    # Initialize discount factors
    dfs = np.zeros_like(rates)

    for j in range(5):
        # Sum the discount factors for preceding years
        previous_sum = dfs[:, :j].sum(axis=1)

        # Apply the bootstrap recursion
        dfs[:, j] = (
            1 - rates[:, j] * previous_sum
        ) / (1 + rates[:, j])

    # Validate the resulting discount factors
    if not np.isfinite(dfs).all() or (dfs <= 0).any():
        raise ValueError("Bootstrapping produced invalid discount factors.")

    return dfs


# In[46]:


# ============================================================
# 5. Swap valuation
# ============================================================

def price_swap(par_rates, notional, fixed_rate, side):
    # Simplified spot-start, five-year OIS with annual payments
    # Accrual factors are assumed to equal one
    dfs = bootstrap_discount_factors(par_rates)

    # Present values of the floating and fixed legs
    pv_float = notional * (1 - dfs[:, -1])
    pv_fixed = notional * fixed_rate * dfs.sum(axis=1)

    value = pv_float - pv_fixed

    if side == "payer":
        return value
    elif side == "receiver":
        return -value
    else:
        raise ValueError("side must be 'payer' or 'receiver'.")


# Extract the value for the single current-curve scenario
current_value = price_swap(
    current_quotes, NOTIONAL, FIXED_RATE, SIDE
)[0]


# In[47]:


# ============================================================
# 6. Historical scenarios and losses
# ============================================================

# Add each historical vector of rate changes to the current curve
scenario_quotes = (
    current_quotes + historical_changes.to_numpy()
)

# Revalue the swap under every scenario
scenario_values = price_swap(
    scenario_quotes, NOTIONAL, FIXED_RATE, SIDE
)

# Positive values indicate losses; negative values indicate profits
losses = current_value - scenario_values


# In[48]:


# ============================================================
# 7. Calculate VaR and ES
# ============================================================

def calculate_var_es(losses, confidence):
    x = np.sort(np.asarray(losses, dtype=float))

    if x.ndim != 1 or x.size == 0 or not np.isfinite(x).all():
        raise ValueError(
            "Losses must be a non-empty, one-dimensional array "
            "of finite numbers."
        )

    if not 0 < confidence < 1:
        raise ValueError("The confidence level must be between zero and one.")

    # VaR: the ceil(confidence × sample size)-th ordered loss
    var = x[int(np.ceil(confidence * len(x))) - 1]

    # ES: average loss in the worst tail, with fractional boundary weighting
    tail_size = (1 - confidence) * len(x)

    # Correct floating-point errors near integer tail sizes
    if np.isclose(tail_size, round(tail_size), rtol=0, atol=1e-10):
        tail_size = float(round(tail_size))

    whole = int(np.floor(tail_size))
    fraction = tail_size - whole

    tail_sum = x[-whole:].sum() if whole > 0 else 0.0

    if fraction > 0:
        tail_sum += fraction * x[-whole - 1]

    es = tail_sum / tail_size

    return float(var), float(es)


# Create one result row per confidence level
results = pd.DataFrame(
    [
        [confidence, *calculate_var_es(losses, confidence)]
        for confidence in CONFIDENCE_LEVELS
    ],
    columns=["Confidence", "VaR_USD", "ES_USD"]
)



# In[49]:


# ============================================================
# 8. Scenario details and numerical checks
# ============================================================

scenario_results = pd.DataFrame({
    "Historical_Shock_End_Date": historical_changes.index,
    "Scenario_Value_USD": scenario_values,
    "Loss_USD": losses
})

# Verify that bootstrapped discount factors reproduce current par quotes
dfs = bootstrap_discount_factors(current_quotes)[0]
repriced_par = (1 - dfs) / np.cumsum(dfs)

np.testing.assert_allclose(
    repriced_par, current_quotes, atol=1e-12, rtol=0
)

# ES must not be below VaR at the same confidence level
assert (results["ES_USD"] >= results["VaR_USD"] - 1e-8).all()


# In[50]:


# ============================================================
# 9. Display results
# ============================================================

print(f"Valuation date: {current_date.date()}")
print(f"Notional: USD {NOTIONAL:,.0f}")
print(f"Fixed rate: {FIXED_RATE:.3%}; position: {SIDE}")
print(f"Number of historical scenarios: {len(losses)}")
print(f"Current model value: USD {current_value:,.2f}")

display(
    results.style.format({
        "Confidence": "{:.0%}",
        "VaR_USD": "{:,.2f}",
        "ES_USD": "{:,.2f}"
    })
)

print("The five largest scenario losses:")

display(
    scenario_results.nlargest(5, "Loss_USD").style.format({
        "Scenario_Value_USD": "{:,.2f}",
        "Loss_USD": "{:,.2f}"
    })
)


# In[51]:


# ============================================================
# 10. Plot the loss distribution
# ============================================================

fig, ax = plt.subplots(figsize=(10, 5))

# Express losses in USD thousands
ax.hist(
    losses / 1000,
    bins=35,
    color="skyblue",
    edgecolor="white"
)

# Use a different color for each confidence level
for color, row in zip(
    ["orange", "red"],
    results.itertuples(index=False)
):
    ax.axvline(
        row.VaR_USD / 1000,
        color=color,
        linestyle="--",
        label=f"{row.Confidence:.0%} VaR"
    )

    ax.axvline(
        row.ES_USD / 1000,
        color=color,
        linestyle=":",
        label=f"{row.Confidence:.0%} ES"
    )

ax.set(
    title=f"Historical Simulation ({current_date.date()})",
    xlabel="Loss (USD thousands)",
    ylabel="Number of scenarios"
)

ax.legend()
plt.tight_layout()
plt.show()


# In[52]:


# Save numerical results
results.to_csv("historical_var_es.csv", index=False)
scenario_results.to_csv("historical_scenarios.csv", index=False)


# In[53]:


from pathlib import Path

save_path = Path.home() / "Desktop" / "historical_var_es.csv"

results.to_csv(save_path, index=False)

print(f"已保存到：{save_path}")


# In[ ]:




