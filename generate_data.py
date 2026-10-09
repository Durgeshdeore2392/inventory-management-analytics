import pandas as pd
import numpy as np
import datetime
import os

def generate_inventory_dataset():
    np.random.seed(42)

    categories = {
        "Electronics": ["ELE", ["Wireless Earbuds", "Gaming Mouse", "4K Monitor", "Mechanical Keyboard", "USB-C Hub", "Smart Watch", "Portable Powerbank", "Bluetooth Speaker", "HD Webcam", "Noise-Canceling Headphones"]],
        "Apparel & Gear": ["APP", ["Thermal Jacket", "Running Shoes", "Waterproof Backpack", "Cotton T-Shirt", "Hiking Boots", "Compression Socks", "Tactical Belt", "Weatherproof Gloves", "Fleece Hoodie", "Sports Duffel"]],
        "Home & Kitchen": ["HKT", ["Air Fryer", "Espresso Machine", "Stainless Steel Knife Set", "Blender 1000W", "Cast Iron Skillet", "Robot Vacuum", "Non-stick Cookware Set", "Water Filter Pitcher", "Food Processor", "Electric Kettle"]],
        "Industrial & Tools": ["IND", ["Cordless Drill", "Laser Measure", "Safety Goggles", "Toolbox Set 100pc", "Digital Caliper", "Angle Grinder", "Work Workbench Light", "Torque Wrench", "Heavy Duty Gloves", "Measuring Tape 25ft"]],
        "Office Supplies": ["OFF", ["Ergonomic Desk Chair", "Standing Desk Converter", "Paper Shredder 12-Sheet", "Dual Monitor Arm", "Desk Mat Large", "Gel Pen Box 24pc", "Filing Cabinet 3-Drawer", "Whiteboard 36x24", "Label Printer", "Document Scanner"]],
        "Healthcare & Safety": ["HCS", ["First Aid Kit 200pc", "Digital Thermometer", "Pulse Oximeter", "N95 Respirator Box", "Hand Sanitizer 1L", "Ergonomic Back Brace", "Automated Defibrillator Trainer", "Safety Vest Reflective", "Nitrile Gloves Box", "Eye Wash Station"]]
    }

    suppliers = [
        "Vanguard Components Inc.",
        "Apex Supply Chain Solutions",
        "Nordic Logistics & Trading",
        "Precision Dynamics Ltd.",
        "GlobalTech Distributing",
        "Horizon Industrial Corp.",
        "Summit Trading Group",
        "Nexus Mercantile Co.",
        "Prime Source International",
        "Atlas Cargo & Imports"
    ]

    products = []
    product_id = 1

    for cat_name, (prefix, templates) in categories.items():
        for i in range(1, 87):  # ~86 products per category -> total 516 products
            template = np.random.choice(templates)
            variant = f"Mod-{np.random.randint(100, 999)}"
            product_name = f"{template} {variant}"
            sku = f"{prefix}-{product_id:04d}"
            supplier = np.random.choice(suppliers)

            # Cost and pricing logic
            base_cost = round(float(np.random.uniform(8.0, 450.0)), 2)
            markup = np.random.uniform(1.35, 1.95)
            selling_price = round(base_cost * markup, 2)

            # Demand classification profile for Pareto simulation
            # 15% fast movers, 65% normal, 20% slow movers
            mover_roll = np.random.random()
            if mover_roll < 0.15:
                profile = "fast"
                daily_avg_demand = np.random.uniform(4.0, 12.0)
            elif mover_roll < 0.80:
                profile = "normal"
                daily_avg_demand = np.random.uniform(0.8, 3.5)
            else:
                profile = "slow"
                daily_avg_demand = np.random.uniform(0.05, 0.5)

            lead_time = int(np.random.randint(3, 22))
            
            # Reorder point calculation: ROP = (daily_avg * lead_time) + safety_stock
            safety_stock = int(np.ceil(daily_avg_demand * lead_time * 0.5))
            reorder_point = int(np.ceil(daily_avg_demand * lead_time + safety_stock))
            min_order_qty = max(20, int(np.ceil(daily_avg_demand * 30)))

            # Initial stock set relative to demand profile
            # We will adjust stock after generating transactions
            initial_stock = int(np.random.uniform(reorder_point * 0.8, reorder_point * 3.5))

            products.append({
                "product_id": product_id,
                "sku": sku,
                "product_name": product_name,
                "category": cat_name,
                "supplier": supplier,
                "unit_cost": base_cost,
                "selling_price": selling_price,
                "reorder_point": reorder_point,
                "min_order_qty": min_order_qty,
                "supplier_lead_time_days": lead_time,
                "daily_avg_demand": daily_avg_demand,
                "initial_stock": initial_stock,
                "current_stock": initial_stock
            })
            product_id += 1

    products_df = pd.DataFrame(products)

    # Generate 12 months of sales transactions
    end_date = datetime.date(2026, 10, 1)
    start_date = end_date - datetime.timedelta(days=365)

    transactions = []
    tx_id = 1

    # Track inventory balances dynamically over time
    stock_tracker = {p["product_id"]: p["initial_stock"] for p in products}

    current_d = start_date
    while current_d <= end_date:
        day_of_year = current_d.timetuple().tm_yday
        is_weekend = current_d.weekday() >= 5
        
        # Seasonality factor (Q4 holiday surge in Nov/Dec)
        month = current_d.month
        seasonality = 1.35 if month in [11, 12] else (0.9 if month in [1, 2] else 1.0)
        weekend_factor = 0.85 if is_weekend else 1.05

        # Sample products that sell on this day
        # Higher probability for fast movers
        for _, prod in products_df.iterrows():
            pid = prod["product_id"]
            sku = prod["sku"]
            demand_rate = prod["daily_avg_demand"] * seasonality * weekend_factor
            
            # Poisson distribution for daily sales quantity
            qty_demanded = np.random.poisson(demand_rate)
            
            if qty_demanded > 0:
                available = stock_tracker[pid]
                actual_sold = min(qty_demanded, available)
                
                if actual_sold > 0:
                    stock_tracker[pid] -= actual_sold
                    transactions.append({
                        "transaction_id": tx_id,
                        "product_id": pid,
                        "sku": sku,
                        "transaction_type": "Sale",
                        "quantity": int(actual_sold),
                        "unit_price": float(prod["selling_price"]),
                        "total_amount": round(float(actual_sold * prod["selling_price"]), 2),
                        "transaction_date": current_d.strftime("%Y-%m-%d"),
                        "notes": "Customer Sale Order"
                    })
                    tx_id += 1
                
                # Check if stock dropped below reorder point -> trigger periodic purchase order restocking
                if stock_tracker[pid] <= prod["reorder_point"] and np.random.random() < 0.45:
                    purchase_qty = prod["min_order_qty"]
                    stock_tracker[pid] += purchase_qty
                    transactions.append({
                        "transaction_id": tx_id,
                        "product_id": pid,
                        "sku": sku,
                        "transaction_type": "Purchase",
                        "quantity": int(purchase_qty),
                        "unit_price": float(prod["unit_cost"]),
                        "total_amount": round(float(purchase_qty * prod["unit_cost"]), 2),
                        "transaction_date": current_d.strftime("%Y-%m-%d"),
                        "notes": "Supplier Restock Purchase Order"
                    })
                    tx_id += 1

        # Occasional inventory audit adjustments (1-2 per week across catalog)
        if np.random.random() < 0.3:
            rand_prod = products_df.sample(1).iloc[0]
            pid = rand_prod["product_id"]
            adj_qty = np.random.choice([-5, -3, -1, 2, 5])
            if stock_tracker[pid] + adj_qty >= 0:
                stock_tracker[pid] += adj_qty
                transactions.append({
                    "transaction_id": tx_id,
                    "product_id": pid,
                    "sku": rand_prod["sku"],
                    "transaction_type": "Adjustment",
                    "quantity": int(abs(adj_qty)),
                    "unit_price": float(rand_prod["unit_cost"]),
                    "total_amount": round(float(abs(adj_qty) * rand_prod["unit_cost"]), 2),
                    "transaction_date": current_d.strftime("%Y-%m-%d"),
                    "notes": f"Stock Audit {'Shrinkage' if adj_qty < 0 else 'Found Inventory'}"
                })
                tx_id += 1

        current_d += datetime.timedelta(days=1)

    # Update final current_stock in products_df
    products_df["current_stock"] = products_df["product_id"].map(stock_tracker)
    
    # Force some realistic low stock / stockout scenarios for analytics testing
    # Force ~15 products out of stock and ~35 low stock
    out_of_stock_ids = np.random.choice(products_df["product_id"], size=15, replace=False)
    products_df.loc[products_df["product_id"].isin(out_of_stock_ids), "current_stock"] = 0

    low_stock_ids = np.random.choice(products_df[~products_df["product_id"].isin(out_of_stock_ids)]["product_id"], size=35, replace=False)
    for l_id in low_stock_ids:
        rop = products_df.loc[products_df["product_id"] == l_id, "reorder_point"].values[0]
        products_df.loc[products_df["product_id"] == l_id, "current_stock"] = np.random.randint(1, max(2, rop))

    # Drop internal helper columns before saving
    final_products_df = products_df[[
        "product_id", "sku", "product_name", "category", "supplier",
        "unit_cost", "selling_price", "current_stock", "reorder_point",
        "min_order_qty", "supplier_lead_time_days"
    ]]

    tx_df = pd.DataFrame(transactions)

    os.makedirs("data", exist_ok=True)
    final_products_df.to_csv("data/products.csv", index=False)
    tx_df.to_csv("data/transactions.csv", index=False)

    print(f"Generated {len(final_products_df)} products and {len(tx_df)} transactions.")
    print("Categories distribution:")
    print(final_products_df["category"].value_counts())
    print("\nStock Status Summary:")
    print("Out of stock:", (final_products_df["current_stock"] == 0).sum())
    print("Low stock:", (final_products_df["current_stock"] <= final_products_df["reorder_point"]).sum())

if __name__ == "__main__":
    generate_inventory_dataset()
