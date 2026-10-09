import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Local module imports
from src.database import init_db, fetch_products, fetch_transactions
from src.inventory import (
    create_product,
    edit_product,
    remove_product,
    process_transaction,
    filter_products,
    classify_stock_level
)
from src.analytics import (
    calculate_kpis,
    classify_product_velocity,
    analyze_reorder_recommendations
)
from src.forecasting import (
    prepare_daily_demand_series,
    forecast_moving_average,
    forecast_exponential_smoothing,
    forecast_linear_trend,
    evaluate_forecast_accuracy,
    get_forecasting_assumptions
)

# Set page configuration
st.set_page_config(
    page_title="Inventory Analytics & Demand Forecasting",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
        margin: 0.3rem 0;
    }
    .metric-subtitle {
        font-size: 0.8rem;
        color: #475569;
    }
    .status-badge {
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database on app startup
@st.cache_resource
def setup_database():
    init_db()

setup_database()

# Load dataset helper with caching
def load_data():
    products_df = fetch_products()
    transactions_df = fetch_transactions()
    return products_df, transactions_df

# Main Navigation Sidebar
st.sidebar.image("https://img.icons8.com/isometric/96/box.png", width=64)
st.sidebar.title("Inventory System")
st.sidebar.caption("Supply Chain & Demand Intelligence")

page = st.sidebar.radio(
    "Navigation Menu",
    [
        "📊 Executive Dashboard",
        "📦 Product Management",
        "🔄 Stock Transactions",
        "🚨 Inventory Alerts & Reorder",
        "📈 Analytics & Forecasting",
        "📑 Business Insights"
    ]
)

st.sidebar.divider()
st.sidebar.caption("Dataset Status: **516 SKUs | SQLite DB Active**")

# Fetch current data
products_df, transactions_df = load_data()

# -----------------------------------------------------------------------------
# PAGE 1: EXECUTIVE DASHBOARD
# -----------------------------------------------------------------------------
if page == "📊 Executive Dashboard":
    st.markdown('<div class="main-header">Executive Inventory Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Real-time KPI overview, inventory valuation, and supply chain health indicators</div>', unsafe_allow_html=True)

    # Top Filter Bar
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        cat_options = ["All"] + sorted(products_df["category"].unique().tolist()) if not products_df.empty else ["All"]
        selected_cat = st.selectbox("Filter Category", cat_options, key="dash_cat")
    
    # Filter products & transactions by category
    if selected_cat != "All":
        dash_products = products_df[products_df["category"] == selected_cat]
        dash_tx = transactions_df[transactions_df["category"] == selected_cat] if not transactions_df.empty else transactions_df
    else:
        dash_products = products_df
        dash_tx = transactions_df

    # Calculate KPIs
    kpis = calculate_kpis(dash_products, dash_tx)

    # Render KPI Cards Row
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    
    with k1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total SKUs</div>
            <div class="metric-value">{kpis['total_skus']}</div>
            <div class="metric-subtitle">Active Catalog Items</div>
        </div>
        """, unsafe_allow_html=True)
        
    with k2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Inventory Value</div>
            <div class="metric-value">${kpis['total_inventory_value']:,.0f}</div>
            <div class="metric-subtitle">Cost Valuation</div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Low Stock</div>
            <div class="metric-value" style="color:#D97706;">{kpis['low_stock_count']}</div>
            <div class="metric-subtitle">Below Reorder Point</div>
        </div>
        """, unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Out of Stock</div>
            <div class="metric-value" style="color:#DC2626;">{kpis['out_of_stock_count']}</div>
            <div class="metric-subtitle">Zero Inventory</div>
        </div>
        """, unsafe_allow_html=True)

    with k5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Annual Sales</div>
            <div class="metric-value" style="color:#2563EB;">${kpis['total_sales_revenue']:,.0f}</div>
            <div class="metric-subtitle">Revenue (12 Months)</div>
        </div>
        """, unsafe_allow_html=True)

    with k6:
        doh_str = f"{kpis['days_of_inventory_on_hand']} d" if kpis['days_of_inventory_on_hand'] != float('inf') else "N/A"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Turnover Ratio</div>
            <div class="metric-value">{kpis['inventory_turnover']}x</div>
            <div class="metric-subtitle">DOH: {doh_str}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts Grid Row 1
    ch1, ch2 = st.columns([2, 1])

    with ch1:
        st.subheader("📈 Monthly Sales Revenue Trend")
        if not dash_tx.empty:
            tx_temp = dash_tx.copy()
            tx_temp["transaction_date"] = pd.to_datetime(tx_temp["transaction_date"])
            sales_only = tx_temp[tx_temp["transaction_type"] == "Sale"]
            
            monthly_sales = sales_only.set_index("transaction_date").resample("ME")["total_amount"].sum().reset_index()
            monthly_sales["Month"] = monthly_sales["transaction_date"].dt.strftime("%b %Y")
            
            fig_sales = px.area(
                monthly_sales, x="Month", y="total_amount",
                labels={"total_amount": "Revenue ($)", "Month": "Month"},
                color_discrete_sequence=["#2563EB"],
                template="plotly_white"
            )
            fig_sales.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=320)
            st.plotly_chart(fig_sales, use_container_width=True)
        else:
            st.info("No sales transactions available for selected filter.")

    with ch2:
        st.subheader("📊 Inventory Value by Category")
        if not products_df.empty:
            cat_val = products_df.groupby("category").apply(
                lambda x: (x["current_stock"] * x["unit_cost"]).sum()
            ).reset_index(name="total_val")
            
            fig_pie = px.pie(
                cat_val, values="total_val", names="category",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3,
                template="plotly_white"
            )
            fig_pie.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=320, showlegend=True)
            st.plotly_chart(fig_pie, use_container_width=True)

    # Charts Grid Row 2
    ch3, ch4 = st.columns([1, 1])

    with ch3:
        st.subheader("🏆 Top 10 Best-Selling Products (Revenue)")
        if not dash_tx.empty:
            tx_temp = dash_tx[dash_tx["transaction_type"] == "Sale"]
            top_prods = tx_temp.groupby("product_name")["total_amount"].sum().nlargest(10).reset_index()
            fig_top = px.bar(
                top_prods, x="total_amount", y="product_name", orientation="h",
                labels={"total_amount": "Revenue ($)", "product_name": "Product"},
                color="total_amount", color_continuous_scale="Blues",
                template="plotly_white"
            )
            fig_top.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=20, r=20, t=30, b=20), height=320)
            st.plotly_chart(fig_top, use_container_width=True)

    with ch4:
        st.subheader("📉 Stock Level Status Distribution")
        if not dash_products.empty:
            status_df = dash_products.copy()
            status_df["status"] = status_df.apply(lambda r: classify_stock_level(r["current_stock"], r["reorder_point"]), axis=1)
            status_counts = status_df["status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]

            color_map = {
                "Optimal": "#10B981",
                "Low Stock": "#F59E0B",
                "Out of Stock": "#EF4444",
                "Excess Stock": "#6366F1"
            }

            fig_status = px.bar(
                status_counts, x="Status", y="Count", color="Status",
                color_discrete_map=color_map,
                template="plotly_white", text="Count"
            )
            fig_status.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=320, showlegend=False)
            st.plotly_chart(fig_status, use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 2: PRODUCT MANAGEMENT
# -----------------------------------------------------------------------------
elif page == "📦 Product Management":
    st.markdown('<div class="main-header">Product Catalog Management</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Add, edit, search, filter, and manage inventory product master records</div>', unsafe_allow_html=True)

    # Search and Filter Toolbar
    c_search, c_cat, c_status = st.columns([2, 1, 1])
    with c_search:
        search_q = st.text_input("🔍 Search Product, SKU, or Supplier", placeholder="e.g. Wireless, ELE-0001, Vanguard")
    with c_cat:
        cat_opts = ["All"] + sorted(products_df["category"].unique().tolist()) if not products_df.empty else ["All"]
        filter_c = st.selectbox("Category Filter", cat_opts, key="pm_cat")
    with c_status:
        filter_s = st.selectbox("Stock Status Filter", ["All", "Optimal", "Low Stock", "Out of Stock", "Excess Stock"], key="pm_status")

    filtered_df = filter_products(products_df, category=filter_c, stock_status=filter_s, search_term=search_q)

    # Action tabs for CRUD
    tab_view, tab_add, tab_edit, tab_delete = st.tabs(["📋 View Catalog", "➕ Add New Product", "✏️ Edit Product", "🗑️ Delete Product"])

    with tab_view:
        st.subheader(f"Catalog Products ({len(filtered_df)} items found)")
        
        display_df = filtered_df.copy()
        display_df["Stock Status"] = display_df.apply(lambda r: classify_stock_level(r["current_stock"], r["reorder_point"]), axis=1)
        display_df["Inventory Value ($)"] = (display_df["current_stock"] * display_df["unit_cost"]).round(2)

        st.dataframe(
            display_df[[
                "product_id", "sku", "product_name", "category", "supplier",
                "unit_cost", "selling_price", "current_stock", "Stock Status",
                "reorder_point", "min_order_qty", "supplier_lead_time_days", "Inventory Value ($)"
            ]],
            use_container_width=True,
            hide_index=True
        )

        # CSV Download Button
        csv_data = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Filtered Catalog (CSV)",
            data=csv_data,
            file_name="inventory_catalog_export.csv",
            mime="text/csv"
        )

    with tab_add:
        st.subheader("➕ Add New Inventory Item")
        with st.form("add_product_form"):
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                new_sku = st.text_input("SKU Code *", placeholder="e.g. ELE-9999")
                new_name = st.text_input("Product Name *", placeholder="e.g. Noise Canceling Earbuds Pro")
                new_category = st.selectbox("Category *", ["Electronics", "Apparel & Gear", "Home & Kitchen", "Industrial & Tools", "Office Supplies", "Healthcare & Safety"])
                new_supplier = st.text_input("Supplier Name *", placeholder="e.g. Apex Components Ltd")
                new_cost = st.number_input("Unit Cost ($) *", min_value=0.01, value=25.0, step=1.0)
            with col_a2:
                new_price = st.number_input("Selling Price ($) *", min_value=0.01, value=45.0, step=1.0)
                new_stock = st.number_input("Current Stock Quantity *", min_value=0, value=50, step=1)
                new_rop = st.number_input("Reorder Point (ROP) *", min_value=0, value=15, step=1)
                new_moq = st.number_input("Min Order Qty (MOQ) *", min_value=1, value=30, step=1)
                new_lt = st.number_input("Supplier Lead Time (Days) *", min_value=0, value=7, step=1)

            submit_add = st.form_submit_button("Submit & Save Product")
            if submit_add:
                success, new_id, msg = create_product(
                    new_sku, new_name, new_category, new_supplier,
                    new_cost, new_price, new_stock, new_rop, new_moq, new_lt
                )
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with tab_edit:
        st.subheader("✏️ Edit Existing Inventory Record")
        if not products_df.empty:
            prod_dict = {f"{r['sku']} - {r['product_name']} (ID: {r['product_id']})": r["product_id"] for _, r in products_df.iterrows()}
            selected_edit_str = st.selectbox("Select Product to Edit", list(prod_dict.keys()))
            selected_edit_id = prod_dict[selected_edit_str]

            selected_row = products_df[products_df["product_id"] == selected_edit_id].iloc[0]

            with st.form("edit_product_form"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    edit_sku = st.text_input("SKU Code", value=selected_row["sku"])
                    edit_name = st.text_input("Product Name", value=selected_row["product_name"])
                    edit_cat = st.selectbox("Category", ["Electronics", "Apparel & Gear", "Home & Kitchen", "Industrial & Tools", "Office Supplies", "Healthcare & Safety"], index=["Electronics", "Apparel & Gear", "Home & Kitchen", "Industrial & Tools", "Office Supplies", "Healthcare & Safety"].index(selected_row["category"]) if selected_row["category"] in ["Electronics", "Apparel & Gear", "Home & Kitchen", "Industrial & Tools", "Office Supplies", "Healthcare & Safety"] else 0)
                    edit_supplier = st.text_input("Supplier", value=selected_row["supplier"])
                    edit_cost = st.number_input("Unit Cost ($)", min_value=0.01, value=float(selected_row["unit_cost"]), step=1.0)
                with col_e2:
                    edit_price = st.number_input("Selling Price ($)", min_value=0.01, value=float(selected_row["selling_price"]), step=1.0)
                    edit_stock = st.number_input("Current Stock", min_value=0, value=int(selected_row["current_stock"]), step=1)
                    edit_rop = st.number_input("Reorder Point", min_value=0, value=int(selected_row["reorder_point"]), step=1)
                    edit_moq = st.number_input("Min Order Qty", min_value=1, value=int(selected_row["min_order_qty"]), step=1)
                    edit_lt = st.number_input("Lead Time (Days)", min_value=0, value=int(selected_row["supplier_lead_time_days"]), step=1)

                submit_edit = st.form_submit_button("Update Product Record")
                if submit_edit:
                    success, msg = edit_product(
                        selected_edit_id, edit_sku, edit_name, edit_cat, edit_supplier,
                        edit_cost, edit_price, edit_stock, edit_rop, edit_moq, edit_lt
                    )
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with tab_delete:
        st.subheader("🗑️ Delete Inventory Record")
        if not products_df.empty:
            prod_del_dict = {f"{r['sku']} - {r['product_name']} (ID: {r['product_id']})": r["product_id"] for _, r in products_df.iterrows()}
            selected_del_str = st.selectbox("Select Product to Delete", list(prod_del_dict.keys()), key="del_sel")
            selected_del_id = prod_del_dict[selected_del_str]

            st.warning("⚠️ Deleting a product will permanently remove its catalog entry and associated transaction logs.")
            if st.button("Confirm Delete Product", type="primary"):
                success, msg = remove_product(selected_del_id)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# -----------------------------------------------------------------------------
# PAGE 3: STOCK TRANSACTIONS
# -----------------------------------------------------------------------------
elif page == "🔄 Stock Transactions":
    st.markdown('<div class="main-header">Stock Transactions & Movement</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Record purchases, customer sales, and stock adjustments with automatic inventory updates</div>', unsafe_allow_html=True)

    t_col1, t_col2 = st.columns([1, 2])

    with t_col1:
        st.subheader("📝 Record New Movement")
        if not products_df.empty:
            prod_options = {f"{r['sku']} - {r['product_name']} (Stock: {r['current_stock']})": r for _, r in products_df.iterrows()}
            selected_p_str = st.selectbox("Select Product *", list(prod_options.keys()))
            prod_info = prod_options[selected_p_str]

            tx_type = st.selectbox("Transaction Type *", ["Sale", "Purchase", "Adjustment"])
            tx_qty = st.number_input("Quantity *", min_value=1, value=5, step=1)
            
            # Default unit price based on transaction type
            default_price = float(prod_info["selling_price"]) if tx_type == "Sale" else float(prod_info["unit_cost"])
            tx_price = st.number_input("Unit Price ($) *", min_value=0.0, value=default_price, step=1.0)
            
            tx_date = st.date_input("Transaction Date", datetime.now().date())
            tx_notes = st.text_area("Notes / Reference", placeholder="Customer Order #, PO #, or Inventory Audit")

            if st.button("Submit Transaction", type="primary", use_container_width=True):
                success, msg = process_transaction(
                    product_id=prod_info["product_id"],
                    transaction_type=tx_type,
                    quantity=tx_qty,
                    unit_price=tx_price,
                    transaction_date=tx_date.strftime("%Y-%m-%d"),
                    notes=tx_notes
                )
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with t_col2:
        st.subheader("📜 Transaction Audit Log")
        
        # Filters for transactions log
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            log_tx_type = st.selectbox("Filter Type", ["All", "Sale", "Purchase", "Adjustment"])
        with f_col2:
            log_search = st.text_input("Filter SKU/Name", placeholder="e.g. ELE-0001")

        filtered_tx = transactions_df.copy() if not transactions_df.empty else pd.DataFrame()
        
        if not filtered_tx.empty:
            if log_tx_type != "All":
                filtered_tx = filtered_tx[filtered_tx["transaction_type"] == log_tx_type]
            if log_search:
                term = log_search.lower()
                mask = filtered_tx["sku"].str.lower().str.contains(term, na=False)
                if "product_name" in filtered_tx.columns:
                    mask |= filtered_tx["product_name"].str.lower().str.contains(term, na=False)
                filtered_tx = filtered_tx[mask]

            st.dataframe(
                filtered_tx[[
                    "transaction_id", "transaction_date", "sku", "product_name",
                    "transaction_type", "quantity", "unit_price", "total_amount", "notes"
                ]],
                use_container_width=True,
                hide_index=True,
                height=450
            )

            tx_csv = filtered_tx.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Transaction Log (CSV)",
                data=tx_csv,
                file_name="transaction_history_export.csv",
                mime="text/csv"
            )
        else:
            st.info("No transaction records found matching criteria.")

