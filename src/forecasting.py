import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def prepare_daily_demand_series(transactions_df, product_id=None, category=None):
    """
    Aggregates historical sales transactions into a continuous daily demand time series.
    Missing dates are filled with zero sales.
    """
    if transactions_df.empty:
        return pd.DataFrame(columns=["date", "demand"])

    tx_df = transactions_df.copy()
    tx_df["transaction_date"] = pd.to_datetime(tx_df["transaction_date"])
    sales_df = tx_df[tx_df["transaction_type"] == "Sale"]

    if product_id:
        sales_df = sales_df[sales_df["product_id"] == product_id]
    elif category and category != "All":
        sales_df = sales_df[sales_df["category"] == category]

    if sales_df.empty:
        return pd.DataFrame(columns=["date", "demand"])

    daily = sales_df.groupby("transaction_date")["quantity"].sum().reset_index()
    daily.rename(columns={"transaction_date": "date", "quantity": "demand"}, inplace=True)

    # Reindex to complete continuous date sequence
    min_date = daily["date"].min()
    max_date = daily["date"].max()
    full_idx = pd.date_range(start=min_date, end=max_date, freq="D")

    daily = daily.set_index("date").reindex(full_idx, fill_value=0).reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    return daily

def forecast_moving_average(daily_df, forecast_horizon_days=30, window_size=14):
    """
    Simple Moving Average (SMA) Demand Forecast.
    Assumes recent average demand is representative of upcoming demand.
    """
    if len(daily_df) < window_size:
        avg_val = daily_df["demand"].mean() if not daily_df.empty else 0.0
    else:
        avg_val = daily_df["demand"].iloc[-window_size:].mean()

    last_date = daily_df["date"].max()
    future_dates = [last_date + timedelta(days=i) for i in range(1, forecast_horizon_days + 1)]

    forecast_df = pd.DataFrame({
        "date": future_dates,
        "forecast_demand": [round(float(avg_val), 2)] * forecast_horizon_days,
        "lower_bound": [max(0.0, round(float(avg_val * 0.8), 2))] * forecast_horizon_days,
        "upper_bound": [round(float(avg_val * 1.2), 2)] * forecast_horizon_days,
        "method": "Simple Moving Average (SMA)"
    })
    return forecast_df

def forecast_exponential_smoothing(daily_df, forecast_horizon_days=30, alpha=0.3):
    """
    Single Exponential Smoothing (SES) Demand Forecast.
    Applies exponentially decreasing weights to older demand observations.
    """
    if daily_df.empty:
        return pd.DataFrame()

    series = daily_df["demand"].values
    smoothed = [series[0]]
    for t in range(1, len(series)):
        val = alpha * series[t] + (1 - alpha) * smoothed[-1]
        smoothed.append(val)

    last_forecast = smoothed[-1]
    last_date = daily_df["date"].max()
    future_dates = [last_date + timedelta(days=i) for i in range(1, forecast_horizon_days + 1)]

    # Standard deviation of residuals for confidence band
    residuals = series - np.array(smoothed)
    std_err = np.std(residuals) if len(residuals) > 1 else 1.0

    forecast_df = pd.DataFrame({
        "date": future_dates,
        "forecast_demand": [round(float(last_forecast), 2)] * forecast_horizon_days,
        "lower_bound": [max(0.0, round(float(last_forecast - 1.645 * std_err), 2))] * forecast_horizon_days,
        "upper_bound": [round(float(last_forecast + 1.645 * std_err), 2)] * forecast_horizon_days,
        "method": f"Exponential Smoothing (alpha={alpha})"
    })
    return forecast_df

