import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.analytics import calculate_kpis, classify_product_velocity, analyze_reorder_recommendations
from src.forecasting import (
    prepare_daily_demand_series,
    forecast_moving_average,
    forecast_exponential_smoothing,
    forecast_linear_trend,
    evaluate_forecast_accuracy
)

@pytest.fixture
def sample_inventory_data():
    products = pd.DataFrame([
        {
            "product_id": 1, "sku": "ELE-001", "product_name": "Earbuds",
            "category": "Electronics", "supplier": "Supplier A",
            "unit_cost": 20.0, "selling_price": 40.0, "current_stock": 50,
            "reorder_point": 15, "min_order_qty": 30, "supplier_lead_time_days": 7
        },
        {
            "product_id": 2, "sku": "APP-001", "product_name": "Jacket",
            "category": "Apparel", "supplier": "Supplier B",
            "unit_cost": 50.0, "selling_price": 100.0, "current_stock": 5,
            "reorder_point": 10, "min_order_qty": 20, "supplier_lead_time_days": 5
        },
        {
            "product_id": 3, "sku": "HKT-001", "product_name": "Blender",
            "category": "Home & Kitchen", "supplier": "Supplier C",
            "unit_cost": 30.0, "selling_price": 60.0, "current_stock": 0,
            "reorder_point": 12, "min_order_qty": 25, "supplier_lead_time_days": 10
        }
    ])

    dates = [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)]
    tx_list = []
    tx_id = 1

    # Product 1 sales
    for d in dates:
        tx_list.append({
            "transaction_id": tx_id, "product_id": 1, "sku": "ELE-001",
            "transaction_type": "Sale", "quantity": 5, "unit_price": 40.0,
            "total_amount": 200.0, "transaction_date": d.strftime("%Y-%m-%d"),
            "category": "Electronics", "unit_cost": 20.0
        })
        tx_id += 1

    # Product 2 sales
    for d in dates[:3]:
        tx_list.append({
            "transaction_id": tx_id, "product_id": 2, "sku": "APP-001",
            "transaction_type": "Sale", "quantity": 1, "unit_price": 100.0,
            "total_amount": 100.0, "transaction_date": d.strftime("%Y-%m-%d"),
            "category": "Apparel", "unit_cost": 50.0
        })
        tx_id += 1

    transactions = pd.DataFrame(tx_list)
    return products, transactions

def test_calculate_kpis(sample_inventory_data):
    products, transactions = sample_inventory_data
    kpis = calculate_kpis(products, transactions)

    assert kpis["total_skus"] == 3
    # Total inventory value = (50*20) + (5*50) + (0*30) = 1000 + 250 + 0 = 1250
    assert kpis["total_inventory_value"] == 1250.0
    assert kpis["low_stock_count"] == 2  # Product 2 (stock 5 <= ROP 10) and Product 3 (stock 0 <= ROP 12)
    assert kpis["out_of_stock_count"] == 1  # Product 3

    # Total Sales Revenue = (10 * 200) + (3 * 100) = 2000 + 300 = 2300
    assert kpis["total_sales_revenue"] == 2300.0

    # Total COGS = (50 * 20) + (3 * 50) = 1000 + 150 = 1150
    assert kpis["total_cogs"] == 1150.0

    # Turnover = 1150 / 1250 = 0.92
    assert kpis["inventory_turnover"] == 0.92

def test_kpis_zero_sales(sample_inventory_data):
    products, _ = sample_inventory_data
    empty_tx = pd.DataFrame(columns=["transaction_id", "product_id", "transaction_type", "quantity", "unit_price", "total_amount", "transaction_date"])
    kpis = calculate_kpis(products, empty_tx)

    assert kpis["total_sales_revenue"] == 0.0
    assert kpis["total_cogs"] == 0.0
    assert kpis["inventory_turnover"] == 0.0
    assert kpis["days_of_inventory_on_hand"] == float("inf")

def test_classify_product_velocity(sample_inventory_data):
    products, transactions = sample_inventory_data
    classified = classify_product_velocity(products, transactions)

    assert "velocity_class" in classified.columns
    # Product 1 has highest sales -> Fast-Moving
    p1 = classified[classified["product_id"] == 1].iloc[0]
    assert p1["velocity_class"] == "Fast-Moving"

    # Product 3 has 0 sales and 0 stock -> Non-Moving
    p3 = classified[classified["product_id"] == 3].iloc[0]
    assert p3["velocity_class"] == "Non-Moving"

def test_analyze_reorder_recommendations(sample_inventory_data):
    products, transactions = sample_inventory_data
    reorder_df = analyze_reorder_recommendations(products, transactions)

    assert len(reorder_df) == 3
    # Product 3 (out of stock) should have CRITICAL stockout risk
    p3 = reorder_df[reorder_df["product_id"] == 3].iloc[0]
    assert p3["stockout_risk"] == "CRITICAL"
    assert p3["recommended_order_qty"] > 0

def test_demand_forecasting(sample_inventory_data):
    _, transactions = sample_inventory_data
    daily_df = prepare_daily_demand_series(transactions, product_id=1)

    assert not daily_df.empty
    assert "date" in daily_df.columns
    assert "demand" in daily_df.columns

    # Test SMA forecast
    sma_fc = forecast_moving_average(daily_df, forecast_horizon_days=14, window_size=7)
    assert len(sma_fc) == 14
    assert sma_fc["forecast_demand"].iloc[0] > 0

    # Test Exponential Smoothing
    exp_fc = forecast_exponential_smoothing(daily_df, forecast_horizon_days=14, alpha=0.3)
    assert len(exp_fc) == 14
    assert exp_fc["forecast_demand"].iloc[0] > 0

    # Test Linear Trend
    trend_fc = forecast_linear_trend(daily_df, forecast_horizon_days=14)
    assert len(trend_fc) == 14