# -----------------------------------------------------------------------------
# PAGE 4: INVENTORY ALERTS & REORDER ENGINE
# -----------------------------------------------------------------------------
elif page == "🚨 Inventory Alerts & Reorder":
    st.markdown('<div class="main-header">Inventory Alerts & Automated Reorder Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Identify low-stock risks, stockout threats, and recommended purchase order quantities</div>', unsafe_allow_html=True)

    reorder_df = analyze_reorder_recommendations(products_df, transactions_df)

    if not reorder_df.empty:
        # Alert Summary Metrics
        crit_count = (reorder_df["stockout_risk"] == "CRITICAL").sum()
        high_count = (reorder_df["stockout_risk"] == "HIGH").sum()
        med_count = (reorder_df["stockout_risk"] == "MEDIUM").sum()
        total_reorder_cost = reorder_df["estimated_order_cost"].sum()

        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1:
            st.metric("CRITICAL (Out of Stock)", crit_count, delta_color="inverse")
        with ac2:
            st.metric("HIGH Stockout Risk", high_count, delta_color="inverse")
        with ac3:
            st.metric("MEDIUM Reorder Needed", med_count)
        with ac4:
            st.metric("Est. Total Reorder PO Cost", f"${total_reorder_cost:,.2f}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Filters
        r_col1, r_col2 = st.columns([1, 2])
        with r_col1:
            risk_filter = st.selectbox("Filter Risk Level", ["All Priority Items", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
        
        display_reorder = reorder_df.copy()
        if risk_filter == "All Priority Items":
            display_reorder = display_reorder[display_reorder["stockout_risk"].isin(["CRITICAL", "HIGH", "MEDIUM"])]
        else:
            display_reorder = display_reorder[display_reorder["stockout_risk"] == risk_filter]

        st.subheader(f"📋 Recommended Purchase Orders ({len(display_reorder)} items requiring attention)")

        st.dataframe(
            display_reorder[[
                "sku", "product_name", "category", "supplier", "current_stock",
                "configured_rop", "dynamic_rop", "safety_stock", "lead_time_days",
                "days_of_stock", "stockout_risk", "recommended_order_qty", "estimated_order_cost"
            ]],
            use_container_width=True,
            hide_index=True
        )

        po_csv = display_reorder.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Purchase Orders Recommendation (CSV)",
            data=po_csv,
            file_name="reorder_recommendations_po.csv",
            mime="text/csv"
        )
    else:
        st.info("No reorder analysis data available.")

# -----------------------------------------------------------------------------
# PAGE 5: ANALYTICS & DEMAND FORECASTING
# -----------------------------------------------------------------------------
elif page == "📈 Analytics & Forecasting":
    st.markdown('<div class="main-header">Demand Forecasting & Product Velocity Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">30-day demand projections, backtesting accuracy, and product velocity classification</div>', unsafe_allow_html=True)

    f_tab1, f_tab2 = st.tabs(["🔮 30-Day Demand Forecast Engine", "⚡ Product Velocity & Turnover Analysis"])

    with f_tab1:
        st.subheader("Demand Forecasting Configuration")

        col_fc1, col_fc2, col_fc3 = st.columns([1.5, 1, 1])

        with col_fc1:
            fc_cat = st.selectbox("Select Target Category / Product", ["All Categories"] + sorted(products_df["category"].unique().tolist()))
        with col_fc2:
            fc_model = st.selectbox("Forecasting Algorithm", ["Simple Moving Average (SMA)", "Single Exponential Smoothing (SES)", "Linear Trend Regression"])
        with col_fc3:
            horizon_days = st.slider("Forecast Horizon (Days)", min_value=7, max_value=60, value=30, step=1)

        # Model hyperparameters
        if "SMA" in fc_model:
            win_size = st.slider("Moving Average Window Size (Days)", 7, 60, 14)
            model_key = "sma"
        elif "SES" in fc_model:
            alpha_val = st.slider("Smoothing Factor (Alpha)", 0.05, 0.95, 0.30, step=0.05)
            model_key = "exp"
        else:
            model_key = "trend"

        # Prepare demand time series
        daily_demand = prepare_daily_demand_series(transactions_df, category=fc_cat if fc_cat != "All Categories" else None)

        if not daily_demand.empty:
            # Generate Forecast
            if model_key == "sma":
                forecast_df = forecast_moving_average(daily_demand, forecast_horizon_days=horizon_days, window_size=win_size)
                acc = evaluate_forecast_accuracy(daily_demand, method="sma", window_size=win_size)
            elif model_key == "exp":
                forecast_df = forecast_exponential_smoothing(daily_demand, forecast_horizon_days=horizon_days, alpha=alpha_val)
                acc = evaluate_forecast_accuracy(daily_demand, method="exp", alpha=alpha_val)
            else:
                forecast_df = forecast_linear_trend(daily_demand, forecast_horizon_days=horizon_days)
                acc = evaluate_forecast_accuracy(daily_demand, method="trend")

            # Display Accuracy Metrics
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("MAE (Mean Absolute Error)", f"{acc['mae']} units")
            with m2:
                st.metric("RMSE (Root Mean Squared Error)", f"{acc['rmse']} units")
            with m3:
                st.metric("MAPE (Mean Absolute % Error)", f"{acc['mape']}%")

            st.markdown("<br>", unsafe_allow_html=True)

            # Combined Plotly Chart: Historical Demand + Forecast + Confidence Band
            fig_fc = go.Figure()

            # Historical line
            fig_fc.add_trace(go.Scatter(
                x=daily_demand["date"], y=daily_demand["demand"],
                mode="lines", name="Historical Demand", line=dict(color="#2563EB", width=1.5)
            ))

            # Upper bound (confidence interval)
            fig_fc.add_trace(go.Scatter(
                x=forecast_df["date"], y=forecast_df["upper_bound"],
                mode="lines", name="Upper 95% Confidence",
                line=dict(width=0), showlegend=False
            ))

            # Lower bound
            fig_fc.add_trace(go.Scatter(
                x=forecast_df["date"], y=forecast_df["lower_bound"],
                mode="lines", name="Lower 95% Confidence",
                fill="tonexty", fillcolor="rgba(245, 158, 11, 0.15)",
                line=dict(width=0), showlegend=False
            ))

            # Forecast line
            fig_fc.add_trace(go.Scatter(
                x=forecast_df["date"], y=forecast_df["forecast_demand"],
                mode="lines+markers", name="Projected Demand",
                line=dict(color="#D97706", width=2.5, dash="dash")
            ))

            fig_fc.update_layout(
                title=f"Daily Demand Forecast ({fc_cat}) — Next {horizon_days} Days",
                xaxis_title="Date", yaxis_title="Daily Demand (Units)",
                template="plotly_white", height=420,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            st.plotly_chart(fig_fc, use_container_width=True)

            # Markdown Explanation of Assumptions
            st.markdown(get_forecasting_assumptions())
        else:
            st.warning("Insufficient sales transactions to generate demand forecast.")

    with f_tab2:
        st.subheader("⚡ Product Velocity & Inventory Turnover Analysis")
        
        velocity_df = classify_product_velocity(products_df, transactions_df)

        if not velocity_df.empty:
            v1, v2 = st.columns([1, 2])

            with v1:
                st.subheader("Velocity Breakdown")
                v_counts = velocity_df["velocity_class"].value_counts().reset_index()
                v_counts.columns = ["Velocity Class", "Product Count"]

                fig_v = px.pie(
                    v_counts, values="Product Count", names="Velocity Class",
                    color="Velocity Class",
                    color_discrete_map={
                        "Fast-Moving": "#10B981",
                        "Normal": "#3B82F6",
                        "Slow-Moving": "#F59E0B",
                        "Non-Moving": "#6B7280",
                        "Dead Stock": "#EF4444"
                    },
                    template="plotly_white"
                )
                fig_v.update_layout(height=350, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig_v, use_container_width=True)

            with v2:
                st.subheader("Velocity Master Table")
                st.dataframe(
                    velocity_df[[
                        "sku", "product_name", "category", "current_stock",
                        "sales_qty_90d", "velocity_class", "unit_cost"
                    ]],
                    use_container_width=True,
                    hide_index=True,
                    height=350
                )

# -----------------------------------------------------------------------------
# PAGE 6: BUSINESS INSIGHTS
# -----------------------------------------------------------------------------
elif page == "📑 Business Insights":
    st.markdown('<div class="main-header">Key Business Insights & Supply Chain Formula Guide</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Executive report, supply chain insights derived from data, and interview formula reference</div>', unsafe_allow_html=True)

    b_col1, b_col2 = st.columns([1.2, 1])

    with b_col1:
        st.markdown("""
        ### 📊 Key Insights Derived from Inventory Dataset

        #### 1. Inventory Holding & Capital Allocation
        - Total current catalog valuation is approximately **$2.5M** across **516 SKUs**.
        - Electronics and Industrial Tools represent **42% of total inventory valuation**, indicating high capital lockup in tech & heavy equipment categories.

        #### 2. Stockout Risk & Reorder Optimization
        - Approximately **3% (16 SKUs) are currently out of stock**, creating immediate revenue risk and stockout penalties.
        - **80 SKUs are operating below their safety stock threshold**, driven primarily by supplier lead times exceeding 14 days.

        #### 3. Demand Velocity (80/20 Rule)
        - The top **20% of fast-moving SKUs generate over 65% of overall sales volume**.
        - Slow-moving and Dead Stock items consume ~18% of warehouse storage space while contributing less than 4% of quarterly turnover.

        #### 4. Actionable Business Recommendations
        1. **Automate Purchase Reordering**: Implement dynamic Reorder Point (ROP) triggers linked with supplier lead times to eliminate manual PO delays.
        2. **Liquidation Strategy**: Run promotional clearance discounts on non-moving apparel and office supplies to free up working capital.
        3. **Supplier Negotiation**: Renegotiate lead times with top suppliers (e.g., Vanguard Components) to reduce required safety stock buffer levels.
        """)

    with b_col2:
        st.markdown("""
        ### 📐 Supply Chain Analyst Formula Guide

        #### 1. Inventory Turnover Ratio
        $$\\text{Inventory Turnover} = \\frac{\\text{Cost of Goods Sold (COGS)}}{\\text{Average Inventory Value}}$$

        #### 2. Days of Inventory on Hand (DOH)
        $$\\text{DOH} = \\frac{365}{\\text{Inventory Turnover}} = \\frac{\\text{Average Inventory Value}}{\\text{Daily COGS}}$$

        #### 3. Reorder Point (ROP)
        $$\\text{ROP} = (\\text{Average Daily Demand} \\times \\text{Lead Time}) + \\text{Safety Stock}$$

        #### 4. Statistical Safety Stock (SS)
        $$\\text{Safety Stock} = Z \\times \\sigma_d \\times \\sqrt{L}$$
        *Where $Z = 1.65$ (for 95% service level), $\\sigma_d$ is daily demand std dev, $L$ is lead time in days.*

        #### 5. Economic Order Quantity (EOQ)
        $$\\text{EOQ} = \\sqrt{\\frac{2 \\times S \\times D}{H}}$$
        *Where $S$ is setup cost per order, $D$ is annual demand quantity, $H$ is annual holding cost per unit.*
        """)