def forecast_linear_trend(daily_df, forecast_horizon_days=30):
    """
    Linear Trend Demand Forecast using Ordinary Least Squares regression.
    Captures overall upward or downward growth trajectory.
    """
    if len(daily_df) < 5:
        return forecast_moving_average(daily_df, forecast_horizon_days)

    y = daily_df["demand"].values
    x = np.arange(len(y))

    # OLS fit: y = slope * x + intercept
    slope, intercept = np.polyfit(x, y, 1)

    future_x = np.arange(len(y), len(y) + forecast_horizon_days)
    future_y = slope * future_x + intercept
    future_y = np.maximum(0, future_y)  # Non-negative demand constraint

    last_date = daily_df["date"].max()
    future_dates = [last_date + timedelta(days=i) for i in range(1, forecast_horizon_days + 1)]

    # Calculate residual error bound
    fitted_y = slope * x + intercept
    residuals = y - fitted_y
    std_err = np.std(residuals) if len(residuals) > 1 else 1.0

    forecast_df = pd.DataFrame({
        "date": future_dates,
        "forecast_demand": np.round(future_y, 2),
        "lower_bound": np.round(np.maximum(0, future_y - 1.645 * std_err), 2),
        "upper_bound": np.round(future_y + 1.645 * std_err, 2),
        "method": f"Linear Trend (Slope: {slope:.3f})"
    })
    return forecast_df

def evaluate_forecast_accuracy(daily_df, method="sma", window_size=14, alpha=0.3, test_days=30):
    """
    Backtests the selected forecasting model against historical test data.
    Calculates MAE, RMSE, and MAPE metrics.
    """
    if len(daily_df) <= test_days + 14:
        return {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "status": "Insufficient historical data for backtesting"}

    train_df = daily_df.iloc[:-test_days].copy()
    test_df = daily_df.iloc[-test_days:].copy()

    if method == "sma":
        fc = forecast_moving_average(train_df, forecast_horizon_days=test_days, window_size=window_size)
    elif method == "exp":
        fc = forecast_exponential_smoothing(train_df, forecast_horizon_days=test_days, alpha=alpha)
    else:
        fc = forecast_linear_trend(train_df, forecast_horizon_days=test_days)

    actuals = test_df["demand"].values
    preds = fc["forecast_demand"].values

    mae = float(np.mean(np.abs(actuals - preds)))
    rmse = float(np.sqrt(np.mean((actuals - preds) ** 2)))

    # MAPE with zero-division safeguard
    non_zero_mask = actuals > 0
    if np.sum(non_zero_mask) > 0:
        mape = float(np.mean(np.abs((actuals[non_zero_mask] - preds[non_zero_mask]) / actuals[non_zero_mask])) * 100)
    else:
        mape = 0.0

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "test_days": test_days,
        "status": "Successful backtest"
    }

def get_forecasting_assumptions():
    """
    Returns markdown documentation explaining forecasting models, parameters, and limitations.
    """
    return """
### 📌 Demand Forecasting Assumptions & Limitations

#### 1. Forecasting Methodologies
- **Simple Moving Average (SMA)**: Computes average demand over an $N$-day sliding window. Best for stable, baseline inventory items without trend or seasonality.
- **Single Exponential Smoothing (SES)**: Assigns exponentially decaying weights ($\alpha=0.3$) to historical demand. Responsive to recent demand shifts while smoothing random noise.
- **Linear Trend Regression**: Fits an Ordinary Least Squares (OLS) slope to capture long-term expansion or contraction trajectories.

#### 2. Core Business Assumptions
- **Constant Lead Time**: Supplier lead times remain within expected historical variance.
- **Stationary Customer Demand**: Unfulfilled demand or stockout periods reflect zero sales rather than lost latent demand.
- **Non-Negative Constraint**: All projected demand quantities are bounded below by $0.0$.

#### 3. Model Limitations
- **External Factors**: Does not account for external macroeconomic shocks, localized promotional campaigns, or competitor pricing shifts.
- **Lumpy Demand**: High-variance, intermittent purchases (e.g. specialized industrial tools) may exhibit elevated Mean Absolute Percentage Error (MAPE).
"""
