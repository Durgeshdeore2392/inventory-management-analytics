import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def calculate_kpis(products_df, transactions_df, time_window_days=365):
    """
    Calculates executive inventory KPIs over the specified time window.
    """
    if products_df.empty:
        return {
            "total_skus": 0,
            "total_inventory_value": 0.0,
            "total_selling_value": 0.0,
            "low_stock_count": 0,
            "out_of_stock_count": 0,
            "total_sales_revenue": 0.0,
            "total_cogs": 0.0,
            "inventory_turnover": 0.0,
            "days_of_inventory_on_hand": 0.0
        }

    total_skus = len(products_df)
    products_df["inventory_value"] = products_df["current_stock"] * products_df["unit_cost"]
    products_df["selling_value"] = products_df["current_stock"] * products_df["selling_price"]

    total_inventory_value = float(products_df["inventory_value"].sum())
    total_selling_value = float(products_df["selling_value"].sum())

    out_of_stock_count = int((products_df["current_stock"] == 0).sum())
    low_stock_count = int((products_df["current_stock"] <= products_df["reorder_point"]).sum())

    # Filter sales transactions within window
    if not transactions_df.empty:
        tx_df = transactions_df.copy()
        tx_df["transaction_date"] = pd.to_datetime(tx_df["transaction_date"])
        
        cutoff_date = datetime.now() - timedelta(days=time_window_days)
        sales_df = tx_df[(tx_df["transaction_type"] == "Sale") & (tx_df["transaction_date"] >= cutoff_date)]

        total_sales_revenue = float(sales_df["total_amount"].sum())
        
        # Calculate Cost of Goods Sold (COGS)
        # Merge with unit_cost from products_df if available
        if "unit_cost" in sales_df.columns:
            total_cogs = float((sales_df["quantity"] * sales_df["unit_cost"]).sum())
        else:
            merged_sales = sales_df.merge(products_df[["product_id", "unit_cost"]], on="product_id", how="left")
            total_cogs = float((merged_sales["quantity"] * merged_sales["unit_cost"]).sum())
    else:
        total_sales_revenue = 0.0
        total_cogs = 0.0

    # Inventory Turnover = COGS / Average Inventory Value
    # Using current inventory value as proxy for average inventory
    avg_inventory_value = max(total_inventory_value, 1.0)
    inventory_turnover = round(total_cogs / avg_inventory_value, 2) if total_cogs > 0 else 0.0

    # Days of Inventory on Hand (DOH) = 365 / Inventory Turnover
    if inventory_turnover > 0:
        days_on_hand = round((avg_inventory_value / (total_cogs / time_window_days)), 1)
    else:
        days_on_hand = float("inf") if total_inventory_value > 0 else 0.0

    return {
        "total_skus": total_skus,
        "total_inventory_value": total_inventory_value,
        "total_selling_value": total_selling_value,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_sales_revenue": total_sales_revenue,
        "total_cogs": total_cogs,
        "inventory_turnover": inventory_turnover,
        "days_of_inventory_on_hand": days_on_hand
    }

def classify_product_velocity(products_df, transactions_df, window_days=90):
    """
    Classifies products into Fast-Moving, Normal, Slow-Moving, and Non-Moving (Dead Stock).
    Based on sales volume over the given window.
    """
    if products_df.empty:
        return products_df

    df = products_df.copy()
    
    if transactions_df.empty:
        df["velocity_class"] = "Non-Moving"
        df["90d_sales_qty"] = 0
        return df

    tx_df = transactions_df.copy()
    tx_df["transaction_date"] = pd.to_datetime(tx_df["transaction_date"])
    
    max_date = tx_df["transaction_date"].max()
    cutoff_date = max_date - timedelta(days=window_days)

    sales_df = tx_df[(tx_df["transaction_type"] == "Sale") & (tx_df["transaction_date"] >= cutoff_date)]
    sales_by_prod = sales_df.groupby("product_id")["quantity"].sum().reset_index()
    sales_by_prod.rename(columns={"quantity": "sales_qty_90d"}, inplace=True)

    df = df.merge(sales_by_prod, on="product_id", how="left")
    df["sales_qty_90d"] = df["sales_qty_90d"].fillna(0)

    # Velocity classification boundaries using percentiles among active items
    active_sales = df[df["sales_qty_90d"] > 0]["sales_qty_90d"]

    if not active_sales.empty:
        p80 = np.percentile(active_sales, 80)
        p30 = np.percentile(active_sales, 30)

        def assign_class(row):
            qty = row["sales_qty_90d"]
            stock = row["current_stock"]
            if qty == 0:
                return "Dead Stock" if stock > 0 else "Non-Moving"
            elif qty >= p80:
                return "Fast-Moving"
            elif qty <= p30:
                return "Slow-Moving"
            else:
                return "Normal"

        df["velocity_class"] = df.apply(assign_class, axis=1)
    else:
        df["velocity_class"] = "Non-Moving"

    return df

def analyze_reorder_recommendations(products_df, transactions_df):
    """
    Calculates statistical safety stock, dynamic reorder point (ROP),
    and recommended order quantity for every product.
    
    Formulas used:
    - Daily Demand Mean (mu_d) & Std Dev (sigma_d) over 90 days
    - Lead Time (L) in days
    - Safety Stock (SS) = Z * sigma_d * sqrt(L)  where Z = 1.65 (95% service level)
    - Dynamic ROP = (mu_d * L) + SS
    - Reorder Quantity = max(0, min_order_qty, (ROP + min_order_qty - current_stock))
    """
    if products_df.empty:
        return pd.DataFrame()

    df = products_df.copy()

    # Calculate 90-day daily demand statistics per product
    if not transactions_df.empty:
        tx_df = transactions_df.copy()
        tx_df["transaction_date"] = pd.to_datetime(tx_df["transaction_date"])
        max_date = tx_df["transaction_date"].max()
        cutoff_date = max_date - timedelta(days=90)

        sales_df = tx_df[(tx_df["transaction_type"] == "Sale") & (tx_df["transaction_date"] >= cutoff_date)]

        # Daily sales aggregation
        daily_sales = sales_df.groupby(["product_id", "transaction_date"])["quantity"].sum().reset_index()

        stats = daily_sales.groupby("product_id")["quantity"].agg(
            daily_demand_avg="mean",
            daily_demand_std="std",
            total_sold_90d="sum"
        ).reset_index()

        stats["daily_demand_avg"] = stats["daily_demand_avg"] / 1.0
        stats["daily_demand_std"] = stats["daily_demand_std"].fillna(0.0)

        df = df.merge(stats, on="product_id", how="left")
        df["daily_demand_avg"] = df["daily_demand_avg"].fillna(0.0)
        df["daily_demand_std"] = df["daily_demand_std"].fillna(0.0)
        df["total_sold_90d"] = df["total_sold_90d"].fillna(0)
    else:
        df["daily_demand_avg"] = 0.0
        df["daily_demand_std"] = 0.0
        df["total_sold_90d"] = 0

    # Service factor Z for 95% cycle service level
    Z = 1.65

    recommendations = []
    for _, row in df.iterrows():
        l_days = row["supplier_lead_time_days"]
        mu_d = row["daily_demand_avg"]
        sigma_d = row["daily_demand_std"]
        stock = row["current_stock"]
        moq = row["min_order_qty"]

        # Statistical Safety Stock
        safety_stock = int(np.ceil(Z * sigma_d * np.sqrt(max(1, l_days))))
        if safety_stock == 0 and mu_d > 0:
            safety_stock = int(np.ceil(mu_d * l_days * 0.5))

        # Dynamic Reorder Point
        calc_rop = int(np.ceil((mu_d * l_days) + safety_stock))
        final_rop = max(calc_rop, row["reorder_point"])

        # Stockout Risk Flag
        days_of_stock = stock / mu_d if mu_d > 0 else 999.0
        is_low_stock = stock <= final_rop
        stockout_risk = "CRITICAL" if stock == 0 else ("HIGH" if days_of_stock < l_days else ("MEDIUM" if is_low_stock else "LOW"))

        # Recommended Purchase Order Quantity
        if is_low_stock:
            reorder_qty = max(moq, (final_rop + moq) - stock)
        else:
            reorder_qty = 0

        estimated_cost = round(reorder_qty * row["unit_cost"], 2)

        recommendations.append({
            "product_id": row["product_id"],
            "sku": row["sku"],
            "product_name": row["product_name"],
            "category": row["category"],
            "supplier": row["supplier"],
            "current_stock": stock,
            "configured_rop": row["reorder_point"],
            "dynamic_rop": final_rop,
            "safety_stock": safety_stock,
            "lead_time_days": l_days,
            "daily_avg_demand": round(mu_d, 2),
            "days_of_stock": round(days_of_stock, 1) if days_of_stock < 900 else "N/A",
            "stockout_risk": stockout_risk,
            "recommended_order_qty": int(reorder_qty),
            "unit_cost": row["unit_cost"],
            "estimated_order_cost": estimated_cost
        })

    return pd.DataFrame(recommendations)
